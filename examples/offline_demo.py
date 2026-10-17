"""Run the adapter with synthetic HTTP responses. No credentials/network required."""
import io
import json
import os
from pathlib import Path
import sys
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import proxmox_mcp_server as app


def fake_open(request, timeout):
    if request.get_method() != 'GET':
        raise AssertionError('Demo must not write')
    if request.full_url.endswith('/api2/json/nodes'):
        data = [{'node': 'node-a', 'status': 'online'},
                {'node': 'node-b', 'status': 'online'},
                {'node': 'node-c', 'status': 'online'}]
    else:
        raise AssertionError('Unexpected demo endpoint')
    return io.BytesIO(json.dumps({'data': data}).encode())


def main():
    print('OFFLINE DEMO | Synthetic nodes and credentials | No network access')
    environment = {
        'PROXMOX_BASE_URL': 'https://pve.example.com:8006',
        'PROXMOX_TOKEN_ID': 'portfolio@pve!readonly',
        'PROXMOX_TOKEN_SECRET': 'synthetic-demo-token',
    }
    with patch.dict(os.environ, environment, clear=True), patch('urllib.request.OpenerDirector.open', side_effect=fake_open):
        print('\n1. Initialize protocol')
        reply = app.handle_request({'jsonrpc': '2.0', 'id': 1, 'method': 'initialize',
            'params': {'protocolVersion': '2025-06-18'}})
        print(json.dumps(reply, indent=2))
        print('\n2. Discover read-only tools')
        print(', '.join(tool['name'] for tool in app.tools()))
        print('\n3. List nodes through the real HTTP request/response path with a fixture transport')
        reply = app.handle_request({'jsonrpc': '2.0', 'id': 2, 'method': 'tools/call',
            'params': {'name': 'proxmox_list_nodes', 'arguments': {}}})
        print(json.dumps(reply, indent=2))
        assert 'error' not in reply and not reply['result'].get('isError')
        print('\n4. Reject a guest shutdown while writes are disabled')
        reply = app.handle_request({'jsonrpc': '2.0', 'id': 3, 'method': 'tools/call',
            'params': {'name': 'proxmox_guest_power', 'arguments': {
                'node': 'node-a', 'guest_type': 'qemu', 'vmid': 111, 'action': 'shutdown'}}})
        print(json.dumps(reply, indent=2))
        assert reply['result']['isError'] is True
    print('\nCompleted: fixture read succeeded; write attempt denied.')


if __name__ == '__main__':
    main()
