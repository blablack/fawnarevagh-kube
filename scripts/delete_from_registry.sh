#!/bin/bash

# Check if image argument is provided
if [ $# -eq 0 ]; then
    echo "Usage: $0 <image-name>"
    echo "Example: $0 public/bitnami/postgresql"
    exit 1
fi

# Image to be deleted (from first argument)
image="$1"

# Function to delete an image using its digest
delete_image() {
  local image=$1
  local tag=$2
  echo "Deleting image: $image:$tag"
  digest=$(curl -I -s -H "Accept: application/vnd.docker.distribution.manifest.v2+json" "http://nucio.nowhere:30038/v2/$image/manifests/$tag" | grep Docker-Content-Digest | awk '{print $2}' | tr -d '\r')
  if [ -z "$digest" ]; then
    echo "Error: Digest not found for image $image:$tag"
    return 1
  fi
  curl -X DELETE "http://nucio.nowhere:30038/v2/$image/manifests/$digest"
}

# Function to get all tags for an image
get_tags() {
  local image=$1
  curl -s "http://nucio.nowhere:30038/v2/$image/tags/list" | jq -r '.tags[]'
}

# Prompt user for confirmation
read -p "Are you sure you want to delete image '$image' and all its tags? Type 'yes' to confirm: " confirmation

if [ "$confirmation" == "yes" ]; then
  echo "Getting tags for image: $image"
  tags=$(get_tags "$image")
  
  if [ -z "$tags" ]; then
    echo "No tags found for image: $image"
    exit 1
  fi
  
  for tag in $tags; do
    delete_image "$image" "$tag"
  done
  
  echo "Image $image deleted successfully."
  
  # Run garbage collection
  echo "Running garbage collection..."
  kubectl -n kube-system exec -it deployment/docker-registry -- registry garbage-collect /etc/docker/registry/config.yml
  
  # Remove repository folder
  echo "Removing repository directory..."
  kubectl -n kube-system exec -it deployment/docker-registry -- rm -r "/data/docker/registry/v2/repositories/$image"
  echo "Deleted directory for image: $image"
  
  # Show final view of the catalog
  echo "Current registry catalog:"
  curl -X GET http://nucio.nowhere:30038/v2/_catalog | jq
else
  echo "Operation cancelled."
fi