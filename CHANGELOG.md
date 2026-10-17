# Changes

## 0.2.0 — public portfolio preparation, October 17, 2026

Based on the existing Python helper, with its Proxmox endpoint mappings retained.

- Reconciled the README/catalog with the implemented backup, storage, and APT operations.
- Replaced the stale read-only server name with `proxmox-mcp`.
- Hid write tools by default and added dispatch/transport write gates.
- Added input checks for required fields, types, enums, bounds, and path identifiers.
- Centralized HTTP request logic; require verified HTTPS, support a private CA, and reject redirects.
- Added structured tool-execution errors, request-envelope checks, ping, and bounded protocol-version negotiation.
- Added a fixture-based demo, offline tests, CI configuration, and documented limitations.

The hardened public copy has not been exercised against the live lab. The original private helper and environment files were left unchanged.
