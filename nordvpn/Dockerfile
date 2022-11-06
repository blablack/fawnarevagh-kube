FROM ubuntu:22.04

ARG DEBIAN_FRONTEND=noninteractive

RUN apt update -y && \
    apt install -y curl && \
    curl https://repo.nordvpn.com/deb/nordvpn/debian/pool/main/nordvpn-release_1.0.0_all.deb --output /tmp/nordrepo.deb && \
    apt install -y /tmp/nordrepo.deb && \
    apt update -y && \
    apt install -y systemctl nordvpn && \
    apt remove -y nordvpn-release && \
    apt autoremove -y && \
    apt autoclean -y && \
    rm -rf \
		/tmp/* \
		/var/cache/apt/archives/* \
		/var/lib/apt/lists/* \
		/var/tmp/* 

RUN echo 'net.ipv6.conf.all.disable_ipv6 = 1' >> /etc/sysctl.conf && \
    echo 'net.ipv6.conf.default.disable_ipv6 = 1' >> /etc/sysctl.conf && \
    echo 'net.ipv6.conf.lo.disable_ipv6 = 1' >> /etc/sysctl.conf && \
    echo 'net.ipv6.conf.tun0.disable_ipv6 = 1' >> /etc/sysctl.conf && \
    echo 'net.ipv4.ip_forward=1' >> /etc/sysctl.conf 

CMD systemctl start nordvpn && sleep 2s && \
    nordvpn login --token $NORDVPN_TOKEN && \
    nordvpn set technology nordlynx && \
    nordvpn connect $COUNTRY && \
    while nordvpn status | grep -q 'Status: Connected' ; do sleep 5m ; done


