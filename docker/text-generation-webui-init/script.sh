#!/bin/bash

CONFIG_DIRECTORIES=("characters" "loras" "models" "presets" "prompts" "training/datasets" "training/formats")

for config_dir in "${CONFIG_DIRECTORIES[@]}"; do
  target_dir="/home/app/text-generation-webui/$config_dir"

  if [ ! -d "$target_dir" ]; then
    echo "*** Creating directory: '$target_dir' ***"
    mkdir -p "$target_dir"
  fi

  if [ -z "$(ls "$target_dir")" ]; then
    echo "*** Initializing config for: '$config_dir' ***"
    cp -ar "/text-generation-webui/$config_dir"/* "$target_dir"/
  fi
done
