FROM alpine:latest

ENV TZ=Europe/London

RUN apk add --no-cache dnsmasq
RUN apk add --no-cache tzdata

EXPOSE 53 53/udp 67/udp

ENTRYPOINT ["/usr/sbin/dnsmasq", "--no-daemon"]
