# Permissions and security decisions

## Trust boundary

An MCP client can ask this process to call Proxmox. The local environment supplies the credentials; the model must not supply a token in tool arguments. API output may contain infrastructure information and untrusted text, so review client/tool output before sharing it or following instructions contained in logs.

## Read-only default

The default catalog contains read tools only. `PROXMOX_ENABLE_WRITES=true` is an explicit local opt-in; tool dispatch and the HTTP transport both check it. This is a guardrail, not a replacement for server-side authorization. A process that controls the local environment or source code can bypass local guards.

Use a dedicated service user/token with privilege separation. Proxmox evaluates the token within the user's permissions; both need appropriate ACLs. `PVEAuditor` is a built-in read-oriented role, but the required scope and privileges must be checked against the exact endpoints and installed release. Do not solve a 403 by giving the adapter unrestricted administrator access.

Write operations have different permissions and operational impact. Check the Proxmox API viewer for each endpoint and scope them to the intended resources. There is no universal safe write role documented by this prototype. Enable only in a lab after reviewing the intended action in the MCP client.

## Transport

- HTTPS origins only; credentials in URLs and URL paths/query strings are rejected.
- TLS certificate verification remains enabled. Private CA support uses `PROXMOX_CA_FILE`.
- HTTP redirects are refused to avoid forwarding the token to another location.
- API credentials are sent in the Authorization header, never in query strings.
- Requests use a positive finite timeout, default 15 seconds.
- HTTP errors report a status, not raw server response bodies. Normal successful results still contain real infrastructure metadata.

The configured origin is trusted administrator input. This server is not intended to accept arbitrary destination URLs from remote users.

## Secret handling

`env.local.ps1`, local dotenv files, keys, and certificates are ignored by Git. Example files contain placeholders only. Git ignore rules do not remove secrets already committed; review staged files and never copy private configuration into an issue or demo.

The public copy does not load or modify the existing private helper's local configuration. It has no live credentials and was tested offline.

## References

- [Proxmox user and API-token permissions](https://pve.proxmox.com/pve-docs/pve-admin-guide.html#pveum_tokens)
- [Proxmox API viewer — endpoint permissions](https://pve.proxmox.com/pve-docs/api-viewer/)
- [MCP 2025-06-18 tool definitions and errors](https://modelcontextprotocol.io/specification/2025-06-18/server/tools)
- [MCP 2025-06-18 stdio transport](https://modelcontextprotocol.io/specification/2025-06-18/basic/transports)
