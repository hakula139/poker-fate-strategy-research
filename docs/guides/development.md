# Development

Enter the pinned development environment before running repository tools:

```bash
nix develop
```

`direnv` loads the same environment through `.envrc`. The flake provides Android resource decoding, Java decompilation, Python tooling, documentation checks, and spelling checks.

Run the repository checks before publishing a change:

```bash
nix flake check --print-build-logs
```

The development shell installs the same checks as Git hooks. CI runs them for pull requests, including requests based on another feature branch.

Keep downloaded clients and generated analysis output in ignored `artifacts/`, `work/`, or `data/`. Store provenance and reproducible methods with the documentation that uses them.
