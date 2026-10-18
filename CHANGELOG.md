# Changelog

## 0.2.0 — October 17, 2026

- Added a read-only default: write tools are hidden from discovery and blocked at tool dispatch and HTTP request handling.
- Added required-field, type, enum, range, and path-identifier validation.
- Consolidated HTTP requests with verified HTTPS, private CA support, timeouts, and redirect refusal.
- Added tool execution errors, JSON-RPC request checks, ping support, and protocol-version negotiation.
- Added an offline demo, 22 automated tests, and GitHub Actions checks on Python 3.10 and 3.12.
- Expanded setup instructions and documented the full backup, storage, and APT tool catalog.
- Renamed the server to `proxmox-mcp` to reflect its optional administrative tools.
