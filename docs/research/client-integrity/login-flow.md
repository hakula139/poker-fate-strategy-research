# Official login flow

The decoded Android 1.7.0 client exposes an email-and-password login flow that waits for a native device-risk token before sending its login request. Static inspection identifies the client-side sequence, but does not establish a working script-only login for an existing account. No account login, verification-code delivery or password-recovery requests were made during this investigation.

The source belongs to the [Android 1.7.0 artifact](../../reference/artifacts/android-1.7.0.md). Its [machine-readable record](../../reference/artifacts/android-1.7.0.json) records the artifact hashes. Line references below refer to the decoded Lua files and the generated native method map for that artifact.

## Email login

`LoginLayer.lua:304-332` reads an email address and password, validates the email format and requires a nonempty password, then calls `LoginModel:emailLogin`. `EnumConfig.lua:386-395` assigns email login type `2`. This form requires an email address, so a player nickname alone cannot identify the login account.

`LoginModel.lua:93-123` prepares the email as `token` and the password as `verify`, alongside the platform, device identifier and language. It stores a pending login action, then asks `YiDunHelper` to prepare the risk report. `LoginModel.lua:38-43` adds language, attribution ID, push token and the client loading-mask field before sending the request. `SdkHelper.lua:80-93` obtains and persists the device identifier through native or Unity identifiers, with a GUID fallback. `SdkHelper.lua:145-152` obtains the push token.

## Native risk dependency

`YiDunHelper.lua:2-4` defines version thresholds `1.4.10` and `1.5.3`. Android 1.7.0 selects the instance call `CS.DeviceFingerprint.Instance:GetToken()` at `YiDunHelper.lua:60-62`. The report contains account and IP placeholders, platform and scene information (`YiDunHelper.lua:48-58`). The login operation is represented by `"log"` (`EnumConfig.lua:422-424`).

`YiDunHelper:setToken` stores the returned token and marks it ready (`YiDunHelper.lua:23-26`). A scheduled callback then inserts the token into the report and emits `evt_yidunTokenCallback` (`YiDunHelper.lua:72-80`). `LoginModel.lua:258-260` executes the pending action. That action attaches `yidun_risk_check` to the email login request (`LoginModel.lua:104-105`).

The generated `dump.cs:329902-329950` identifies `DeviceFingerprint` as a Unity `MonoBehaviour` with initialization, token retrieval, coroutine waiting, role-information and touch-event methods. `script.json:513814-513822` maps `GetToken` and `WaitForToken`. These generated records contain method signatures and addresses. Their empty method bodies do not describe the native implementation, so token generation and its exact native-to-Lua delivery remain unresolved. The older-version and editor empty-token branches at `YiDunHelper.lua:64-69,81-84` do not establish support for an empty token in a current production login.

## Verification codes and providers

The inspected views use email verification codes for registration and password recovery. Registration requests a code, confirms it, sets a password and then performs ordinary email login (`LoginRegisterDialog.lua:35-53,76-88`, `LoginModel.lua:127-170`). Recovery accepts account-identification input, confirms a code and changes the password (`LoginForgotDialog.lua:56-73,147-177`, `LoginModel.lua:517-536`). No routine verification-code login for an existing account was identified in these views. Recovery would change the account and needs separate authorization.

Provider selection depends on platform and distribution channel. `LoginLayer.lua:157-188` exposes email and guest login for ordinary Android, STOVE for selected mobile channels, and Steam or STOVE for selected PC channels. STOVE initializes its native provider selection (`LoginModel.lua:173-185`). Its callback and the Steam ticket callback route through `doLogin`, which also waits for the risk report (`LoginModel.lua:599-645,23-35`). These source paths establish provider distinctions, but do not establish current availability or compatibility with a particular account.

## Runtime authentication status

A guest HTTP request on 2026-10-07 at 11:00:27 UTC, using a fresh local device identifier and omitting the native risk report, returned code `-5`. It issued no session. This establishes that the tested request shape was rejected, while the contribution of the device identifier, risk report and server policy remains unresolved.

The [protocol client](../../guides/protocol-client.md) imports a session from an official login response and performs the WebSocket handshake separately. Its response-capture addon and transport have passed local simulated tests. Official-client proxy compatibility, live session reuse and server training entry remain unverified until a user completes official authentication.
