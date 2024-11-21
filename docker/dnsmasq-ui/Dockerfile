FROM python:alpine

ENV TZ=Europe/London

RUN apk add --update --no-cache build-base
RUN apk add --no-cache tzdata

WORKDIR /app
COPY ./requirements.txt ./

RUN pip install --no-cache-dir --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt
RUN apk del build-base

COPY ./templates ./templates
COPY ./dnsmasq-leases-ui.py ./

EXPOSE 5000
CMD ["python", "dnsmasq-leases-ui.py"]
