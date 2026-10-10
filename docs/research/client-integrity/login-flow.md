# Official login flow

The Android 1.7.0 client requires a native device-risk token for email login. Official email login succeeded and enabled free-practice gameplay. Script-only authentication remains unverified.

Source citations refer to the [Android 1.7.0 artifact](../../reference/artifacts/android-1.7.0.md) and its [method-map record](../../reference/artifacts/android-1.7.0.json).

## Email login

The form validates an email address and a nonempty password, then selects login type `2` (`LoginLayer.lua:304-332`, `EnumConfig.lua:386-395`). `LoginModel:emailLogin` sends the email as `token` and password as `verify`, with platform, device, language, attribution, and push fields (`LoginModel.lua:38-43,93-123`, `SdkHelper.lua:80-93,145-152`). Sending waits for the native risk report.

## Native risk dependency

Android 1.7.0 uses `CS.DeviceFingerprint.Instance:GetToken()` (`YiDunHelper.lua:2-4,60-62`). The report contains account and IP placeholders, platform and scene information, and login operation `"log"` (`YiDunHelper.lua:48-58`, `EnumConfig.lua:422-424`). The token callback releases the pending login action, attaching `yidun_risk_check` (`YiDunHelper.lua:23-26,72-80`, `LoginModel.lua:104-105,258-260`).

The native map identifies `DeviceFingerprint` initialization, retrieval, and callback methods (`dump.cs:329902-329950`, `script.json:513814-513822`). Token generation and native-to-Lua delivery remain unresolved. Empty-token fallbacks are restricted to older versions and the editor (`YiDunHelper.lua:64-69,81-84`).

## Verification codes and providers

Email verification codes support registration and password recovery (`LoginRegisterDialog.lua:35-53,76-88`, `LoginModel.lua:127-170`, `LoginForgotDialog.lua:56-73,147-177`, `LoginModel.lua:517-536`). The inspected existing-account flow uses a password. Recovery changes the account password.

Provider availability depends on platform and distribution. Ordinary Android exposes email and guest login, selected mobile channels expose STOVE, and selected PC channels expose Steam or STOVE (`LoginLayer.lua:157-188`). Provider callbacks also wait for the risk report (`LoginModel.lua:173-185,599-645,23-35`). Compatibility with a particular account requires runtime verification.

## Runtime authentication status

Official Android email login and [practice-table delivery](hidden-card-delivery.md#practice-table-runtime-observations) succeeded. A guest HTTP request with a fresh device identifier and no native risk report returned `-5` without a session. The cause of that rejection remains unresolved.

The separate [protocol client](../../guides/protocol-client.md) imports an official session and establishes its own WebSocket connection. Live proxy capture, session reuse, and training entry through that client remain unverified.
