FROM alpine:latest

RUN apk add --no-cache dnsmasq

EXPOSE 53 53/udp 67/udp

ENTRYPOINT ["/usr/sbin/dnsmasq", "--no-daemon"]
