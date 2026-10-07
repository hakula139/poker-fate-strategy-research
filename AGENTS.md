# AGENTS.md: poker-fate-strategy-research

Follow the user's global instructions. Keep this file focused on constraints that are not apparent from the source or tooling.

## Research evidence

- Record the official source, retrieval time, package version, size, and SHA-256 before deriving findings from a client artifact.
- Keep APKs, decoded client sources, raw captures, account identifiers, and credentials in ignored `artifacts/`, `work/`, or `data/`. Commit analysis tools, provenance, and concise evidence references.
- Separate observations, hypotheses, and live-server results. State the limits of static evidence and keep source references beside each finding.
- Preserve message timing and recipient context when a finding depends on runtime data. Keep artifact-specific investigation methods with the corresponding research document.
- Use only user-authorized accounts and test actions. Follow the official authentication flow and let the user enter passwords and verification codes. Keep session material local. Do not automate gameplay on public tables.
- Discuss client instrumentation, new installation requirements, and changes to test scope with the user before proceeding. Static inspection of official artifacts is authorized.

## Development

Run `nix flake check` for repository hooks. When changing Python, run the locked checks declared in CI. Keep generated output local and reproducible from the recorded artifact.

Use topic branches and squash-merged PRs. Obtain approval for each PR before merging. Keep local plans under ignored `.agents/plans/`.
