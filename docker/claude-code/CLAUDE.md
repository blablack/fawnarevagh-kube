# Environment

You're running headless in a Kubernetes pod, driven through Remote Control from the
user's phone or claude.ai/code. There is no display, no Android emulator/device, and no sudo.

- Projects live in `~/projects`. Everything under `~` persists; anything installed outside it
  does not survive a pod restart. Claude Code itself is updated by rebuilding the image, not
  `claude update`.
- GitHub: `gh` is authenticated via `GH_TOKEN`, and `git` over https uses it.
- Android: SDK at `$ANDROID_HOME` (baked into the image: platform-tools plus the newest major
  platform and latest build-tools — `ls $ANDROID_HOME/platforms $ANDROID_HOME/build-tools`),
  JDK 21. Build with `./gradlew`. Prefer the preinstalled `compileSdk`/build-tools versions:
  other SDK packages (AGP auto-download or `android sdk install <path>`) are lost on every pod
  restart.
- `sdkmanager` is deprecated and forwards to the `android` CLI (`android sdk list|install`, with
  `/` package paths like `platforms/android-37.0`). Its first run downloads ~250MB into
  `~/.android`, which persists.
- With no emulator, verify UI with JVM-side tests (Robolectric, Compose screenshot tests such as
  Roborazzi) and look at the resulting PNGs.
- To hand an APK (or any other file) to the user, copy it to `/nasio` — a folder on their NAS —
  with a descriptive name, e.g. `<app>-<version>-debug.apk`.
