FROM python:slim

ENV DEBIAN_FRONTEND=noninteractive

#RUN groupadd --gid 1001 picsync && \
#    useradd --uid 1001 --gid picsync --create-home picsync

#WORKDIR /home/picsync

RUN apt-get update && \
    apt-get install -y rsync sshpass inetutils-ping
    #apt-get install -y rsync sshpass inetutils-ping && \
#    rm -rf /tmp/* /var/cache/apt/archives/* /var/lib/apt/lists/* /var/tmp/*

#COPY requirements.txt /home/picsync

#RUN pip install --no-cache-dir --upgrade pip && \
#    pip install --no-cache-dir -r requirements.txt

#COPY picsync.py /home/picsync

#USER picsync:picsync

#CMD ["python3", "picsync.py"]
