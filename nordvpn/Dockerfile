FROM ubuntu:23.10

ARG DEBIAN_FRONTEND=noninteractive

HEALTHCHECK --interval=30m --timeout=20s --start-period=1m \
	CMD if test $( curl --interface nordlynx -m 10 -s https://api.nordvpn.com/v1/helpers/ips/insights | jq -r '.["protected"]' ) == "true" ; then exit 0; else exit 1; fi

RUN apt-get update -y 
RUN apt-get install -y curl
RUN curl https://repo.nordvpn.com/deb/nordvpn/debian/pool/main/nordvpn-release_1.0.0_all.deb --output /tmp/nordrepo.deb 
RUN apt-get install -y /tmp/nordrepo.deb 
RUN apt-get update -y 
RUN apt-get install -y jq iputils-ping nordvpn 
RUN apt-get remove -y nordvpn-release 
RUN apt-get dist-upgrade -y 
RUN apt-get autoremove -y 
RUN apt-get autoclean -y 
RUN rm -rf /tmp/* /var/cache/apt/archives/* /var/lib/apt/lists/* /var/tmp/* 

COPY run_nordvpn.sh / 
RUN chmod +x run_nordvpn.sh

COPY wait_for_nordvpn.sh / 
RUN chmod +x wait_for_nordvpn.sh

CMD /run_nordvpn.sh
