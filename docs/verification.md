# Verification record

Date: October 17, 2026. Environment: Windows, Python 3.12.10.

| Check | Result |
| --- | --- |
| `python -m unittest discover -s tests -v` | 22 tests passed locally |
| `python examples/offline_demo.py` | Passed; fixture read succeeded and write was denied |
| Python compilation | Checked during packaging |
| Default catalog | 10 read tools |
| Optional write catalog | 7 tools; opt-in required |
| Hosted Linux CI | Passed on Python 3.10 and 3.12; [workflow run #1](https://github.com/noaht360/proxmox-mcp/actions/runs/39079821626) |

Tests deliberately replace or block the network transport. No live credentials,
Proxmox connections, or server mutations were used for this verification.
The hosted workflow also ran the offline demo and compilation on both Python
versions. Live testing of this public copy remains a separate validation task.

The demo transcript is [saved here](demo-output.txt). Its three node records are
synthetic. Historical real-lab operations are described in the companion lab
repository, with their evidence limits.
