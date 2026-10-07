# Android client analysis

Use the [development environment](development.md) and keep the downloaded package and derived output in ignored local directories. Record package identity before using it as evidence. Each artifact reference owns its decoding parameters, and each research report states which artifact it examined.

## Preserve the official package

The [official site](https://www.pokerfate.com/) links to an Android download whose contents can change without a URL change. Save the response headers and choose a dated filename:

```bash
mkdir -p artifacts
curl --fail --location \
  --dump-header artifacts/PokerFate_Android-20261007.headers \
  --output artifacts/PokerFate_Android-20261007.apk \
  https://aws.poker-fate.com/dl/PokerFate_Android.apk
```

Measure the downloaded file and inspect its manifest:

```bash
python - <<'PY'
import hashlib
from pathlib import Path

apk = Path('artifacts/PokerFate_Android-20261007.apk')
with apk.open('rb') as stream:
    digest = hashlib.file_digest(stream, 'sha256').hexdigest()
print(apk.stat().st_size, digest)
PY

apktool decode --only-manifest --no-src --no-assets \
  --output work/manifest-1.7.0 artifacts/PokerFate_Android-20261007.apk
```

Read the package name from `AndroidManifest.xml` and the version and SDK levels from `apktool.yml`. Record these values with the retrieval date, source URL, byte count, and SHA-256. HTTP modification time and multipart ETag describe the response, while SHA-256 identifies the downloaded bytes. The [Android 1.7.0 reference](../reference/artifacts/android-1.7.0.md) records the package inspected on 2026-10-07. If the download has changed, establish a new artifact identity before applying its decoding parameters.

## Inspect native metadata

Extract the ARM64 library and Unity metadata from the same APK:

```bash
mkdir -p work/native work/native-map
unzip -p artifacts/PokerFate_Android-20261007.apk \
  lib/arm64-v8a/libil2cpp.so > work/native/libil2cpp.so
unzip -p artifacts/PokerFate_Android-20261007.apk \
  assets/bin/Data/Managed/Metadata/global-metadata.dat > work/native/global-metadata.dat
```

[Il2CppDumper v6.7.46](https://github.com/Perfare/Il2CppDumper/releases/tag/v6.7.46) generated the method and field map used in this artifact's analysis. Preserve and verify its release archive against the tool hash in the artifact record:

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
  artifacts/PokerFate_Android-20261007.apk \
  --output work/android-1.7.0 \
  --seed-offset 0x69ae20
```

The extractor requires a fresh output directory. It unwraps selected XENC source bundles, decodes encoded Lua and protocol assets, preserves their full Unity container paths, and writes `inventory.json` with hashes and sizes. The metadata field offset comes from the native decoder's static-field initialization and must be checked for each build.

For the recorded package, the extraction produced 66 bundles and 691 assets: 683 Lua files and eight protocol files. An independent extraction produced the same decoded hashes. Match source citations to the [selected source records](../reference/artifacts/android-1.7.0.json) through the APK entry, container path, and Unity path ID. Preserve decoded bytes when checking hashes, including line endings. Keep full inventories and decoded client source local.
