#!/bin/bash

CONFIG_DIRECTORIES=("characters" "loras" "models" "presets" "prompts" "training/datasets" "training/formats")

for config_dir in "${CONFIG_DIRECTORIES[@]}"; do
  if [ -z "$(ls /home/app/text-generation-webui/"$config_dir")" ]; then
    echo "*** Initialising config for: '$config_dir' ***"
    cp -ar /text-generation-webui/"$config_dir"/* /home/app/text-generation-webui/"$config_dir"/
  fi
done
