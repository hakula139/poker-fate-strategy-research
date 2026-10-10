# Development

Enter the pinned development environment before running repository tools:

```bash
nix develop
```

`direnv` loads the same environment through `.envrc`. The flake provides Android resource decoding, Java decompilation, a .NET runtime for native metadata inspection, Python tooling, documentation checks, and spelling checks.

Run the repository checks before publishing a change:

```bash
nix flake check --print-build-logs
```

The development shell installs the same checks as Git hooks. CI runs them for pull requests, including requests based on another feature branch.

Keep downloaded clients and generated analysis output in ignored `artifacts/`, `work/`, or `data/`. Store provenance and reproducible methods with the documentation that uses them.

Python dependencies are recorded in `uv.lock`. Use `nix develop .#python` for the Python tools without the APK research environment. Both shells provide the same Python runtime, uv, protobuf compiler and proxy. Install the locked environment and run the Python checks when changing analysis tools:

```bash
uv sync --locked
uv run --no-sync ruff check
uv run --no-sync ruff format --check
uv run --no-sync mypy
uv run --no-sync pytest -q
```

Outside either development shell, the proxy integration test skips when `mitmdump` is unavailable.
