FROM ubuntu:22.10

ENV DEBIAN_FRONTEND noninteractive 

RUN apt-get update 
RUN apt-get -y dist-upgrade 

RUN apt-get install -y ca-certificates curl gnupg lsb-release

RUN mkdir -m 0755 -p /etc/apt/keyrings
RUN curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg

RUN echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null

RUN apt-get update 

RUN apt-get install -y podman docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin git 
RUN apt-get autoremove -y 
RUN apt-get autoclean -y 
RUN rm -rf /tmp/* /var/cache/apt/archives/* /var/lib/apt/lists/* /var/tmp/*

COPY script.sh ./ 
COPY daemon.json /etc/docker/
COPY storage.conf /etc/containers/

RUN chmod +x script.sh

CMD ./script.sh
