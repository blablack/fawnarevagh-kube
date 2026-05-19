FROM ubuntu:26.04

ARG DEBIAN_FRONTEND=noninteractive

SHELL ["/bin/bash", "-c"]

RUN apt-get update -y && \
    apt-get install -y --no-install-recommends curl && \
    DEB=$(curl -s https://repo.nordvpn.com/deb/nordvpn/debian/pool/main/n/nordvpn/ | grep -o 'nordvpn_[^" >]*_amd64.deb' | sort -V | tail -n1) && \
    curl -L "https://repo.nordvpn.com/deb/nordvpn/debian/pool/main/n/nordvpn/${DEB}" --output /tmp/nordrepo.deb && \
    apt-get install -y --no-install-recommends /tmp/nordrepo.deb && \
    apt-get remove --purge -y curl && \
    apt-get autoremove --purge -y && \
    rm -rf /tmp/* /var/cache/apt/archives/* /var/tmp/* /var/lib/apt/lists/*

COPY run_nordvpn.sh wait_for_nordvpn.sh check_nordvpn_connection.sh /
RUN chmod +x /run_nordvpn.sh /wait_for_nordvpn.sh /check_nordvpn_connection.sh

CMD ["/run_nordvpn.sh"]
