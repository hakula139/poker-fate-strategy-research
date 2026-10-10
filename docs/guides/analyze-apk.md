# Android client analysis

Use the [development environment](development.md) and the decoding parameters in the package's artifact reference.

## Preserve the official package

The [official download](https://aws.poker-fate.com/dl/PokerFate_Android.apk) is mutable. Save the package and response headers:

```bash
mkdir -p artifacts
curl --fail --location \
  --dump-header artifacts/PokerFate_Android.headers \
  --output artifacts/PokerFate_Android.apk \
  https://aws.poker-fate.com/dl/PokerFate_Android.apk
```

Measure the downloaded file and inspect its manifest:

```bash
python - <<'PY'
import hashlib
from pathlib import Path

apk = Path('artifacts/PokerFate_Android.apk')
with apk.open('rb') as stream:
    digest = hashlib.file_digest(stream, 'sha256').hexdigest()
print(apk.stat().st_size, digest)
PY

apktool decode --only-manifest --no-src --no-assets \
  --output work/manifest-1.7.0 artifacts/PokerFate_Android.apk
```

Read the package name from `AndroidManifest.xml` and the version and SDK levels from `apktool.yml`. Match the size and SHA-256 to the [artifact record](../reference/artifacts/android-1.7.0.json) before applying its decoding parameters. A changed package requires its own provenance record.

## Inspect native metadata

Extract the ARM64 library and Unity metadata from the same APK:

```bash
mkdir -p work/native work/native-map
unzip -p artifacts/PokerFate_Android.apk \
  lib/arm64-v8a/libil2cpp.so > work/native/libil2cpp.so
unzip -p artifacts/PokerFate_Android.apk \
  assets/bin/Data/Managed/Metadata/global-metadata.dat > work/native/global-metadata.dat
```

Use [Il2CppDumper v6.7.46](https://github.com/Perfare/Il2CppDumper/releases/tag/v6.7.46) and verify its archive against the artifact record:

```bash
curl --fail --location \
  --output artifacts/Il2CppDumper-net7-v6.7.46.zip \
  https://github.com/Perfare/Il2CppDumper/releases/download/v6.7.46/Il2CppDumper-net7-v6.7.46.zip
unzip -q artifacts/Il2CppDumper-net7-v6.7.46.zip -d work/il2cpp-dumper
jq '.RequireAnyKey = false' work/il2cpp-dumper/config.json > work/il2cpp-dumper/config.tmp
mv work/il2cpp-dumper/config.tmp work/il2cpp-dumper/config.json
research_root="$PWD"
DOTNET_ROLL_FORWARD=Major dotnet \
  "$research_root/work/il2cpp-dumper/Il2CppDumper.dll" \
  "$research_root/work/native/libil2cpp.so" \
  "$research_root/work/native/global-metadata.dat" \
  "$research_root/work/native-map"
```

The archive targets .NET 7. The pinned development shell provides .NET 8, so the command permits a major-version runtime roll-forward. The output directory must already exist. Generated C# contains signatures and empty method bodies. Inspect the mapped native functions when a finding depends on their implementation.

## Extract Lua and protocol assets

Install the locked Python dependencies, then select the metadata field offset recorded for the artifact:

```bash
uv sync --locked
uv run --no-sync poker-fate-strategy extract \
  artifacts/PokerFate_Android.apk \
  --output work/android-1.7.0 \
  --seed-offset 0x69ae20
```

The extractor requires a fresh output directory. It unwraps selected XENC source bundles, decodes encoded Lua and protocol assets, preserves their full Unity container paths, and writes `inventory.json` with hashes and sizes. The metadata field offset comes from the native decoder's static-field initialization and must be checked for each build.

The recorded package contains 66 selected bundles and 691 source assets: 683 Lua files and eight protocol files. Match citations to the [source records](../reference/artifacts/android-1.7.0.json) by APK entry, container path, and Unity path ID. Hash comparisons require unchanged decoded bytes, including line endings.
