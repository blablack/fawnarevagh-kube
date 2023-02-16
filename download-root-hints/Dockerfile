FROM ubuntu:22.10

ENV DEBIAN_FRONTEND noninteractive 

RUN apt-get update 
RUN apt-get -y dist-upgrade 
RUN apt-get install -y wget
RUN apt-get autoremove -y 
RUN apt-get autoclean -y 
RUN rm -rf /tmp/* /var/cache/apt/archives/* /var/lib/apt/lists/* /var/tmp/*

CMD wget https://www.internic.net/domain/named.root -qO- | sudo tee /tmp/unbound_config/root.hints
