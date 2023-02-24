FROM ubuntu:22.10

ARG DEBIAN_FRONTEND=noninteractive

RUN apt-get update -y 
RUN apt dist-upgrade -y

RUN apt install -y nfs-kernel-server

RUN apt-get autoremove -y 
RUN apt-get autoclean -y 
RUN rm -rf /tmp/* /var/cache/apt/archives/* /var/lib/apt/lists/* /var/tmp/* 

RUN mkdir -p /var/lib/nfs/rpc_pipefs /var/lib/nfs/v4recovery 
RUN echo "rpc_pipefs    /var/lib/nfs/rpc_pipefs rpc_pipefs      defaults        0       0" >> /etc/fstab 
RUN echo "nfsd  /proc/fs/nfsd   nfsd    defaults        0       0" >> /etc/fstab

COPY exports /etc/
COPY nfsd.sh /usr/bin/nfsd.sh

RUN chmod +x /usr/bin/nfsd.sh

ENTRYPOINT ["/usr/bin/nfsd.sh"]