FROM ubuntu:22.10

ENV DEBIAN_FRONTEND noninteractive 

RUN apt-get update 
RUN apt-get -y dist-upgrade 
RUN apt-get install -y podman-docker git 
RUN apt-get autoremove -y 
RUN apt-get autoclean -y 
RUN rm -rf /tmp/* /var/cache/apt/archives/* /var/lib/apt/lists/* /var/tmp/*

COPY script.sh ./ 
COPY nucio_registry.conf /etc/containers/registries.conf.d/
COPY storage.conf /etc/containers/

RUN chmod +x script.sh

CMD ./script.sh
