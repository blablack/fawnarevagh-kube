#!/bin/bash
SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" &>/dev/null && pwd)

PV=$(kubectl get pv -o json | jq -r ".items[] | select(.spec.claimRef != null and (.spec.claimRef.name | contains(\"$1\"))) | .metadata.name")
kubectl patch pv $PV -p '{"spec":{"claimRef":null}}'

echo $PV

(
    cd $SCRIPT_DIR/../$1
    for i in *.yaml ; do kubectl apply -f $i ; done
)