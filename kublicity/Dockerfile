FROM ubuntu:22.04

ENV DEBIAN_FRONTEND noninteractive 

RUN apt update \
    && apt -y dist-upgrade \
	&& apt install -y duplicity \
    && apt-get autoremove -y \
    && apt-get autoclean -y \
    && rm -rf \
	    /tmp/* \
		/var/cache/apt/archives/* \
		/var/lib/apt/lists/* \
		/var/tmp/*

CMD ["duplicity", "/data", "file:///backup/DejaDupNucio", "--no-encryption", "--allow-source-mismatch"]