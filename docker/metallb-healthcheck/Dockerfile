FROM alpine:latest

RUN apk add --no-cache curl jq iputils-arping

COPY check.sh /check.sh
RUN chmod +x /check.sh

CMD ["/check.sh"]
