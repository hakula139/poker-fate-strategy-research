# Development

## Enter the environment

The default shell provides the APK analysis tools, a .NET runtime for native metadata inspection, Python with uv, the protobuf compiler, and mitmproxy. `direnv` loads it through `.envrc`, and entering it installs the Git hooks:

```bash
nix develop
```

`nix develop .#python` provides only the Python tools, and `nix develop .#android` the Android SDK, emulator, and Frida.

## Check a change

Run the repository hooks and the tests:

```bash
nix develop -c run-hooks
uv run --locked pytest -q
```
