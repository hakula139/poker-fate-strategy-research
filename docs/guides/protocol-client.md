# Protocol client

<!-- cspell:ignore awsb -->

The protocol client reuses a session established by an official client and records decoded WebSocket messages. Human interaction completes authentication, verification challenges and official warnings. The `observe` command connects without requesting room entry. The `practice` command requests one server Hold'em training entry and records subsequent messages. It does not send poker decisions, room-exit requests or display-completion acknowledgments.

## Prepare the local schema

Enter `nix develop`, run `uv sync --locked`, and [extract the recorded APK](analyze-apk.md). Compile its eight protobuf sources into a local descriptor set:

```bash
uv run --no-sync poker-fate-strategy schema \
  work/android-1.7.0/sources/gameres_assets_proto_ed9afd34d986ed09f20d6f3133ed9092/Assets/GameRes/Proto \
  --output work/android-1.7.0.pb
```

Use the source directory from the extraction inventory if its location differs. The descriptor set remains local and its SHA-256 is included in each recording. Optional protobuf fields remain absent when their bytes were absent. Unknown message types and malformed payloads receive explicit status labels. A known message with fields outside the loaded schema sets `unknown_fields` to `true`, so a schema mismatch remains visible.

## Capture an official login

The flake provides `mitmdump` and a response-capture addon. Start it with a fresh output path and the native channel of the official client being used:

```bash
PYTHONPATH="$PWD/src" mitmdump -q \
  --listen-host 127.0.0.1 --listen-port 8080 \
  --set flow_detail=0 \
  --set confdir="$PWD/work/login-proxy" \
  --set session_output="$PWD/work/session.json" \
  --set client_channel=3 \
  -s src/poker_fate_strategy_research/login_proxy.py
```

Channel `3` is verified for the recorded Android 1.7.0 APK. Use the authenticating client's own native channel for another distribution. The addon reads its version from the HTTP `Version` header. Desktop compatibility and distribution values require verification against that desktop artifact.

Configure the official client environment to use this proxy, then install its generated certificate in that environment as described in the [mitmproxy certificate guide](https://docs.mitmproxy.org/stable/concepts/certificates/). With a Windows virtual machine and a proxy running on its host, the guest needs a reachable host address and a listener bound to that address. Determine that address and agree on the listener configuration before changing network settings. The command above binds only to loopback.

The addon matches POST `/login` on `ga-foreign.poker-fate.com`. If the official client selects another recorded login host, set `--set login_host=awsb-entry.poker-fate.com` or its observed official host. Complete guest or email login in the official client. Handle any verification challenge there. Code `-6` carries the official risk warning and valid session fields. Complete that warning before reusing the captured session.

Only the first accepted matching response is reduced to the WebSocket session fields and written with mode `600`. The addon omits the HTTP authorization value and never saves the request or full response. Keep `-q` and `flow_detail=0`, and leave flow saving disabled. Stop the proxy after capture. Close the official client before the script connects, so both clients do not compete for the same session. Session takeover and shutdown behavior remain unverified on the live service.

If the client ignores the proxy or rejects its certificate, record the failure stage and pause that setup. Certificate pinning and alternate instrumentation require a separate decision based on the observed failure. The addon has been verified with a local synthetic HTTP server and the Nix-provided proxy runtime. It has not yet captured a live official-client login.

An official login response captured through another agreed local method can also be imported:

```bash
chmod 600 work/login-response.json
uv run --no-sync poker-fate-strategy import-session work/login-response.json \
  --version 1.7.0 --channel 3 --output work/session.json
```

The importer reads the root `uid`, `rdkey`, `login_ip`, and `server.server[0].server_host`. `--server-index` selects another returned endpoint. It accepts nonnegative HTTP codes and the official warning code `-6`, and requires the session fields. Keep the response and normalized session in ignored local storage. Share login status and failure stages in discussion without posting response contents or credentials.

## Observe messages

Start with a short connection:

```bash
uv run --no-sync poker-fate-strategy observe \
  --session work/session.json --schema work/android-1.7.0.pb \
  --output data/lobby-observation.jsonl --duration 60
```

The client sends `UserLoginREQ` and empty `HeartBeatREQ` messages every five seconds. Login code `1002` keeps the client queued and delays room requests until code `0`. `--login-timeout` bounds that wait, and `--duration` bounds the connected observation. Environment proxies are disabled for this connection. WSS certificate verification stays enabled, and unencrypted WS is permitted only on loopback for local tests. Connections are made once without automatic reconnect.

To request a snapshot for an already known room, add `--room-id`. This sends `GetRoomDataREQ` after login. Rejected or missing snapshots fail the operation. Pushed location messages are recorded without automatically issuing `EnterRoomREQ`.

## Enter training

Use an authorized guest account for the initial server training test:

```bash
uv run --no-sync poker-fate-strategy practice \
  --session work/session.json --schema work/android-1.7.0.pb \
  --buy-in 40 --output data/training-observation.jsonl --duration 120
```

This command changes live training state by requesting a seat with the selected training chips. The implemented request uses game type `40010101`, big blind `2`, currency ID `10100001`, and `wait_blind=true`. Buy-in must be an even integer from `40` to `400`, matching the inspected configuration. The server can reject those values or require additional initialization. Such a result needs investigation before adding requests.

`QuickStartRSP` acceptance alone does not establish room readiness. A successful `EnterRoomRSP` with a positive room ID and the expected training type records `room-ready`. An operation that ends before its requested room becomes ready fails. The server may time out a seated player who does not send decisions. Ending the recording closes its transport without explicitly leaving the room, so verify the account's room state afterward in the official client.

The source of these request fields is the [Android 1.7.0 artifact](../reference/artifacts/android-1.7.0.md): `EnumConfig.lua:56,165-168`, `tpl_table_poker_free.lua:8`, and `LobbyByinDialog.lua:44-56`. Guide mode installs a local receiver, while this command always uses the server transport.

## Interpret a recording

Each packet includes its sequence, direction, room ID, recipient context, UTC `observed_at`, and local `monotonic_ns`. Receive timestamps are taken after WebSocket message reassembly. Send timestamps are taken after the transport accepts the send. Multiple protocol packets in one WebSocket message share an observation timestamp and retain sequence order.

The recorder omits authentication payloads. UID fields become `self` or stable per-recording player aliases, and names in player records are removed. Known credential fields and the active session key are redacted. Non-authentication payload hashes identify local observations, while raw payload bytes are omitted. Unknown fields, free-form text and unrecognized identity formats still require review before sharing a recording. Captures stay in ignored local storage and are created with mode `600`. Existing output files are never overwritten.

For hidden-card analysis, correlate the recorded cards with round identity, seat context and the authoritative stage in the corresponding message stream. Reception establishes delivery to this connection. It does not by itself establish when a legitimate UI displayed the data, whether another account received it, or how a separate cheating client obtained it. Keep those claims distinct when deriving findings.
