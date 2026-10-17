import io
import json
import os
from pathlib import Path
import ssl
import subprocess
import sys
import unittest
from unittest.mock import MagicMock, patch
import urllib.error
import urllib.parse

import proxmox_mcp_server as app


ENV = {
    'PROXMOX_BASE_URL': 'https://pve.example.com:8006',
    'PROXMOX_TOKEN_ID': 'portfolio@pve!readonly',
    'PROXMOX_TOKEN_SECRET': 'synthetic-test-token',
}


def rpc(name, arguments=None):
    return app.handle_request({'jsonrpc': '2.0', 'id': 1, 'method': 'tools/call',
                               'params': {'name': name, 'arguments': arguments}})


class AdapterTests(unittest.TestCase):
    def setUp(self):
        self.environment = patch.dict(os.environ, ENV, clear=True)
        self.environment.start()
        self.addCleanup(self.environment.stop)
        self.network = patch('urllib.request.OpenerDirector.open',
                             side_effect=AssertionError('Unexpected network access'))
        self.network.start()
        self.addCleanup(self.network.stop)

    def test_read_catalog_excludes_every_write(self):
        self.assertTrue(app.tools())
        self.assertTrue(all(t['annotations']['readOnlyHint'] for t in app.tools()))
        self.assertLess(len(app.tools()), len(app.all_tools()))

    def test_every_write_denied_before_client_construction(self):
        with patch.object(app, 'ProxmoxClient') as client:
            for tool in app.all_tools():
                if not tool['annotations']['readOnlyHint']:
                    with self.subTest(tool=tool['name']):
                        self.assertTrue(rpc(tool['name'], {})['result']['isError'])
            client.assert_not_called()

    def test_direct_http_write_also_denied(self):
        client = app.ProxmoxClient()
        for method in (client.post, client.put):
            with self.subTest(method=method.__name__), self.assertRaises(PermissionError):
                method('/cluster/backup', {})

    def test_flag_requires_exact_true_value(self):
        for value in ('false', '1', 'yes', 'truthy'):
            with self.subTest(value=value), patch.dict(os.environ, {'PROXMOX_ENABLE_WRITES': value}):
                self.assertFalse(app.writes_enabled())
        with patch.dict(os.environ, {'PROXMOX_ENABLE_WRITES': 'true'}):
            self.assertEqual(len(app.tools()), len(app.all_tools()))

    def test_invalid_arguments_fail_without_client(self):
        cases = [
            ('missing', {}), ('proxmox_version', {'extra': 1}),
            ('proxmox_list_nodes', []), ('proxmox_recent_tasks', {'limit': True}),
            ('proxmox_recent_tasks', {'limit': 101}),
            ('proxmox_get_guest_status', {'node': 'a', 'guest_type': 'qemu'}),
            ('proxmox_get_guest_status', {'node': '../a', 'guest_type': 'qemu', 'vmid': 1}),
            ('proxmox_get_guest_status', {'node': 'a?b', 'guest_type': 'qemu', 'vmid': 1}),
            ('proxmox_get_guest_status', {'node': 'a', 'guest_type': 'other', 'vmid': 1}),
            ('proxmox_get_guest_status', {'node': 'a', 'guest_type': 'qemu', 'vmid': 0}),
            ('proxmox_get_guest_status', {'node': 'a', 'guest_type': 'qemu', 'vmid': '1'}),
        ]
        with patch.object(app, 'ProxmoxClient') as client:
            for name, args in cases:
                with self.subTest(name=name, args=args):
                    self.assertEqual(rpc(name, args)['error']['code'], -32602)
            client.assert_not_called()

    def test_https_origin_and_url_credentials(self):
        for url in ('http://pve.example.com', 'https://u:p@pve.example.com',
                    'https://pve.example.com/api2', 'https://pve.example.com?token=x',
                    'https://pve.example.com#fragment'):
            with self.subTest(url=url), patch.dict(os.environ, {'PROXMOX_BASE_URL': url}):
                with self.assertRaises(app.ConfigError):
                    app.ProxmoxClient()

    def test_missing_config_names_but_no_secret(self):
        with patch.dict(os.environ, {}, clear=True), self.assertRaises(app.ConfigError) as error:
            app.ProxmoxClient()
        self.assertIn('PROXMOX_BASE_URL', str(error.exception))
        self.assertNotIn('synthetic-test-token', str(error.exception))

    def test_timeout_validation(self):
        for value in ('0', '-1', 'NaN', 'inf', 'word'):
            with self.subTest(value=value), patch.dict(os.environ, {'PROXMOX_TIMEOUT': value}):
                with self.assertRaises(app.ConfigError):
                    app.ProxmoxClient()

    def test_tls_validation_cannot_be_disabled(self):
        with patch.dict(os.environ, {'PROXMOX_VERIFY_TLS': 'false'}):
            with self.assertRaises(app.ConfigError):
                app.ProxmoxClient()
        self.assertEqual(app.ProxmoxClient().ssl_context.verify_mode, ssl.CERT_REQUIRED)
        self.assertTrue(app.ProxmoxClient().ssl_context.check_hostname)

    def test_private_ca_forwarded_to_ssl(self):
        with patch.dict(os.environ, {'PROXMOX_CA_FILE': '/example/ca.pem'}):
            with patch.object(app.ssl, 'create_default_context', wraps=ssl.create_default_context) as factory:
                with self.assertRaises(FileNotFoundError):
                    app.ProxmoxClient()
                factory.assert_called_once_with(cafile='/example/ca.pem')

    def test_redirect_refused(self):
        with self.assertRaises(RuntimeError):
            app.NoRedirect().redirect_request(None, None, 302, '', {}, 'https://other.example.com')

    def test_get_request_auth_and_query(self):
        client = app.ProxmoxClient()
        response = MagicMock()
        response.__enter__.return_value.read.return_value = b'{"data":[{"vmid":111}]}'
        client.opener = MagicMock()
        client.opener.open.return_value = response
        self.assertEqual(client.get('/cluster/resources', {'type': 'vm'}), [{'vmid': 111}])
        request = client.opener.open.call_args.args[0]
        self.assertEqual(request.full_url, 'https://pve.example.com:8006/api2/json/cluster/resources?type=vm')
        self.assertEqual(request.get_header('Authorization'), 'PVEAPIToken=portfolio@pve!readonly=synthetic-test-token')
        self.assertNotIn('synthetic-test-token', request.full_url)
        self.assertEqual(request.get_method(), 'GET')

    def test_form_encoded_write(self):
        with patch.dict(os.environ, {'PROXMOX_ENABLE_WRITES': 'true'}):
            client = app.ProxmoxClient()
            response = MagicMock()
            response.__enter__.return_value.read.return_value = b'{"data":"UPID:synthetic"}'
            client.opener = MagicMock()
            client.opener.open.return_value = response
            self.assertEqual(client.post('/example', {'description': 'before update'}), 'UPID:synthetic')
            request = client.opener.open.call_args.args[0]
            self.assertEqual(request.get_method(), 'POST')
            self.assertEqual(urllib.parse.parse_qs(request.data.decode()), {'description': ['before update']})

    def test_api_errors_are_sanitized(self):
        client = app.ProxmoxClient()
        client.opener = MagicMock()
        client.opener.open.side_effect = urllib.error.HTTPError('https://private.example', 403, 'Forbidden', {}, io.BytesIO(b'private details'))
        with self.assertRaises(RuntimeError) as error:
            client.get('/version')
        self.assertIn('403', str(error.exception))
        self.assertNotIn('private', str(error.exception))

    def test_malformed_upstream_payloads(self):
        for body in (b'not-json', b'[]', b'{"unexpected":1}'):
            with self.subTest(body=body):
                client = app.ProxmoxClient()
                client.opener = MagicMock()
                client.opener.open.return_value.__enter__.return_value.read.return_value = body
                with self.assertRaises(RuntimeError):
                    client.get('/version')

    def test_execution_error_uses_is_error(self):
        with patch.object(app, 'ProxmoxClient') as factory:
            factory.return_value.get.side_effect = RuntimeError('Proxmox HTTP 403')
            result = rpc('proxmox_version')
            self.assertTrue(result['result']['isError'])
            self.assertNotIn('error', result)

    def test_node_failure_retains_other_guests(self):
        client = MagicMock()
        def get(path, params=None):
            if path == '/cluster/resources':
                return []
            if path == '/nodes':
                return [{'node': 'node-a'}, {'node': 'node-b'}]
            if path == '/nodes/node-a/qemu':
                return [{'vmid': 111}]
            if path.startswith('/nodes/node-b/'):
                raise RuntimeError('Unavailable')
            return []
        client.get.side_effect = get
        result = app.list_all_guests(client)['by_node']
        self.assertEqual(result[0]['vmid'], 111)
        self.assertEqual(sum('error' in row for row in result), 2)

    def test_power_and_snapshot_payloads(self):
        with patch.dict(os.environ, {'PROXMOX_ENABLE_WRITES': 'true'}), patch.object(app, 'ProxmoxClient') as factory:
            client = factory.return_value
            client.post.return_value = 'UPID:synthetic'
            args = {'node': 'node-a', 'guest_type': 'qemu', 'vmid': 111}
            rpc('proxmox_guest_power', {**args, 'action': 'shutdown'})
            client.post.assert_called_with('/nodes/node-a/qemu/111/status/shutdown')
            rpc('proxmox_create_snapshot', {**args, 'snapname': 'before-change', 'include_vm_state': True})
            self.assertEqual(client.post.call_args.args[1]['vmstate'], 1)
            rpc('proxmox_create_snapshot', {**args, 'guest_type': 'lxc', 'snapname': 'before-change', 'include_vm_state': True})
            self.assertNotIn('vmstate', client.post.call_args.args[1])

    def test_backup_and_storage_payload_translation(self):
        with patch.dict(os.environ, {'PROXMOX_ENABLE_WRITES': 'true'}), patch.object(app, 'ProxmoxClient') as factory:
            client = factory.return_value
            client.post.return_value = None
            client.put.return_value = None
            rpc('proxmox_create_backup_job', {'id': 'lab-job', 'storage': 'shared-nfs',
                'schedule': 'tue,sat 03:00', 'vmid': '111,113', 'enabled': False,
                'prune_backups': 'keep-last=4'})
            payload = client.post.call_args.args[1]
            self.assertEqual(payload['enabled'], 0)
            self.assertEqual(payload['prune-backups'], 'keep-last=4')
            rpc('proxmox_update_storage', {'storage': 'shared-nfs', 'prune_backups': 'keep-last=4'})
            client.put.assert_called_once_with('/storage/shared-nfs', {'prune-backups': 'keep-last=4'})

    def test_task_identifier_is_encoded(self):
        with patch.object(app, 'ProxmoxClient') as factory:
            factory.return_value.get.return_value = []
            rpc('proxmox_get_task_log', {'node': 'node-a', 'upid': 'UPID:demo/x?', 'limit': 2})
            factory.return_value.get.assert_called_once_with('/nodes/node-a/tasks/UPID%3Ademo%2Fx%3F/log')

    def test_protocol_envelopes_and_negotiation(self):
        for invalid in ([], None, {'method': 'ping'}, {'jsonrpc': '2.0', 'method': 2}):
            self.assertEqual(app.handle_request(invalid)['error']['code'], -32600)
        self.assertIsNone(app.handle_request({'jsonrpc': '2.0', 'method': 'notifications/initialized'}))
        request = {'jsonrpc': '2.0', 'id': 0, 'method': 'initialize', 'params': {'protocolVersion': 'future'}}
        self.assertEqual(app.handle_request(request)['result']['protocolVersion'], '2025-06-18')
        self.assertEqual(app.handle_request({**request, 'method': 'ping', 'params': {}})['result'], {})
        self.assertEqual(app.handle_request({**request, 'params': []})['error']['code'], -32602)
        self.assertEqual(app.handle_request({**request, 'method': 'missing'})['error']['code'], -32601)

    def test_stdio_recovery_after_invalid_json(self):
        script = Path(app.__file__)
        messages = '\n'.join(['not-json', json.dumps({'jsonrpc': '2.0', 'id': 0, 'method': 'ping'}),
            json.dumps({'jsonrpc': '2.0', 'method': 'notifications/initialized'}),
            json.dumps({'jsonrpc': '2.0', 'id': 2, 'method': 'tools/list'})]) + '\n'
        completed = subprocess.run([sys.executable, str(script)], input=messages, text=True,
                                   capture_output=True, env={}, timeout=15)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        rows = [json.loads(line) for line in completed.stdout.splitlines()]
        self.assertEqual(len(rows), 3)
        self.assertEqual(rows[0]['error']['code'], -32700)
        self.assertEqual(rows[1]['result'], {})
        self.assertTrue(all(t['annotations']['readOnlyHint'] for t in rows[2]['result']['tools']))


if __name__ == '__main__':
    unittest.main()
