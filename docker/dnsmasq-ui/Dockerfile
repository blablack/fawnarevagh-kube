FROM ubuntu:23.10

ENV DEBIAN_FRONTEND noninteractive 

RUN mkdir /dnsmasq-ui
WORKDIR /dnsmasq-ui

RUN apt-get update 
RUN apt-get -y dist-upgrade 

RUN apt-get install -y git

RUN git pull https://github.com/julianscheel/dnsmasq.leaseui.git

RUN apt-get install -y golang-go ragel

RUN apt-get autoremove -y 
RUN apt-get autoclean -y 

RUN rm -rf /tmp/* /var/cache/apt/archives/* /var/lib/apt/lists/* /var/tmp/*

COPY script.sh /dnsmasq-ui
RUN chmod +x script.sh

EXPOSE 80 80/tcp 

ENTRYPOINT ["script.sh"]
