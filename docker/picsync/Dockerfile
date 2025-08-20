FROM python:alpine

RUN addgroup -g 1001 picsync && \
    adduser -u 1001 -G picsync -h /home/picsync -s /bin/sh -D picsync

WORKDIR /home/picsync

RUN apk add --no-cache rsync sshpass iputils

COPY requirements.txt /home/picsync

RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

COPY picsync.py /home/picsync

USER picsync:picsync

CMD ["python3", "picsync.py"]