FROM ubuntu:24.04

ARG DEBIAN_FRONTEND=noninteractive

RUN apt-get update -y 

RUN apt-get install -y git
RUN git clone https://github.com/oobabooga/text-generation-webui.git

RUN apt-get remove -y git
RUN apt-get dist-upgrade -y 
RUN apt-get autoremove -y 
RUN apt-get autoclean -y 
RUN rm -rf /tmp/* /var/cache/apt/archives/* /var/lib/apt/lists/* /var/tmp/* 

COPY script.sh / 
RUN chmod +x script.sh

CMD /script.sh
