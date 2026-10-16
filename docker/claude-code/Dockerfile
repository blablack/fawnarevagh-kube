FROM ubuntu:26.04

ARG DEBIAN_FRONTEND=noninteractive

# No SHELL instruction: buildah ignores it when building OCI images (Jenkins), so RUN
# lines always go through /bin/sh (dash) — keep them POSIX

RUN apt-get update -y && \
    apt-get install -y --no-install-recommends ca-certificates curl git tmux tini tzdata unzip zip jq ripgrep less nano python3 openjdk-21-jdk-headless && \
    curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg -o /usr/share/keyrings/githubcli-archive-keyring.gpg && \
    echo "deb [arch=amd64 signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" > /etc/apt/sources.list.d/github-cli.list && \
    apt-get update -y && \
    apt-get install -y --no-install-recommends gh && \
    rm -rf /tmp/* /var/cache/apt/archives/* /var/tmp/* /var/lib/apt/lists/*

# git over https to GitHub authenticates through gh, which reads GH_TOKEN (same as `gh auth setup-git`)
RUN git config --system credential.https://github.com.helper '' && \
    git config --system --add credential.https://github.com.helper '!/usr/bin/gh auth git-credential'

# Claude Code: the native installer puts it under $HOME, which the PVC hides at runtime, so
# copy the self-contained binary out. Updated by rebuilding the image (self-updates disabled below).
RUN curl -fsSL https://claude.ai/install.sh | bash && \
    cp -L /root/.local/bin/claude /usr/local/bin/claude && \
    rm -rf /root/.local /root/.claude /root/.claude.json

# Android SDK: latest cmdline-tools (no pinned version), then platform-tools and the latest
# stable platform + build-tools. Owned by uid 1000 so AGP can still fetch anything else a
# project needs (that lands in the container layer and is lost on restart).
ENV ANDROID_HOME=/opt/android-sdk
RUN ZIP=$(curl -fsSL https://dl.google.com/android/repository/repository2-3.xml | grep -o 'commandlinetools-linux-[0-9]*_latest.zip' | sort -V | tail -n1) && \
    curl -fsSL "https://dl.google.com/android/repository/${ZIP}" -o /tmp/cmdline-tools.zip && \
    unzip -q /tmp/cmdline-tools.zip -d /tmp && \
    mkdir -p "$ANDROID_HOME/cmdline-tools" && \
    mv /tmp/cmdline-tools "$ANDROID_HOME/cmdline-tools/latest" && \
    SDKMANAGER="$ANDROID_HOME/cmdline-tools/latest/bin/sdkmanager" && \
    (yes || true) | "$SDKMANAGER" --licenses > /dev/null && \
    LIST=$("$SDKMANAGER" --list 2>/dev/null) && \
    PLATFORM=$(printf '%s\n' "$LIST" | grep -oE '^ *platforms;android-[0-9]+ ' | tr -d ' ' | sort -V | tail -n1) && \
    BUILD_TOOLS=$(printf '%s\n' "$LIST" | grep -oE '^ *build-tools;[0-9.]+ ' | tr -d ' ' | sort -V | tail -n1) && \
    echo "Installing $PLATFORM and $BUILD_TOOLS" && \
    [ -n "$PLATFORM" ] && [ -n "$BUILD_TOOLS" ] && \
    "$SDKMANAGER" "platform-tools" "$PLATFORM" "$BUILD_TOOLS" > /dev/null && \
    chown -R 1000:1000 "$ANDROID_HOME" && \
    rm -rf /tmp/* /root/.android

# The base image ships an "ubuntu" user on uid 1000; replace it with "claude"
RUN userdel -r ubuntu && \
    useradd -m -u 1000 -U -s /bin/bash claude

# Managed-policy CLAUDE.md: always loaded, and kept current by rebuilding the image
# (unlike ~/.claude/CLAUDE.md, which lives on the PVC and is left to the user)
COPY CLAUDE.md /etc/claude-code/CLAUDE.md
COPY start.sh remote-control-loop.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/start.sh /usr/local/bin/remote-control-loop.sh

# Also blocks `claude update`/`claude install`, which would drop a second copy into
# ~/.local/bin on the PVC and outlive the next image rebuild
ENV DISABLE_UPDATES=1
ENV PATH=$ANDROID_HOME/cmdline-tools/latest/bin:$ANDROID_HOME/platform-tools:$PATH:/home/claude/.local/bin

USER claude
WORKDIR /home/claude

ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["/usr/local/bin/start.sh"]
