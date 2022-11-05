#!/bin/bash

# clone or pull repo
if [ -d "fawnarevagh-kube" ] 
then
    (cd fawnarevagh-kube ; git pull)
else
    git clone https://github.com/blablack/fawnarevagh-kube.git
fi

(
    cd fawnarevagh-kube/kublicity 
    docker build -t kublicity . 
    docker tag kublicity:latest nucio.nowhere:30038/kublicity:latest
    docker push nucio.nowhere:30038/kublicity:latest
)

(
    cd fawnarevagh-kube/picsync 
    docker build -t picsync . 
    docker tag picsync:latest nucio.nowhere:30038/picsync:latest
    docker push nucio.nowhere:30038/picsync:latest
)
