#!/bin/bash
(
    git clone https://github.com/kubernetes/autoscaler.git
    cd autoscaler/vertical-pod-autoscaler/
    ./pkg/admission-controller/gencerts.sh
    ./hack/vpa-up.sh
    cd ../../
    rm -rf autoscaler
)