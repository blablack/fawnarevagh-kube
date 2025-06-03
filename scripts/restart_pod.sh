#!/bin/bash

kubectl rollout restart deployment/$1
kubectl rollout status deployment/$1
