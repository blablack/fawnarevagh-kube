FROM ubuntu:23.04

ENV DEBIAN_FRONTEND noninteractive 

RUN apt-get update 
RUN apt-get -y dist-upgrade 
RUN apt-get install -y duplicity 
RUN apt-get autoremove -y 
RUN apt-get autoclean -y 
RUN rm -rf /tmp/* /var/cache/apt/archives/* /var/lib/apt/lists/* /var/tmp/*

CMD duplicity /data file:///backup/DejaDupNucio --no-encryption --allow-source-mismatch --verbosity 8
