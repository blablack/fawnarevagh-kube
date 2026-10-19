# Environment

You're running headless in a Kubernetes pod, driven through Remote Control from the
user's phone or claude.ai/code. There is no display and no sudo.

- Projects live in `~/projects`. The session starts in the directory set by `$CLAUDE_WORKDIR`
  (defaults to `~/projects` if unset). Everything under `~` persists; anything installed outside it
  does not survive a pod restart. Claude Code itself is updated by rebuilding the image, not
  `claude update`.
- GitHub: `gh` is authenticated via `GH_TOKEN`, and `git` over https uses it.
- Android: SDK at `$ANDROID_HOME` (baked into the image: platform-tools, emulator, the newest
  major platform, and latest build-tools — `ls $ANDROID_HOME/platforms $ANDROID_HOME/build-tools`),
  JDK 21. Build with `./gradlew`. Prefer the preinstalled `compileSdk`/build-tools versions:
  other SDK packages (AGP auto-download or `android sdk install <path>`) are lost on every pod
  restart.
- `sdkmanager` is deprecated and forwards to the `android` CLI (`android sdk list|install`, with
  `/` package paths like `platforms/android-37.0`). Its first run downloads ~250MB into
  `~/.android`, which persists.
- **Android emulator**: `/dev/kvm` is available. The system image is NOT baked into the image —
  install it once into `~/.android` (it persists on the PVC):
  ```
  android sdk install "system-images/android-36/google_apis/x86_64"
  ```
  Then create an AVD (also persists):
  ```
  avdmanager create avd -n emu -k "system-images/android-36/google_apis/x86_64" --device pixel_6
  ```
  Start it headless (software rendering — no `/dev/dri` in this pod):
  ```
  emulator -avd emu -no-window -no-audio -gpu swiftshader_indirect &
  adb wait-for-device
  ```
- To hand an APK (or any other file) to the user, copy it to the directory in `$HANDOFF_DIR`
  (set by the deployment; a folder the user can reach outside the pod) with a descriptive
  name, e.g. `<app>-<version>-debug.apk`. If `HANDOFF_DIR` is unset, ask the user.
