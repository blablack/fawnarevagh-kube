# Environment

You're running headless in a Kubernetes pod, driven through Remote Control from the
user's phone or claude.ai/code. There is no display.

- Projects live in `~/projects`. The session starts in the directory set by `$CLAUDE_WORKDIR`
  (defaults to `~/projects` if unset). Everything under `~` persists; anything installed outside it
  does not survive a pod restart. Claude Code itself is updated by rebuilding the image, not
  `claude update`.
- GitHub: `gh` is authenticated via `GH_TOKEN`, and `git` over https uses it.
- `sudo` is passwordless: use it to `apt-get install` whatever a project needs (the image is
  minimal: no JDK, Android SDK or other toolchains). System-wide installs live in the container
  layer and are lost on every pod restart, so for anything you'll want again put it under `~`
  (e.g. SDKs, `~/.local`) or note the install steps in the project's README/CLAUDE.md.
- To hand a file to the user, copy it to the directory in `$HANDOFF_DIR` (set by the deployment;
  a folder the user can reach outside the pod) with a descriptive name. If `HANDOFF_DIR` is unset,
  ask the user.
- **Android dev**: not baked into the image. Run `setup-android` once (idempotent, a few minutes,
  re-run it after a pod restart if the emulator complains about missing libraries). It installs
  JDK 21 into `~/jdk` and the SDK (platform-tools, emulator, newest platform, latest build-tools,
  a google_apis x86_64 system image) into `~/android-sdk`, both on the PVC. `ANDROID_HOME`,
  `JAVA_HOME` and `PATH` are already set, so no restart is needed. Build with `./gradlew`; prefer
  the installed `compileSdk`/build-tools versions (`ls $ANDROID_HOME/platforms $ANDROID_HOME/build-tools`).
- `sdkmanager` is deprecated and forwards to the `android` CLI (`android sdk list|install`, with
  `/` package paths like `platforms/android-37.0`).
- **Android emulator**: `/dev/kvm` is available. Create an AVD once (it persists in `~/.android`):
  ```
  avdmanager create avd -n emu \
    -k "$(ls -d $ANDROID_HOME/system-images/*/*/x86_64 | head -1 | sed "s|$ANDROID_HOME/||")" \
    --device pixel_6
  ```
  Start it headless (software rendering — no `/dev/dri` in this pod):
  ```
  emulator -avd emu -no-window -no-audio -gpu swiftshader_indirect &
  adb wait-for-device
  ```
