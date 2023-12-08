FROM alpine:latest

RUN apk add --no-cache wget

CMD wget https://www.internic.net/domain/named.root -qO- | tee /tmp/unbound_config/root.hints
