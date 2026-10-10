# Protocol client

<!-- cspell:ignore awsb -->

The protocol client reuses an official session and records WebSocket messages. `observe` connects without requesting room entry. `practice` requests a server Hold'em training seat. Poker decisions and room-exit requests require the official client. Live session reuse remains unverified.

## Prepare the local schema

Enter `nix develop`, run `uv sync --locked`, and [extract the recorded APK](analyze-apk.md). Compile its eight protobuf sources into a local descriptor set:

```bash
uv run --no-sync poker-fate-strategy schema \
  work/android-1.7.0/sources/gameres_assets_proto_ed9afd34d986ed09f20d6f3133ed9092/Assets/GameRes/Proto \
  --output work/android-1.7.0.pb
```

Use the source directory listed in the extraction inventory. Recordings include the descriptor set's SHA-256, preserve optional-field absence, and label unknown messages or malformed payloads. `unknown_fields=true` flags fields outside the loaded schema.

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

Configure the client to use the proxy and its generated certificate as described in the [mitmproxy certificate guide](https://docs.mitmproxy.org/stable/concepts/certificates/). The command binds to loopback. A VM guest requires a reachable host address and a listener configured for that address.

The addon matches POST `/login` on `ga-foreign.poker-fate.com`. If the official client selects another recorded login host, set `--set login_host=awsb-entry.poker-fate.com` or its observed official host. Complete guest or email login in the official client. Handle any verification challenge there. Code `-6` carries the official risk warning and valid session fields. Complete that warning before reusing the captured session.

The addon saves the first accepted matching response's session fields with mode `600`, omitting HTTP authorization and the full exchange. Keep `-q`, `flow_detail=0`, and flow saving disabled. Stop the proxy and close the official client before connecting the script to avoid competing sessions.

Live proxy capture remains unverified. A client that ignores the proxy or rejects its certificate requires a separate setup decision before further instrumentation.

An official login response captured through another agreed local method can also be imported:

```bash
chmod 600 work/login-response.json
uv run --no-sync poker-fate-strategy import-session work/login-response.json \
  --version 1.7.0 --channel 3 --output work/session.json
```

The importer requires `uid`, `rdkey`, `login_ip`, and `server.server[0].server_host`. `--server-index` selects another endpoint. Accepted codes are nonnegative or the official warning code `-6`.

## Observe messages

Start with a short connection:

```bash
uv run --no-sync poker-fate-strategy observe \
  --session work/session.json --schema work/android-1.7.0.pb \
  --output data/lobby-observation.jsonl --duration 60
```

The client sends `UserLoginREQ` and keeps the connection alive with `HeartBeatREQ`. Login code `1002` queues the client until code `0`. `--login-timeout` bounds login, and `--duration` bounds observation. WSS certificate verification is enabled, environment proxies are disabled, and unencrypted WS is restricted to loopback. The client connects once.

To request a snapshot for an already known room, add `--room-id`. This sends `GetRoomDataREQ` after login. Rejected or missing snapshots fail the operation. Pushed location messages are recorded without automatically issuing `EnterRoomREQ`.

## Enter training

Use an authorized guest account for the initial server training test:

```bash
uv run --no-sync poker-fate-strategy practice \
  --session work/session.json --schema work/android-1.7.0.pb \
  --buy-in 40 --output data/training-observation.jsonl --duration 120
```

This command requests a training seat with game type `40010101`, big blind `2`, currency ID `10100001`, and `wait_blind=true`. Buy-in must be an even integer from `40` to `60`, or a multiple of `20` from `80` to `400`, matching the inspected UI choices. Live training entry remains unverified.

A successful `EnterRoomRSP` with a positive room ID and the expected training type records `room-ready`. An operation that ends before room readiness fails. The server may remove an inactive player. Ending the recording closes the connection, so check the account's room state in the official client.

The source of these request fields is the [Android 1.7.0 artifact](../reference/artifacts/android-1.7.0.md): `EnumConfig.lua:56,165-168`, `tpl_table_poker_free.lua:8`, `tpl_constdata.lua:6`, and `LobbyByinDialog.lua:44-56`. Guide mode installs a local receiver, while this command always uses the server transport.

## Interpret a recording

Packets retain sequence, direction, room ID, and recipient context. All packets in a frame are recorded before lifecycle handling, including packets following a server rejection. Invalid frames retain their size and error category.

The recorder omits authentication payloads and raw bytes, replaces UIDs with per-recording aliases, and removes player names and known credentials. Files use mode `600`, and existing output is preserved. Unknown fields and free-form text require review before sharing.

Interpret cards alongside hand identity, recipient role, and betting stage. Reception establishes delivery to the recorded connection. Other recipients' access and UI reveal state require separate evidence.
