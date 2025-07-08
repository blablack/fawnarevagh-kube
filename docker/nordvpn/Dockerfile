FROM ubuntu:latest

ARG DEBIAN_FRONTEND=noninteractive

SHELL ["/bin/bash", "-c"]

RUN apt-get update -y && \
    apt-get install -y --no-install-recommends curl jq iputils-ping && \
    rm -rf /var/lib/apt/lists/*

RUN curl -k -L https://repo.nordvpn.com/deb/nordvpn/debian/pool/main/n/nordvpn/nordvpn_3.20.2_amd64.deb --output /tmp/nordrepo.deb 
#RUN curl -k -L https://repo.nordvpn.com/deb/nordvpn/debian/pool/main/n/nordvpn/$(curl -s https://repo.nordvpn.com/deb/nordvpn/debian/pool/main/n/nordvpn/ | grep -o 'nordvpn-release_[^" >]*_all.deb' | sort -V | tail -n1) --output /tmp/nordrepo.deb 
RUN apt-get install -y /tmp/nordrepo.deb && \
    rm -rf /tmp/* /var/cache/apt/archives/* /var/tmp/*

WORKDIR /

COPY run_nordvpn.sh / 
RUN chmod +x run_nordvpn.sh

COPY wait_for_nordvpn.sh / 
RUN chmod +x wait_for_nordvpn.sh

COPY add_to_meshnet.sh / 
RUN chmod +x add_to_meshnet.sh

COPY check_nordvpn_connection.sh / 
RUN chmod +x check_nordvpn_connection.sh

COPY get_mesh_name.sh / 
RUN chmod +x get_mesh_name.sh
RUN mkdir -p /config

HEALTHCHECK --interval=30s --timeout=10s --start-period=30s CMD /check_nordvpn_connection.sh || exit 1

CMD /run_nordvpn.sh
