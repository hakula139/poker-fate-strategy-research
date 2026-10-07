# AGENTS.md: poker-fate-strategy-research

Follow the user's global instructions. Keep this file focused on constraints that are not apparent from the source or tooling.

## Research evidence

- Record the official source, retrieval time, package version, size, and SHA-256 before deriving findings from a client artifact.
- Keep APKs, decoded client sources, raw captures, account identifiers, and credentials in ignored `artifacts/`, `work/`, or `data/`. Commit analysis tools, provenance, and concise evidence references.
- Separate observed client behavior, hypotheses, and live-server results. A schema field or a UI hiding a card does not establish that the server sends that card before disclosure.
- Trace card data from transport decoding through model updates to rendering, including reconnect, spectating, all-in, and replay paths. Preserve message timing and recipient context in any runtime evidence.
- Use only user-authorized accounts and test actions. Follow the official authentication flow and let the user enter passwords and verification codes. Keep session material local. Do not automate gameplay on public tables.
- Discuss client instrumentation, new installation requirements, and changes to test scope with the user before proceeding. Static inspection of official artifacts is authorized.

## Development

Run `nix flake check` for repository hooks. When changing Python, run the locked checks declared in CI. Keep generated output local and reproducible from the recorded artifact.

Use topic branches and squash-merged PRs. Obtain approval for each PR before merging. Keep local plans under ignored `.agents/plans/`.
