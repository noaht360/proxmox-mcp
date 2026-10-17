#!/usr/bin/env python3
"""Small, read-only-by-default stdio MCP adapter for Proxmox VE.

Credentials come from environment variables:
  PROXMOX_BASE_URL
  PROXMOX_TOKEN_ID
  PROXMOX_TOKEN_SECRET
  PROXMOX_CA_FILE (optional)
  PROXMOX_ENABLE_WRITES (optional, defaults to false)
"""

from __future__ import annotations

import argparse
import json
import math
import re
import os
import ssl
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any


SERVER_NAME = "proxmox-mcp"
SERVER_VERSION = "0.2.0"
SUPPORTED_PROTOCOLS = ("2024-11-05", "2025-03-26", "2025-06-18")


class ConfigError(RuntimeError):
    pass


def writes_enabled() -> bool:
    # Exact opt-in avoids accidentally accepting misspelled values.
    return os.environ.get("PROXMOX_ENABLE_WRITES", "false").lower() == "true"


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise RuntimeError("Proxmox redirect refused; check PROXMOX_BASE_URL")


class ProxmoxClient:
    def __init__(self) -> None:
        self.base_url = os.environ.get("PROXMOX_BASE_URL", "").rstrip("/")
        self.token_id = os.environ.get("PROXMOX_TOKEN_ID", "")
        self.token_secret = os.environ.get("PROXMOX_TOKEN_SECRET", "")
        missing = [name for name, value in {
            "PROXMOX_BASE_URL": self.base_url,
            "PROXMOX_TOKEN_ID": self.token_id,
            "PROXMOX_TOKEN_SECRET": self.token_secret,
        }.items() if not value]
        if missing:
            raise ConfigError(f"Missing environment variables: {', '.join(missing)}")
        url = urllib.parse.urlsplit(self.base_url)
        if (url.scheme != "https" or not url.hostname or url.username or url.password
                or url.path or url.query or url.fragment):
            raise ConfigError("PROXMOX_BASE_URL must be an HTTPS origin, e.g. https://pve.example.com:8006")
        if os.environ.get("PROXMOX_VERIFY_TLS", "true").lower() in {"0", "false", "no", "off"}:
            raise ConfigError("TLS verification is required; use PROXMOX_CA_FILE for a private CA")
        try:
            self.timeout = float(os.environ.get("PROXMOX_TIMEOUT", "15"))
        except ValueError as exc:
            raise ConfigError("PROXMOX_TIMEOUT must be a positive finite number") from exc
        if not math.isfinite(self.timeout) or self.timeout <= 0:
            raise ConfigError("PROXMOX_TIMEOUT must be a positive finite number")
        self.ssl_context = ssl.create_default_context(cafile=os.environ.get("PROXMOX_CA_FILE") or None)
        self.opener = urllib.request.build_opener(
            NoRedirect(), urllib.request.HTTPSHandler(context=self.ssl_context)
        )

    def _request(self, method: str, path: str, data: dict[str, Any] | None = None) -> Any:
        if method != "GET" and not writes_enabled():
            raise PermissionError("Writes are disabled; set PROXMOX_ENABLE_WRITES=true and restart the client")
        query = ""
        encoded = None
        if method == "GET" and data:
            query = "?" + urllib.parse.urlencode(data)
        elif method != "GET":
            encoded = urllib.parse.urlencode(data or {}).encode("utf-8")
        request = urllib.request.Request(
            f"{self.base_url}/api2/json{path}{query}", data=encoded, method=method,
            headers={
                "Authorization": f"PVEAPIToken={self.token_id}={self.token_secret}",
                "Accept": "application/json",
                **({"Content-Type": "application/x-www-form-urlencoded"} if encoded is not None else {}),
            },
        )
        try:
            with self.opener.open(request, timeout=self.timeout) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            # Do not forward arbitrary error bodies, URLs, or credentials to a client.
            raise RuntimeError(f"Proxmox HTTP {exc.code}; check permissions and server logs") from exc
        except (urllib.error.URLError, TimeoutError) as exc:
            raise RuntimeError("Could not reach Proxmox; check connectivity and certificate trust") from exc
        except (ValueError, UnicodeDecodeError) as exc:
            raise RuntimeError("Proxmox returned invalid JSON") from exc
        if not isinstance(payload, dict) or "data" not in payload:
            raise RuntimeError("Proxmox response is missing its data envelope")
        return payload["data"]

    def get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        return self._request("GET", path, params)

    def post(self, path: str, data: dict[str, Any] | None = None) -> Any:
        return self._request("POST", path, data)

    def put(self, path: str, data: dict[str, Any] | None = None) -> Any:
        return self._request("PUT", path, data)


def text_result(data: Any) -> dict[str, Any]:
    return {
        "content": [
            {"type": "text", "text": json.dumps(data, indent=2, sort_keys=True)}
        ]
    }


def all_tools() -> list[dict[str, Any]]:
    empty = {"type": "object", "properties": {}, "additionalProperties": False}
    return [
        {
            "name": "proxmox_version",
            "description": "Read the Proxmox VE version visible to the token.",
            "inputSchema": empty,
            "annotations": {"readOnlyHint": True},
        },
        {
            "name": "proxmox_list_nodes",
            "description": "List cluster nodes and basic node status.",
            "inputSchema": empty,
            "annotations": {"readOnlyHint": True},
        },
        {
            "name": "proxmox_list_guests",
            "description": "List QEMU VMs and LXC containers across the cluster.",
            "inputSchema": empty,
            "annotations": {"readOnlyHint": True},
        },
        {
            "name": "proxmox_list_storage",
            "description": "List configured Proxmox VE storage entries.",
            "inputSchema": empty,
            "annotations": {"readOnlyHint": True},
        },
        {
            "name": "proxmox_recent_tasks",
            "description": "List recent cluster tasks visible to the token.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "limit": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 100,
                        "default": 25,
                    }
                },
                "additionalProperties": False,
            },
            "annotations": {"readOnlyHint": True},
        },
        {
            "name": "proxmox_get_task_log",
            "description": "Read the log for a Proxmox task UPID.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "node": {"type": "string"},
                    "upid": {"type": "string"},
                    "limit": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 500,
                        "default": 100,
                    },
                },
                "required": ["node", "upid"],
                "additionalProperties": False,
            },
            "annotations": {"readOnlyHint": True},
        },
        {
            "name": "proxmox_list_backup_jobs",
            "description": "List configured Proxmox backup jobs.",
            "inputSchema": empty,
            "annotations": {"readOnlyHint": True},
        },
        {
            "name": "proxmox_update_storage",
            "description": "Update selected storage settings such as content types and backup pruning.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "storage": {"type": "string"},
                    "content": {"type": "string"},
                    "prune_backups": {"type": "string"},
                    "digest": {"type": "string"},
                },
                "required": ["storage"],
                "additionalProperties": False,
            },
            "annotations": {"readOnlyHint": False},
        },
        {
            "name": "proxmox_create_backup_job",
            "description": "Create a scheduled Proxmox vzdump backup job.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "storage": {"type": "string"},
                    "schedule": {"type": "string"},
                    "vmid": {"type": "string"},
                    "mode": {"type": "string", "enum": ["snapshot", "suspend", "stop"]},
                    "compress": {"type": "string", "enum": ["0", "gzip", "lzo", "zstd"]},
                    "prune_backups": {"type": "string"},
                    "enabled": {"type": "boolean"},
                    "comment": {"type": "string"},
                },
                "required": ["id", "storage", "schedule", "vmid"],
                "additionalProperties": False,
            },
            "annotations": {"readOnlyHint": False},
        },
        {
            "name": "proxmox_get_node_apt_repositories",
            "description": "Read APT repository configuration and warnings for one Proxmox node.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "node": {"type": "string"},
                },
                "required": ["node"],
                "additionalProperties": False,
            },
            "annotations": {"readOnlyHint": True},
        },
        {
            "name": "proxmox_run_node_apt_update",
            "description": "Run apt-get update on one Proxmox node and return the task id.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "node": {"type": "string"},
                },
                "required": ["node"],
                "additionalProperties": False,
            },
            "annotations": {"readOnlyHint": False},
        },
        {
            "name": "proxmox_add_standard_apt_repository",
            "description": "Add a standard Proxmox APT repository by handle to one node.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "node": {"type": "string"},
                    "handle": {
                        "type": "string",
                        "enum": [
                            "enterprise",
                            "no-subscription",
                            "test",
                            "ceph-squid-enterprise",
                            "ceph-squid-no-subscription",
                            "ceph-squid-test",
                        ],
                    },
                    "digest": {"type": "string"},
                },
                "required": ["node", "handle"],
                "additionalProperties": False,
            },
            "annotations": {"readOnlyHint": False},
        },
        {
            "name": "proxmox_set_apt_repository_enabled",
            "description": "Enable or disable an existing APT repository entry by file path and index.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "node": {"type": "string"},
                    "path": {"type": "string"},
                    "index": {"type": "integer", "minimum": 0},
                    "enabled": {"type": "boolean"},
                    "digest": {"type": "string"},
                },
                "required": ["node", "path", "index", "enabled"],
                "additionalProperties": False,
            },
            "annotations": {"readOnlyHint": False},
        },
        {
            "name": "proxmox_list_snapshots",
            "description": "List snapshots for one QEMU VM or LXC container.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "node": {"type": "string"},
                    "guest_type": {"type": "string", "enum": ["qemu", "lxc"]},
                    "vmid": {"type": "integer", "minimum": 1},
                },
                "required": ["node", "guest_type", "vmid"],
                "additionalProperties": False,
            },
            "annotations": {"readOnlyHint": True},
        },
        {
            "name": "proxmox_get_guest_status",
            "description": "Read current runtime status for one QEMU VM or LXC container.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "node": {"type": "string"},
                    "guest_type": {"type": "string", "enum": ["qemu", "lxc"]},
                    "vmid": {"type": "integer", "minimum": 1},
                },
                "required": ["node", "guest_type", "vmid"],
                "additionalProperties": False,
            },
            "annotations": {"readOnlyHint": True},
        },
        {
            "name": "proxmox_guest_power",
            "description": "Start, shutdown, or reboot one QEMU VM or LXC container.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "node": {"type": "string"},
                    "guest_type": {"type": "string", "enum": ["qemu", "lxc"]},
                    "vmid": {"type": "integer", "minimum": 1},
                    "action": {"type": "string", "enum": ["start", "shutdown", "reboot"]},
                },
                "required": ["node", "guest_type", "vmid", "action"],
                "additionalProperties": False,
            },
            "annotations": {"readOnlyHint": False},
        },
        {
            "name": "proxmox_create_snapshot",
            "description": "Create a snapshot for one QEMU VM or LXC container.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "node": {"type": "string"},
                    "guest_type": {"type": "string", "enum": ["qemu", "lxc"]},
                    "vmid": {"type": "integer", "minimum": 1},
                    "snapname": {
                        "type": "string",
                        "description": "Optional snapshot name. Defaults to codex-YYYYMMDD-HHMMSS.",
                    },
                    "description": {
                        "type": "string",
                        "description": "Optional snapshot description.",
                    },
                    "include_vm_state": {
                        "type": "boolean",
                        "description": "For QEMU guests, include running memory state.",
                        "default": False,
                    },
                },
                "required": ["node", "guest_type", "vmid"],
                "additionalProperties": False,
            },
            "annotations": {"readOnlyHint": False},
        },
    ]


def tools() -> list[dict[str, Any]]:
    return [tool for tool in all_tools()
            if tool["annotations"]["readOnlyHint"] or writes_enabled()]


def validate_arguments(name: str, arguments: Any) -> dict[str, Any]:
    catalog = {tool["name"]: tool for tool in all_tools()}
    if not isinstance(name, str) or name not in catalog:
        raise ValueError("Unknown tool")
    tool = catalog[name]
    if not tool["annotations"]["readOnlyHint"] and not writes_enabled():
        raise PermissionError("Writes are disabled; set PROXMOX_ENABLE_WRITES=true and restart the client")
    arguments = {} if arguments is None else arguments
    if not isinstance(arguments, dict):
        raise ValueError("arguments must be an object")
    schema = tool["inputSchema"]
    props = schema["properties"]
    if set(arguments) - set(props):
        raise ValueError("Unexpected argument")
    for key in schema.get("required", []):
        if key not in arguments:
            raise ValueError(f"{key} is required")
    for key, value in arguments.items():
        spec = props[key]
        expected = {"string": str, "integer": int, "boolean": bool}[spec["type"]]
        if type(value) is not expected:
            raise ValueError(f"{key} must be {spec['type']}")
        if expected is str and not value.strip():
            raise ValueError(f"{key} must not be blank")
        if "enum" in spec and value not in spec["enum"]:
            raise ValueError(f"{key} has an unsupported value")
        if "minimum" in spec and value < spec["minimum"]:
            raise ValueError(f"{key} is below the minimum")
        if "maximum" in spec and value > spec["maximum"]:
            raise ValueError(f"{key} is above the maximum")
        if key in {"node", "storage", "snapname"} and not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", value):
            raise ValueError(f"{key} must be a simple identifier")
    return arguments


def require_guest_args(arguments: dict[str, Any]) -> tuple[str, str, int]:
    node = str(arguments.get("node", "")).strip()
    guest_type = str(arguments.get("guest_type", "")).strip()
    vmid = int(arguments.get("vmid", 0))

    if not node:
        raise ValueError("node is required")
    if guest_type not in {"qemu", "lxc"}:
        raise ValueError("guest_type must be qemu or lxc")
    if vmid < 1:
        raise ValueError("vmid must be a positive integer")

    return node, guest_type, vmid


def list_all_guests(client: ProxmoxClient) -> dict[str, Any]:
    cluster_resources = client.get("/cluster/resources", {"type": "vm"}) or []
    by_node: list[dict[str, Any]] = []

    for node in client.get("/nodes") or []:
        node_name = node.get("node")
        if not node_name:
            continue
        for guest_type in ("qemu", "lxc"):
            try:
                guests = client.get(f"/nodes/{node_name}/{guest_type}") or []
            except RuntimeError as exc:
                by_node.append(
                    {
                        "node": node_name,
                        "guest_type": guest_type,
                        "error": str(exc),
                    }
                )
                continue

            for guest in guests:
                guest["node"] = node_name
                guest["guest_type"] = guest_type
                by_node.append(guest)

    return {"cluster_resources": cluster_resources, "by_node": by_node}


def list_all_storage(client: ProxmoxClient) -> dict[str, Any]:
    datacenter_storage = client.get("/storage") or []
    by_node: list[dict[str, Any]] = []

    for node in client.get("/nodes") or []:
        node_name = node.get("node")
        if not node_name:
            continue
        try:
            storage_entries = client.get(f"/nodes/{node_name}/storage") or []
        except RuntimeError as exc:
            by_node.append({"node": node_name, "error": str(exc)})
            continue

        for storage in storage_entries:
            storage["node"] = node_name
            by_node.append(storage)

    return {"datacenter_storage": datacenter_storage, "by_node": by_node}


def call_tool(name: str, arguments: dict[str, Any] | None) -> dict[str, Any]:
    arguments = validate_arguments(name, arguments)
    client = ProxmoxClient()

    if name == "proxmox_version":
        return text_result(client.get("/version"))
    if name == "proxmox_list_nodes":
        return text_result(client.get("/nodes"))
    if name == "proxmox_list_guests":
        return text_result(list_all_guests(client))
    if name == "proxmox_list_storage":
        return text_result(list_all_storage(client))
    if name == "proxmox_recent_tasks":
        limit = max(1, min(int(arguments.get("limit", 25)), 100))
        tasks = client.get("/cluster/tasks") or []
        return text_result(tasks[:limit])
    if name == "proxmox_get_task_log":
        node = str(arguments.get("node", "")).strip()
        upid = str(arguments.get("upid", "")).strip()
        limit = max(1, min(int(arguments.get("limit", 100)), 500))
        if not node:
            raise ValueError("node is required")
        if not upid:
            raise ValueError("upid is required")
        log = client.get(
            f"/nodes/{node}/tasks/{urllib.parse.quote(upid, safe='')}/log"
        ) or []
        return text_result(log[:limit])
    if name == "proxmox_list_backup_jobs":
        return text_result(client.get("/cluster/backup") or [])
    if name == "proxmox_update_storage":
        storage = str(arguments.get("storage", "")).strip()
        if not storage:
            raise ValueError("storage is required")
        payload: dict[str, Any] = {}
        if arguments.get("content"):
            payload["content"] = str(arguments["content"])
        if arguments.get("prune_backups"):
            payload["prune-backups"] = str(arguments["prune_backups"])
        if arguments.get("digest"):
            payload["digest"] = str(arguments["digest"])
        if not payload:
            raise ValueError("At least one storage setting must be provided")
        result = client.put(f"/storage/{storage}", payload)
        return text_result({"result": result, "storage": storage, **payload})
    if name == "proxmox_create_backup_job":
        job_id = str(arguments.get("id", "")).strip()
        storage = str(arguments.get("storage", "")).strip()
        schedule = str(arguments.get("schedule", "")).strip()
        vmid = str(arguments.get("vmid", "")).strip()
        if not job_id:
            raise ValueError("id is required")
        if not storage:
            raise ValueError("storage is required")
        if not schedule:
            raise ValueError("schedule is required")
        if not vmid:
            raise ValueError("vmid is required")
        payload = {
            "id": job_id,
            "storage": storage,
            "schedule": schedule,
            "vmid": vmid,
            "mode": str(arguments.get("mode") or "snapshot"),
            "compress": str(arguments.get("compress") or "zstd"),
            "enabled": 1 if bool(arguments.get("enabled", True)) else 0,
        }
        if arguments.get("prune_backups"):
            payload["prune-backups"] = str(arguments["prune_backups"])
        if arguments.get("comment"):
            payload["comment"] = str(arguments["comment"])
        result = client.post("/cluster/backup", payload)
        return text_result({"result": result, **payload})
    if name == "proxmox_get_node_apt_repositories":
        node = str(arguments.get("node", "")).strip()
        if not node:
            raise ValueError("node is required")
        return text_result(client.get(f"/nodes/{node}/apt/repositories") or {})
    if name == "proxmox_run_node_apt_update":
        node = str(arguments.get("node", "")).strip()
        if not node:
            raise ValueError("node is required")
        upid = client.post(f"/nodes/{node}/apt/update")
        return text_result({"task": upid, "node": node, "action": "apt-update"})
    if name == "proxmox_add_standard_apt_repository":
        node = str(arguments.get("node", "")).strip()
        handle = str(arguments.get("handle", "")).strip()
        if not node:
            raise ValueError("node is required")
        if not handle:
            raise ValueError("handle is required")
        payload = {"handle": handle}
        if arguments.get("digest"):
            payload["digest"] = str(arguments["digest"])
        result = client.put(f"/nodes/{node}/apt/repositories", payload)
        return text_result({"result": result, "node": node, "handle": handle})
    if name == "proxmox_set_apt_repository_enabled":
        node = str(arguments.get("node", "")).strip()
        path_value = str(arguments.get("path", "")).strip()
        index = int(arguments.get("index", -1))
        enabled = bool(arguments.get("enabled", False))
        if not node:
            raise ValueError("node is required")
        if not path_value:
            raise ValueError("path is required")
        if index < 0:
            raise ValueError("index must be zero or greater")
        payload = {"path": path_value, "index": index, "enabled": int(enabled)}
        if arguments.get("digest"):
            payload["digest"] = str(arguments["digest"])
        result = client.post(f"/nodes/{node}/apt/repositories", payload)
        return text_result(
            {
                "result": result,
                "node": node,
                "path": path_value,
                "index": index,
                "enabled": enabled,
            }
        )
    if name == "proxmox_list_snapshots":
        node, guest_type, vmid = require_guest_args(arguments)
        return text_result(client.get(f"/nodes/{node}/{guest_type}/{vmid}/snapshot") or [])
    if name == "proxmox_get_guest_status":
        node, guest_type, vmid = require_guest_args(arguments)
        return text_result(client.get(f"/nodes/{node}/{guest_type}/{vmid}/status/current"))
    if name == "proxmox_guest_power":
        node, guest_type, vmid = require_guest_args(arguments)
        action = str(arguments.get("action", "")).strip()
        if action not in {"start", "shutdown", "reboot"}:
            raise ValueError("action must be start, shutdown, or reboot")
        upid = client.post(f"/nodes/{node}/{guest_type}/{vmid}/status/{action}")
        return text_result({"task": upid, "node": node, "guest_type": guest_type, "vmid": vmid, "action": action})
    if name == "proxmox_create_snapshot":
        node, guest_type, vmid = require_guest_args(arguments)
        snapname = str(arguments.get("snapname") or "").strip()
        if not snapname:
            snapname = time.strftime("codex-%Y%m%d-%H%M%S")
        payload = {
            "snapname": snapname,
            "description": str(arguments.get("description") or "Created by Codex MCP"),
        }
        if guest_type == "qemu" and bool(arguments.get("include_vm_state", False)):
            payload["vmstate"] = 1
        upid = client.post(f"/nodes/{node}/{guest_type}/{vmid}/snapshot", payload)
        return text_result({"task": upid, "node": node, "guest_type": guest_type, "vmid": vmid, "snapname": snapname})

    raise ValueError(f"Unknown tool: {name}")


def rpc_error(request_id: Any, code: int, message: str) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}}


def handle_request(request: Any) -> dict[str, Any] | None:
    if (not isinstance(request, dict) or request.get("jsonrpc") != "2.0"
            or not isinstance(request.get("method"), str)):
        return rpc_error(None, -32600, "Invalid request")
    if "id" not in request:
        return None  # Notifications do not receive replies.
    request_id = request["id"]
    if type(request_id) not in (str, int):
        return rpc_error(None, -32600, "Request id must be a string or integer")
    method = request["method"]
    params = request.get("params", {})
    if not isinstance(params, dict):
        return rpc_error(request_id, -32602, "params must be an object")
    if method == "initialize":
        requested = params.get("protocolVersion")
        result = {
            "protocolVersion": requested if requested in SUPPORTED_PROTOCOLS else SUPPORTED_PROTOCOLS[-1],
            "capabilities": {"tools": {}},
            "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
        }
    elif method == "ping":
        result = {}
    elif method == "tools/list":
        result = {"tools": tools()}
    elif method == "tools/call":
        try:
            result = call_tool(params.get("name", ""), params.get("arguments"))
        except ValueError as exc:
            return rpc_error(request_id, -32602, str(exc))
        except (RuntimeError, PermissionError) as exc:
            result = text_result({"error": str(exc)})
            result["isError"] = True
        except Exception:
            result = text_result({"error": "Unexpected server error; inspect the server locally"})
            result["isError"] = True
    else:
        return rpc_error(request_id, -32601, "Method not found")
    return {"jsonrpc": "2.0", "id": request_id, "result": result}


def run_stdio() -> None:
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            response = handle_request(json.loads(line))
        except Exception as exc:
            response = {
                "jsonrpc": "2.0",
                "id": None,
                "error": {"code": -32700, "message": "Invalid JSON"},
            }
        if response is not None:
            sys.stdout.write(json.dumps(response, separators=(",", ":")) + "\n")
            sys.stdout.flush()


def run_smoke_test() -> None:
    client = ProxmoxClient()
    payload = {
        "version": client.get("/version"),
        "nodes": client.get("/nodes"),
        "guests": list_all_guests(client),
    }
    print(json.dumps(payload, indent=2, sort_keys=True))


def main() -> int:
    parser = argparse.ArgumentParser(description="Proxmox MCP helper")
    parser.add_argument("--smoke-test", action="store_true")
    args = parser.parse_args()

    if args.smoke_test:
        try:
            run_smoke_test()
        except Exception:
            print("Smoke test failed; check configuration, permissions, connectivity, and certificate trust", file=sys.stderr)
            return 1
    else:
        run_stdio()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
