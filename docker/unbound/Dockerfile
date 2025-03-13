FROM mvance/unbound:latest

RUN apt-get update && \
    apt-get install -y --no-install-recommends wget && \
    apt-get clean && \
    wget https://www.internic.net/domain/named.root -qO- | tee /opt/unbound/etc/unbound/root.hints && \
    chmod _unbound:_unbound /opt/unbound/etc/unbound/root.hints && \
    apt-get purge -y --auto-remove wget && \
    rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

