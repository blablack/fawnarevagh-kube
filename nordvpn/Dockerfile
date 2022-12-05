FROM ubuntu:22.04

ARG DEBIAN_FRONTEND=noninteractive

#HEALTHCHECK --interval=5m --timeout=20s --start-period=1m \
#	CMD if test $( curl -m 10 -s https://api.nordvpn.com/v1/helpers/ips/insights | jq -r '.["protected"]' ) = "true" ; then exit 0; else nordvpn disconnect; nordvpn connect ${CONNECT} ; exit $?; fi

RUN apt update -y && \
    apt install -y curl && \
    curl https://repo.nordvpn.com/deb/nordvpn/debian/pool/main/nordvpn-release_1.0.0_all.deb --output /tmp/nordrepo.deb && \
    apt install -y /tmp/nordrepo.deb && \
    apt update -y && \
    apt install -y jq iputils-ping nordvpn && \
    apt remove -y nordvpn-release && \
    apt autoremove -y && \
    apt autoclean -y && \
    rm -rf \
		/tmp/* \
		/var/cache/apt/archives/* \
		/var/lib/apt/lists/* \
		/var/tmp/* 

COPY run_nordvpn.sh / 
RUN chmod +x run_nordvpn.sh

COPY wait_for_nordvpn.sh / 
RUN chmod +x wait_for_nordvpn.sh

CMD /run_nordvpn.sh


