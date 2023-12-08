FROM python:3.11.7-alpine

RUN apk add --update --no-cache build-base

WORKDIR /app
COPY ./requirements.txt ./

RUN pip install -r requirements.txt 
RUN apk del build-base

COPY ./templates ./templates
COPY ./dnsmasq-leases-ui.py ./

EXPOSE 5000
CMD ["python", "dnsmasq-leases-ui.py"]
