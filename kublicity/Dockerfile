FROM ubuntu:22.04

ENV DEBIAN_FRONTEND noninteractive 

RUN apt update \
    && apt -y dist-upgrade \
	&& apt install -y duplicity 

CMD ["duplicity", "/data", "file:///backup/DejaDupNucio", "--no-encryption", "--allow-source-mismatch"]