FROM ubuntu:23.10

ENV DEBIAN_FRONTEND noninteractive 

RUN apt-get update 
RUN apt-get -y dist-upgrade 

RUN apt-get install -y dnsmasq

RUN apt-get autoremove -y 
RUN apt-get autoclean -y 

RUN rm -rf /tmp/* /var/cache/apt/archives/* /var/lib/apt/lists/* /var/tmp/*

EXPOSE 53 53/udp 67/udp

ENTRYPOINT ["/usr/sbin/dnsmasq"]
CMD ["--keep-in-foreground"]
