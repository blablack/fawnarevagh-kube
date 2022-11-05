FROM ubuntu:22.04
LABEL maintainer="Julio Gutierrez julio.guti+nordvpn@pm.me"

ARG DEBIAN_FRONTEND=noninteractive

RUN apt-get update -y && \
    apt-get install -y curl && \
    curl https://repo.nordvpn.com/deb/nordvpn/debian/pool/main/nordvpn-release_1.0.0_all.deb --output /tmp/nordrepo.deb && \
    apt-get install -y /tmp/nordrepo.deb && \
    apt-get update -y && \
    apt-get install -y nordvpn && \
    apt-get remove -y nordvpn-release && \
    apt-get autoremove -y && \
    apt-get autoclean -y && \
    rm -rf \
		/tmp/* \
		/var/cache/apt/archives/* \
		/var/lib/apt/lists/* \
		/var/tmp/* 

RUN echo 'net.ipv6.conf.all.disable_ipv6 = 1' >> /etc/sysctl.conf && \
    echo 'net.ipv6.conf.default.disable_ipv6 = 1' >> /etc/sysctl.conf && \
    echo 'net.ipv6.conf.lo.disable_ipv6 = 1' >> /etc/sysctl.conf && \
    echo 'net.ipv6.conf.tun0.disable_ipv6 = 1' >> /etc/sysctl.conf 

CMD nordvpn login --token $NORDVPN_TOKEN ; nordvpn set technology nordlynx ; nordvpn connect $IRELAND