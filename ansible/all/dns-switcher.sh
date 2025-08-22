#!/bin/bash
while true; do
    if nc -zv 192.168.2.201 53 2>/dev/null; then
        # Pi-hole is up, use it
        current_dns=$(grep "^DNS=" /etc/systemd/resolved.conf | cut -d= -f2)
        if [ "$current_dns" != "192.168.2.201 192.168.2.202" ]; then
            sed -i 's/^DNS=.*/DNS=192.168.2.201 192.168.2.202/' /etc/systemd/resolved.conf
            systemctl restart systemd-resolved
            sleep 15
            kubectl -n kube-system rollout restart deployment coredns
        fi
    else
        # Pi-hole is down, use fallback
        current_dns=$(grep "^DNS=" /etc/systemd/resolved.conf | cut -d= -f2)
        if [ "$current_dns" != "1.1.1.1 1.0.0.1" ]; then
            sed -i 's/^DNS=.*/DNS=1.1.1.1 1.0.0.1/' /etc/systemd/resolved.conf
            systemctl restart systemd-resolved
            sleep 15
            kubectl -n kube-system rollout restart deployment coredns
        fi
    fi
    sleep 3
done