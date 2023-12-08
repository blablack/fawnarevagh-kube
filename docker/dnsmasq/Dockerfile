FROM alpine:latest

RUN apt-get install -y dnsmasq

EXPOSE 53 53/udp 67/udp

ENTRYPOINT ["/usr/sbin/dnsmasq", "--no-daemon"]
