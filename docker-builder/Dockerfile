FROM ubuntu:22.04

ENV DEBIAN_FRONTEND noninteractive 

RUN apt update \
    && apt -y dist-upgrade \
	&& apt install -y podman-docker git 

COPY script.sh ./ 
COPY nucio_registry.conf /etc/containers/registries.conf.d/

RUN chmod +x script.sh

CMD ["./script.sh"]