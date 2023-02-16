FROM ubuntu:22.10

ENV DEBIAN_FRONTEND noninteractive 

RUN apt-get update 
RUN apt-get -y dist-upgrade 
RUN apt-get install -y wget
RUN apt-get autoremove -y 
RUN apt-get autoclean -y 
RUN rm -rf /tmp/* /var/cache/apt/archives/* /var/lib/apt/lists/* /var/tmp/*

COPY script.sh ./ 

RUN chmod +x script.sh

CMD ./script.sh
