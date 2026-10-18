# Permissions and security

## Authentication

The adapter reads its Proxmox URL and API token from environment variables. Tools receive resource identifiers and operation arguments; credentials stay in the server process configuration.

Create a dedicated service user and token with privilege separation. Proxmox limits the token to permissions held by both the user and token, so both need suitable ACLs at the intended resource scope.

`PVEAuditor` is a built-in read-oriented role and a starting point for inspection tools. Check each endpoint’s permissions against your installed Proxmox release. When a request returns 403, review the user ACL, token ACL, resource scope, and endpoint requirements before changing permissions.

## Enabling administrative actions

`PROXMOX_ENABLE_WRITES` defaults to false. With that default:

- Tool discovery returns the ten read tools.
- Direct calls to administrative tools are rejected before client construction.
- The HTTP client rejects POST and PUT requests.

Set `PROXMOX_ENABLE_WRITES=true` and restart the MCP client to expose the seven administrative tools. Scope the token to the resources and operations you need. The flag enables the write catalog as a group; it does not provide per-tool approval or replace Proxmox authorization.

Review power, snapshot, backup, storage, and APT changes in the MCP client before running them. The server is designed for a local stdio connection, not an unauthenticated network service.

## HTTPS and request handling

| Control | Behavior |
| --- | --- |
| Destination URL | HTTPS origin required; URL credentials, paths, queries, and fragments rejected |
| Certificate trust | TLS verification enabled; `PROXMOX_CA_FILE` supports a private CA bundle |
| Redirects | Refused to keep the API token from being forwarded elsewhere |
| Token transport | Authorization header |
| Timeout | Positive finite value; default 15 seconds |
| HTTP errors | Status returned without forwarding raw server error bodies |

The origin is trusted local configuration. Successful API results can include hostnames, addresses, task logs, and other infrastructure details. Review that output before publishing it, and treat text from services or logs as data rather than instructions.

## Local configuration

Keep credentials in your local environment or `env.local.ps1`. Git ignores local dotenv files, key files, and certificates. The committed example files use placeholders.

Ignore rules only affect untracked files; they do not remove a credential from existing history. Review staged configuration before committing.

## References

- [Proxmox user and API-token permissions](https://pve.proxmox.com/pve-docs/pve-admin-guide.html#pveum_tokens)
- [Proxmox API viewer](https://pve.proxmox.com/pve-docs/api-viewer/)
- [MCP 2025-06-18 tools](https://modelcontextprotocol.io/specification/2025-06-18/server/tools)
- [MCP 2025-06-18 stdio transport](https://modelcontextprotocol.io/specification/2025-06-18/basic/transports)
