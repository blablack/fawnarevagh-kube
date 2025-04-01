FROM ubuntu:latest

ARG DEBIAN_FRONTEND=noninteractive

RUN apt-get update -y 
RUN apt-get install -y curl
RUN curl https://repo.nordvpn.com/deb/nordvpn/debian/pool/main/n/nordvpn-release/nordvpn-release_1.0.0_all.deb --output /tmp/nordrepo.deb 
RUN apt-get install -y /tmp/nordrepo.deb 
RUN apt-get update -y 
RUN apt-get dist-upgrade -y
RUN apt-get install -y jq iputils-ping nordvpn=3.17.4
#RUN apt-get install -y jq iputils-ping nordvpn
RUN apt-get remove -y nordvpn-release 
RUN apt-get autoremove -y 
RUN apt-get autoclean -y 
RUN rm -rf /tmp/* /var/cache/apt/archives/* /var/lib/apt/lists/* /var/tmp/* 

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
RUN mkdir /config

CMD /run_nordvpn.sh
