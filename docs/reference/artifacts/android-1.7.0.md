# Android 1.7.0

This reference identifies the official Android package inspected on 2026-10-07 UTC. The [artifact record](android-1.7.0.json) contains complete hashes and selected source locations. Follow the [analysis guide](../../guides/analyze-apk.md) to reproduce the extraction.

## Package identity

- Official page: <https://www.pokerfate.com/>.
- Download: <https://aws.poker-fate.com/dl/PokerFate_Android.apk>.
- Package: `com.pokerfate.play`.
- Version name: `1.7.0`. Version code: `33`.
- Minimum Android SDK: `28`. Target Android SDK: `36`.
- Size: `1,612,525,590` bytes.
- SHA-256: `b7a77eb04e76013fe50ca4c25ecde1b2d6b8254353ab0d42dd83358417526e20`.
- HTTP Last-Modified: `2026-09-28T04:17:12Z`.
- HTTP ETag: `89a291b5f85f0fec3d6e728bd4205a8d-193`.

The ETag is a multipart object identifier. It is recorded separately from the package hash. The download URL identifies a mutable distribution endpoint, so the findings apply to the recorded bytes.

## Decoding parameters

The package uses ARM64 IL2CPP and metadata version `31`. Il2CppDumper `6.7.46` mapped code registration at RVA `0x39ff040` and metadata registration at RVA `0x3b402f8`. Native disassembly established the XENC stream transformation and the separate XXTEA keys used by Lua and protocol assets. The implementation is in `src/poker_fate_strategy_research/bundles.py`.

The static-field bytes used by the XENC decoder begin at metadata file offset `0x69ae20`. This offset is passed explicitly to the extractor. The selected bundle prefixes are `assets/aa/Android/gameres_assets_src/`, `assets/aa/Android/gameres_assets_src_`, and `assets/aa/Android/gameres_assets_proto_`.

Native method locations for reproducing the decoder inspection are recorded below. File offsets apply to this ELF library and differ from runtime addresses.

| Method              | RVA         | File offset |
| ------------------- | ----------- | ----------- |
| SecretSeed          | `0x1af4244` | `0x1af0244` |
| NonceToU64          | `0x1af42f4` | `0x1af02f4` |
| Mix                 | `0x1af4364` | `0x1af0364` |
| GenKeyBlock         | `0x1af439c` | `0x1af039c` |
| CreateDecryptStream | `0x1af488c` | `0x1af088c` |
| Static constructor  | `0x1af4b44` | `0x1af0b44` |
| XorStream.Read      | `0x1af4c78` | `0x1af0c78` |
| LuaAsset decoder    | `0x1cb4520` | `0x1cb0520` |
| ProtoAsset decoder  | `0x1b13f38` | `0x1b0ff38` |

## Source references

Research citations use decoded filenames and one-based line ranges. The JSON record maps those names to full Unity container paths, APK bundle entries, path IDs, sizes, and SHA-256 values. It also records the native inputs, release archive, and generated method-map hashes. Downloaded and decoded files are retained locally in ignored paths.

One cited upstream class is named `LobbyByinDialog`. Its spelling is retained in evidence identifiers. The apparent intended spelling is "buy-in", and it is treated as an upstream typo in the spelling configuration.

The client sources establish client behavior and message schemas. Production delivery permissions, server implementation, and actual account behavior were not observed.
