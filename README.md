# Poker Fate Strategy Research

A research workspace for Poker Fate strategy and game integrity. The first investigation examines whether an official client receives opponents' hole cards or future community cards before they should be visible.

The repository stores reproducible analysis tools and evidence-backed findings. Downloaded clients, decoded sources, captures, and account credentials remain in ignored local paths.

## Development

```bash
nix develop
nix flake check
```

`direnv` loads the same environment through `.envrc`. Android resource decoding, Java decompilation, Python tooling, documentation checks, and spelling checks are pinned by the project flake.
