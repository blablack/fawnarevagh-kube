#!/bin/sh
set -u

APISERVER="https://kubernetes.default.svc"
TOKEN="$(cat /var/run/secrets/kubernetes.io/serviceaccount/token)"
CACERT=/var/run/secrets/kubernetes.io/serviceaccount/ca.crt
SERVICES="default/jellyfin default/syncthing-aurelien-sync-tcp default/syncthing-aurelien-sync-udp default/syncthing-yvonne-sync-tcp default/syncthing-yvonne-sync-udp"

kget() {
  curl -sS --cacert "$CACERT" -H "Authorization: Bearer $TOKEN" "$APISERVER$1"
}

# Resolve the MAC currently answering ARP for an IP on the LAN, actively
# probing rather than trusting a possibly-stale kernel neighbor cache.
mac_for_ip() {
  arping -c 1 -w 1 "$1" 2>/dev/null | sed -n 's/.*bytes from \([0-9a-fA-F:]*\).*/\1/p' | head -1
}

mismatches=""

for entry in $SERVICES; do
  ns="${entry%%/*}"
  svc="${entry#*/}"

  lb_ip="$(kget "/api/v1/namespaces/$ns/services/$svc" | jq -r '.status.loadBalancer.ingress[0].ip // empty')"
  if [ -z "$lb_ip" ]; then
    echo "$ns/$svc: no LoadBalancer IP yet, skipping"
    continue
  fi

  expected_node="$(kget "/apis/discovery.k8s.io/v1/namespaces/$ns/endpointslices?labelSelector=kubernetes.io/service-name=$svc" \
    | jq -r '[.items[].endpoints[] | select(.conditions.ready==true) | .nodeName] | first // empty')"
  if [ -z "$expected_node" ]; then
    echo "$ns/$svc: no ready endpoint, skipping"
    continue
  fi

  expected_node_ip="$(kget "/api/v1/nodes/$expected_node" | jq -r '.status.addresses[] | select(.type=="InternalIP") | .address')"
  expected_mac="$(mac_for_ip "$expected_node_ip")"
  vip_mac="$(mac_for_ip "$lb_ip")"

  if [ -z "$expected_mac" ] || [ -z "$vip_mac" ]; then
    echo "$ns/$svc: couldn't resolve a MAC this run (expected_node_ip=$expected_node_ip expected_mac=$expected_mac vip_mac=$vip_mac), skipping"
    continue
  fi

  if [ "$expected_mac" != "$vip_mac" ]; then
    echo "$ns/$svc: MISMATCH - VIP $lb_ip is answered by $vip_mac but should be $expected_node ($expected_mac)"
    mismatches="$mismatches $ns/$svc($lb_ip)"
  else
    echo "$ns/$svc: OK - VIP $lb_ip correctly answered by $expected_node"
  fi
done

if [ -n "$mismatches" ]; then
  echo "Restarting metallb speaker DaemonSet to clear:$mismatches"
  ts="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  patch_status="$(curl -sS -o /dev/null -w '%{http_code}' --cacert "$CACERT" -H "Authorization: Bearer $TOKEN" \
    -H 'Content-Type: application/strategic-merge-patch+json' -X PATCH \
    "$APISERVER/apis/apps/v1/namespaces/metallb-system/daemonsets/speaker" \
    -d "{\"spec\":{\"template\":{\"metadata\":{\"annotations\":{\"kubectl.kubernetes.io/restartedAt\":\"$ts\"}}}}}")"
  echo "patch response: $patch_status"
  curl -sS -H "Tags: warning" -H "Priority: high" \
    -d "MetalLB ARP owner mismatch, restarted speaker daemonset. Affected:$mismatches" \
    "http://ntfy.default.svc.cluster.local/metallb-healthcheck" || true
fi
