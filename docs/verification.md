# Verification record

Date: October 17, 2026. Environment: Windows, Python 3.12.10.

| Check | Result |
| --- | --- |
| `python -m unittest discover -s tests -v` | 22 tests passed locally |
| `python examples/offline_demo.py` | Passed; fixture read succeeded and write was denied |
| Python compilation | Checked during packaging |
| Default catalog | 10 read tools |
| Optional write catalog | 7 tools; opt-in required |

Tests deliberately replace or block the network transport. No live credentials,
Proxmox connections, or server mutations were used for this verification.
CI is configured for Python 3.10 and 3.12; configuration alone is not a claim
that a hosted workflow has passed. Live testing of this public copy and testing
on Python 3.10 remain separate validation tasks.

The demo transcript is [saved here](demo-output.txt). Its three node records are
synthetic. Historical real-lab operations are described in the companion lab
repository, with their evidence limits.
