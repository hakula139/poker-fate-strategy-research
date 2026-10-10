# Android 1.7.0

The [artifact record](android-1.7.0.json) identifies the inspected package and source files. The [analysis guide](../../guides/analyze-apk.md) explains extraction.

## Package identity

- Official page: <https://www.pokerfate.com/>.
- Download: <https://aws.poker-fate.com/dl/PokerFate_Android.apk>.
- Package: `com.pokerfate.play`.
- Version name: `1.7.0`. Version code: `33`.
- Minimum Android SDK: `28`. Target Android SDK: `36`.
- Size: `1,612,525,590` bytes.
- SHA-256: `b7a77eb04e76013fe50ca4c25ecde1b2d6b8254353ab0d42dd83358417526e20`.

The download endpoint is mutable. Findings apply to the package identified by this SHA-256.

## Decoding parameters

The package uses ARM64 IL2CPP and metadata version `31`. Code registration is at RVA `0x39ff040`, and metadata registration is at `0x3b402f8`. Source bundles use XENC, with separate XXTEA keys for Lua and protocol assets. The decoder is implemented in [bundles.py](../../../src/poker_fate_strategy_research/bundles.py).

The static-field bytes used by the XENC decoder begin at metadata file offset `0x69ae20`. This offset is passed explicitly to the extractor. The selected bundle prefixes are `assets/aa/Android/gameres_assets_src/`, `assets/aa/Android/gameres_assets_src_`, and `assets/aa/Android/gameres_assets_proto_`.

Native decoder locations use RVAs and ELF file offsets:

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

Research citations use decoded filenames and one-based line ranges. The artifact record maps them to Unity container paths, APK entries, path IDs, sizes, and hashes. It also identifies the native inputs, Il2CppDumper release, and generated method maps.

The sources establish client behavior and message schemas. [Practice-table observations](../../research/client-integrity/hidden-card-delivery.md#practice-table-runtime-observations) cover limited live delivery. Wider server filtering remains unverified.
