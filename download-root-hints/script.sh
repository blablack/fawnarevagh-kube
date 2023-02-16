#!/bin/bash

wget https://www.internic.net/domain/named.root -qO- | sudo tee /tmp/unbound_config/root.hints
