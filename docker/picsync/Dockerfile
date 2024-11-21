FROM python:3.12.6-slim-bookworm

ENV DEBIAN_FRONTEND noninteractive 

RUN apt-get update 
RUN apt-get -y dist-upgrade 
RUN apt-get install -y rsync sshpass python3 inetutils-ping 
RUN apt-get autoremove -y 
RUN apt-get autoclean -y 
RUN rm -rf /tmp/* /var/cache/apt/archives/* /var/lib/apt/lists/* /var/tmp/*

RUN pip install --no-cache-dir --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

RUN pip install -r requirements.txt 

COPY picsync.py ./ 

CMD python3 picsync.py
