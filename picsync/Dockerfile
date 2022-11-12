FROM ubuntu:22.04

ENV DEBIAN_FRONTEND noninteractive 

RUN apt update \
    && apt -y dist-upgrade \
	&& apt install -y rsync sshpass python3 inetutils-ping \
    && apt autoremove -y \
    && apt autoclean -y \
    && rm -rf \
	    /tmp/* \
		/var/cache/apt/archives/* \
		/var/lib/apt/lists/* \
		/var/tmp/*

COPY picsync.py ./ 

CMD python3 picsync.py