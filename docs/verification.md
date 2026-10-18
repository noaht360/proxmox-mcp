# Testing and compatibility

## Run the checks

From the repository root:

```console
python -m unittest discover -s tests -v
python examples/offline_demo.py
python -m compileall -q proxmox_mcp_server.py examples tests
```

The tests use Python’s built-in `unittest` library. Network calls are replaced or blocked, so these commands need neither a Proxmox server nor credentials.

## Test coverage

| Area | Checks |
| --- | --- |
| Write restrictions | Read-only catalog, dispatch rejection, HTTP write rejection, and explicit opt-in |
| Input validation | Required fields, unexpected arguments, types, bounds, enums, and path identifiers |
| Configuration | Missing settings, HTTPS origin, timeouts, certificate trust, and redirect refusal |
| HTTP requests | Authorization header, query parameters, form encoding, response parsing, and error sanitization |
| Tool behavior | Power and snapshot payloads, backup/storage fields, task-ID encoding, and partial node failures |
| Protocol | Request envelopes, protocol negotiation, notifications, ping, and recovery after invalid JSON |

## Results

On October 17, 2026, all **22 tests passed** locally on Windows with Python 3.12.10. The offline demo and compilation checks also passed.

[GitHub Actions run #1](https://github.com/noaht360/proxmox-mcp/actions/runs/39079821626) passed the tests, demo, and compilation on Linux with Python 3.10 and 3.12. The [workflow page](https://github.com/noaht360/proxmox-mcp/actions/workflows/checks.yml) shows subsequent runs.

## Offline demo

The [demo](../examples/offline_demo.py) runs the adapter’s request handling against fixture HTTP responses. It initializes the protocol, discovers read tools, reads three synthetic nodes, and confirms that a shutdown request is rejected with writes disabled. The [sample output](demo-output.txt) shows the complete exchange.

## Live compatibility

These checks exercise adapter behavior without a live server. Testing this version against a Proxmox installation remains pending. Use `--smoke-test` for an initial read of your configured server; test administrative tools separately in a controlled lab.
