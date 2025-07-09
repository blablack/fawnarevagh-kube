FROM ubuntu:latest

ARG DEBIAN_FRONTEND=noninteractive

SHELL ["/bin/bash", "-c"]

RUN apt-get update -y && \
    apt-get install -y curl jq iputils-ping 

#RUN curl -L https://repo.nordvpn.com/deb/nordvpn/debian/pool/main/n/nordvpn/nordvpn_3.20.2_amd64.deb --output /tmp/nordrepo.deb 
RUN curl -L https://repo.nordvpn.com/deb/nordvpn/debian/pool/main/n/nordvpn/$(curl -s https://repo.nordvpn.com/deb/nordvpn/debian/pool/main/n/nordvpn/ | grep -o 'nordvpn_[^" >]*_amd64.deb' | sort -V | tail -n1) --output /tmp/nordrepo.deb 
RUN apt-get install -y /tmp/nordrepo.deb && \
    rm -rf /tmp/* /var/cache/apt/archives/* /var/tmp/* /var/lib/apt/lists/*

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

CMD /run_nordvpn.sh
