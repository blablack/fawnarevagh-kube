FROM ghcr.io/haveagitgat/tdarr_node:latest AS build

ARG DOVI_TOOL_TAG="2.3.2"
ARG MP4BOX_TAG="v2.4.0"
ARG HDR10PLUS_TOOL_TAG="1.7.2"

# Update and install dependencies
RUN apt-get update && \
    apt-get install -y \
        build-essential \
        git \
        pkg-config \
        wget \
        zlib1g-dev \
        mediainfo \
        mkvtoolnix \
        jq \
        bc \
    && rm -rf /var/lib/apt/lists/*

# MP4Box
RUN git clone --depth 1 --branch ${MP4BOX_TAG} https://github.com/gpac/gpac.git && \
    cd gpac && \
    ./configure --static-bin && \
    make -j$(nproc) && \
    make install

# Dovi Tool
RUN wget -O - "https://github.com/quietvoid/dovi_tool/releases/download/${DOVI_TOOL_TAG}/dovi_tool-${DOVI_TOOL_TAG}-x86_64-unknown-linux-musl.tar.gz" | \
    tar -zx -C /usr/local/bin/

# HDR10Plus Tool
RUN wget -O - "https://github.com/quietvoid/hdr10plus_tool/releases/download/${HDR10PLUS_TOOL_TAG}/hdr10plus_tool-${HDR10PLUS_TOOL_TAG}-x86_64-unknown-linux-musl.tar.gz" | \
    tar -zx -C /usr/local/bin/

FROM ghcr.io/haveagitgat/tdarr_node:latest

# Upgrade to latest Jellyfin FFmpeg
RUN CODENAME=$(. /etc/os-release && echo "$VERSION_CODENAME") && \
    VERSION=$(wget -qO- "https://api.github.com/repos/jellyfin/jellyfin-ffmpeg/releases/latest" | grep -o '"tag_name": *"v[^"]*"' | grep -o '[0-9][^"]*') && \
    wget -q "https://github.com/jellyfin/jellyfin-ffmpeg/releases/download/v${VERSION}/jellyfin-ffmpeg5_${VERSION}-${CODENAME}_amd64.deb" && \
    apt-get install -y ./jellyfin-ffmpeg5_${VERSION}-${CODENAME}_amd64.deb && \
    rm -f ./jellyfin-ffmpeg5_*.deb && \
    rm -rf /var/lib/apt/lists/*

# Copy tools from the build stage
COPY --from=build /usr/local/bin/dovi_tool /usr/local/bin/
COPY --from=build /usr/local/bin/hdr10plus_tool /usr/local/bin/
COPY --from=build /usr/local/bin/MP4Box /usr/local/bin/
COPY --from=build /usr/local/bin/gpac /usr/local/bin/

RUN chmod 755 /usr/local/bin/dovi_tool /usr/local/bin/hdr10plus_tool /usr/local/bin/MP4Box /usr/local/bin/gpac