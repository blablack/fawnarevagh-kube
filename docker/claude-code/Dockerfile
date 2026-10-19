FROM ubuntu:26.04

ARG DEBIAN_FRONTEND=noninteractive

# No SHELL instruction: buildah ignores it when building OCI images (Jenkins), so RUN
# lines always go through /bin/sh (dash) — keep them POSIX

RUN apt-get update -y && \
    apt-get install -y --no-install-recommends ca-certificates curl git jq sudo tini tmux tzdata && \
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

# The base image ships an "ubuntu" user on uid 1000; replace it with "claude"
RUN userdel -r ubuntu && \
    useradd -m -u 1000 -U -s /bin/bash claude && \
    echo 'claude ALL=(ALL) NOPASSWD:ALL' > /etc/sudoers.d/claude && \
    chmod 0440 /etc/sudoers.d/claude

# Managed-policy CLAUDE.md: always loaded, and kept current by rebuilding the image
# (unlike ~/.claude/CLAUDE.md, which lives on the PVC and is left to the user)
COPY CLAUDE.md /etc/claude-code/CLAUDE.md
COPY start.sh remote-control-loop.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/start.sh /usr/local/bin/remote-control-loop.sh

# Also blocks `claude update`/`claude install`, which would drop a second copy into
# ~/.local/bin on the PVC and outlive the next image rebuild
ENV DISABLE_UPDATES=1
ENV PATH=$PATH:/home/claude/.local/bin

USER claude
WORKDIR /home/claude

ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["/usr/local/bin/start.sh"]
