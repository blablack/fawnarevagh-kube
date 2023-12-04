FROM ubuntu:23.10

ENV DEBIAN_FRONTEND noninteractive 

COPY dnsmasq.leaseui /dnsmasq.leaseui
WORKDIR /dnsmasq.leaseui

RUN apt-get update 
RUN apt-get -y dist-upgrade 

RUN apt-get install -y golang-go ragel

RUN rm -rf /tmp/* /var/cache/apt/archives/* /var/lib/apt/lists/* /var/tmp/*

COPY script.sh /dnsmasq.leaseui
RUN chmod +x script.sh

EXPOSE 80 80/tcp 

ENTRYPOINT ["script.sh"]
