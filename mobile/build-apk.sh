#!/usr/bin/env bash
set -euo pipefail

# Build the VDO Studio Offline APK using a pinned upstream llama.cpp Android runtime.
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LLAMA_COMMIT="${LLAMA_CPP_COMMIT:-3d65c90d04d337e88f2b1f7f0061f40a5324e662}"
WORKDIR="${VDO_ANDROID_BUILD_DIR:-$ROOT/.build/android}"
LLAMA="$WORKDIR/llama.cpp"

if [[ ! -d "$LLAMA/.git" ]]; then
  mkdir -p "$WORKDIR"
  git clone --filter=blob:none --no-checkout https://github.com/ggml-org/llama.cpp.git "$LLAMA"
fi
git -C "$LLAMA" fetch --depth=1 origin "$LLAMA_COMMIT"
git -C "$LLAMA" checkout --detach FETCH_HEAD

SRC="$ROOT/mobile/app/src/main"
DEST="$LLAMA/examples/llama.android/app/src/main"
cp "$SRC/AndroidManifest.xml" "$DEST/AndroidManifest.xml"
cp "$SRC/java/com/example/llama/MainActivity.kt" "$DEST/java/com/example/llama/MainActivity.kt"
cp "$SRC/res/layout/activity_main.xml" "$DEST/res/layout/activity_main.xml"
cp "$SRC/res/values/strings.xml" "$DEST/res/values/strings.xml"
cp "$SRC/res/values/themes.xml" "$DEST/res/values/themes.xml"

chmod +x "$LLAMA/examples/llama.android/gradlew"
cd "$LLAMA/examples/llama.android"
./gradlew --no-daemon :app:assembleDebug
mkdir -p "$ROOT/dist"
cp app/build/outputs/apk/debug/app-debug.apk "$ROOT/dist/VDO-Studio-Offline-debug.apk"
echo "APK created at $ROOT/dist/VDO-Studio-Offline-debug.apk"
