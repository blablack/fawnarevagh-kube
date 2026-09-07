#!/bin/bash

# Check if image argument is provided
if [ $# -eq 0 ]; then
    echo "Usage: $0 <image-name>"
    echo "Example: $0 public/bitnami/postgresql"
    exit 1
fi

# Image to be deleted (from first argument)
image="$1"

# Every image in this registry is pushed by buildah, which writes OCI manifests
# by default. Accepting only the Docker v2 schema makes the digest lookup 404,
# so the API delete below silently never runs and the blobs are left orphaned.
ACCEPT_MANIFESTS="application/vnd.oci.image.manifest.v1+json, application/vnd.oci.image.index.v1+json, application/vnd.docker.distribution.manifest.v2+json, application/vnd.docker.distribution.manifest.list.v2+json"

# Function to delete an image using its digest
delete_image() {
  local image=$1
  local tag=$2
  echo "Deleting image: $image:$tag"
  digest=$(curl -I -s -H "Accept: $ACCEPT_MANIFESTS" "http://nucio.nowhere:30038/v2/$image/manifests/$tag" | grep -i Docker-Content-Digest | awk '{print $2}' | tr -d '\r')
  if [ -z "$digest" ]; then
    echo "Error: Digest not found for image $image:$tag"
    return 1
  fi
  curl -f -X DELETE "http://nucio.nowhere:30038/v2/$image/manifests/$digest"
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
  
  failed=0
  for tag in $tags; do
    delete_image "$image" "$tag" || failed=1
  done

  if [ "$failed" -ne 0 ]; then
    echo "Error: at least one tag failed to delete via the registry API - aborting."
    echo "Nothing was garbage-collected and the repository directory was left in place."
    exit 1
  fi

  echo "Image $image deleted successfully."

  # Remove repository folder BEFORE garbage collection: while the directory is
  # still there the collector treats this image's manifests/blobs as live and
  # reclaims nothing, leaving them orphaned on disk.
  echo "Removing repository directory..."
  kubectl -n kube-system exec deployment/docker-registry -- rm -r "/data/docker/registry/v2/repositories/$image"
  echo "Deleted directory for image: $image"

  # Run garbage collection
  echo "Running garbage collection..."
  kubectl -n kube-system exec deployment/docker-registry -- registry garbage-collect /etc/docker/registry/config.yml

  # Show final view of the catalog
  echo "Current registry catalog:"
  curl -X GET http://nucio.nowhere:30038/v2/_catalog | jq
else
  echo "Operation cancelled."
fi