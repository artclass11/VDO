# VDO Studio Offline — Android APK

The Android companion is a local GGUF model-powered documentary director assistant. Choose a compatible chat/instruct GGUF model from device storage; VDO copies it into app-private storage and runs inference through the upstream llama.cpp Android sample runtime. The APK does not bundle a multi-gigabyte model, and the app requests no internet permission.

It helps turn a single prompt into a documentary treatment, chapter outline, shot list, edit notes, sound plan, and color-grading intent, then exports the draft as a text file. Full editorial interchange/color package generation is performed by the desktop app.

## Build APK (one time, requires internet for source/dependencies)

The reproducible GitHub Actions workflow checks out a pinned llama.cpp source revision, injects the VDO app UI into the upstream Android sample (which provides the JNI runtime), and builds the debug APK.

1. Open GitHub → Actions → VDO Offline Apps.
2. Run the workflow or push a commit that changes the mobile/desktop app.
3. Download the vdo-studio-android-debug artifact and install the APK on a compatible device.

## Use offline

1. Open VDO Studio Offline.
2. Tap Import GGUF model and select a compatible instruct/chat GGUF file stored on the phone.
3. Wait for local model loading to finish.
4. Enter a documentary idea, choose the target editing program and look, then tap Generate offline plan.
5. Save the generated plan to local storage.

No model is pre-bundled: mobile models can consume several gigabytes and the model license/terms remain the model publisher's responsibility. Model speed and context length depend on device RAM, CPU/GPU support and model size. The app has no internet permission; downloading the model is a separate, user-controlled step done before offline work.

## Upstream runtime and license

This app build reuses the Android sample/runtime under the MIT-licensed ggml-org/llama.cpp project. The CI workflow pins the source commit for reproducibility. See the llama.cpp Android guide at https://github.com/ggml-org/llama.cpp/blob/master/docs/android.md and the upstream repository's LICENSE file.
