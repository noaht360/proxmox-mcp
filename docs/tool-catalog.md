# Tool catalog

Generated from the public adapter source. The default catalog omits write tools.

| Tool | Mode | Required arguments | Purpose |
| --- | --- | --- | --- |
| `proxmox_version` | Read | None | Read the Proxmox VE version visible to the token. |
| `proxmox_list_nodes` | Read | None | List cluster nodes and basic node status. |
| `proxmox_list_guests` | Read | None | List QEMU VMs and LXC containers across the cluster. |
| `proxmox_list_storage` | Read | None | List configured Proxmox VE storage entries. |
| `proxmox_recent_tasks` | Read | None | List recent cluster tasks visible to the token. |
| `proxmox_get_task_log` | Read | `node`, `upid` | Read the log for a Proxmox task UPID. |
| `proxmox_list_backup_jobs` | Read | None | List configured Proxmox backup jobs. |
| `proxmox_update_storage` | Write: opt-in | `storage` | Update selected storage settings such as content types and backup pruning. |
| `proxmox_create_backup_job` | Write: opt-in | `id`, `storage`, `schedule`, `vmid` | Create a scheduled Proxmox vzdump backup job. |
| `proxmox_get_node_apt_repositories` | Read | `node` | Read APT repository configuration and warnings for one Proxmox node. |
| `proxmox_run_node_apt_update` | Write: opt-in | `node` | Run apt-get update on one Proxmox node and return the task id. |
| `proxmox_add_standard_apt_repository` | Write: opt-in | `node`, `handle` | Add a standard Proxmox APT repository by handle to one node. |
| `proxmox_set_apt_repository_enabled` | Write: opt-in | `node`, `path`, `index`, `enabled` | Enable or disable an existing APT repository entry by file path and index. |
| `proxmox_list_snapshots` | Read | `node`, `guest_type`, `vmid` | List snapshots for one QEMU VM or LXC container. |
| `proxmox_get_guest_status` | Read | `node`, `guest_type`, `vmid` | Read current runtime status for one QEMU VM or LXC container. |
| `proxmox_guest_power` | Write: opt-in | `node`, `guest_type`, `vmid`, `action` | Start, shutdown, or reboot one QEMU VM or LXC container. |
| `proxmox_create_snapshot` | Write: opt-in | `node`, `guest_type`, `vmid` | Create a snapshot for one QEMU VM or LXC container. |

## Operational behavior

- Power, snapshot, and package-index operations can return a task identifier. Inspect its task log separately; the adapter does not wait for completion.
- Snapshot support depends on guest configuration and storage capabilities.
- The APT operation refreshes indexes; it does not upgrade packages.
- No delete, shell, firewall, or host-network tool is exposed.
- No automatic retries are performed, especially for mutations where a timeout may leave the outcome unknown.
