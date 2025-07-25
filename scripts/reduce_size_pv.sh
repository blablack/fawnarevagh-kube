#!/bin/bash

# Simplified PV Data Copy Script
# This script creates a new smaller PV, copies data, then cleans up the new PVC while keeping the PV

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
TEMP_POD_NAME="pv-copy-temp"
COPY_IMAGE="alpine:latest"

usage() {
    echo "Usage: $0 [OPTIONS]"
    echo "Options:"
    echo "  -p, --pvc-name          Name of the source PVC to copy from"
    echo "  -n, --namespace         Namespace (default: default)"
    echo "  -s, --new-size          New PV size (e.g., 100Mi, 500Mi, 1Gi)"
    echo "  -c, --storage-class     Storage class (default: longhorn)"
    echo "      --dry-run           Show what would be done without executing"
    echo "  -h, --help              Show this help"
    echo ""
    echo "Example:"
    echo "  $0 -p my-app-data -n production -s 200Mi"
}

log() {
    echo -e "${BLUE}[$(date +'%Y-%m-%d %H:%M:%S')]${NC} $1"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1" >&2
}

success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -p|--pvc-name)
            PVC_NAME="$2"
            shift 2
            ;;
        -n|--namespace)
            NAMESPACE="$2"
            shift 2
            ;;
        -s|--new-size)
            NEW_SIZE="$2"
            shift 2
            ;;
        -c|--storage-class)
            STORAGE_CLASS="$2"
            shift 2
            ;;
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            error "Unknown option $1"
            usage
            exit 1
            ;;
    esac
done

# Set defaults
NAMESPACE=${NAMESPACE:-default}
STORAGE_CLASS=${STORAGE_CLASS:-longhorn}
DRY_RUN=${DRY_RUN:-false}

# Validate required parameters
if [[ -z "$PVC_NAME" || -z "$NEW_SIZE" ]]; then
    error "Missing required parameters"
    usage
    exit 1
fi

# Validate new size format
if ! [[ "$NEW_SIZE" =~ ^[0-9]+[MG]i?$ ]]; then
    error "Invalid size format. Use formats like: 100Mi, 500Mi, 1Gi"
    exit 1
fi

NEW_PVC_NAME="${PVC_NAME}-new-$(date +%s)"

check_prerequisites() {
    log "Checking prerequisites..."
    
    # Check if kubectl is available
    if ! command -v kubectl &> /dev/null; then
        error "kubectl is not installed or not in PATH"
        exit 1
    fi
    
    # Check if PVC exists
    if ! kubectl get pvc "$PVC_NAME" -n "$NAMESPACE" &> /dev/null; then
        error "PVC '$PVC_NAME' not found in namespace '$NAMESPACE'"
        exit 1
    fi
    
    # Get current PVC size
    CURRENT_SIZE=$(kubectl get pvc "$PVC_NAME" -n "$NAMESPACE" -o jsonpath='{.spec.resources.requests.storage}')
    log "Current PVC size: $CURRENT_SIZE"
    log "New PV size: $NEW_SIZE"
}

show_disk_usage() {
    log "Checking current disk usage..."
    
    # Create a temporary pod to check usage
    cat << EOF | kubectl apply -f -
apiVersion: v1
kind: Pod
metadata:
  name: ${TEMP_POD_NAME}-usage
  namespace: $NAMESPACE
spec:
  containers:
  - name: usage-checker
    image: $COPY_IMAGE
    command: ['sh', '-c', 'df -h /data && echo "=== Directory usage (excluding lost+found) ===" && du -sh /data/* 2>/dev/null | grep -v "/data/lost+found" || echo "No files found" && echo "=== Total usage ===" && du -sh /data']
    volumeMounts:
    - name: data
      mountPath: /data
  volumes:
  - name: data
    persistentVolumeClaim:
      claimName: $PVC_NAME
  restartPolicy: Never
EOF

    if [[ "$DRY_RUN" == "true" ]]; then
        log "[DRY RUN] Would check disk usage for PVC: $PVC_NAME"
        kubectl delete pod ${TEMP_POD_NAME}-usage -n "$NAMESPACE" --ignore-not-found=true
        return
    fi

    # Wait for pod to complete
    log "Waiting for usage check to complete..."
    kubectl wait --for=condition=Ready pod/${TEMP_POD_NAME}-usage -n "$NAMESPACE" --timeout=60s 2>/dev/null || true
    sleep 3
    
    # Get usage info
    log "Current disk usage:"
    echo "----------------------------------------"
    kubectl logs ${TEMP_POD_NAME}-usage -n "$NAMESPACE" 2>/dev/null || log "Could not retrieve usage logs"
    echo "----------------------------------------"
    
    # Cleanup
    kubectl delete pod ${TEMP_POD_NAME}-usage -n "$NAMESPACE" --ignore-not-found=true
}

create_new_pvc() {
    log "Creating new PVC with size $NEW_SIZE..."
    
    if [[ "$DRY_RUN" == "true" ]]; then
        log "[DRY RUN] Would create PVC: $NEW_PVC_NAME"
        return
    fi
    
    cat << EOF | kubectl apply -f -
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: $NEW_PVC_NAME
  namespace: $NAMESPACE
spec:
  accessModes:
    - ReadWriteOnce
  resources:
    requests:
      storage: $NEW_SIZE
  storageClassName: $STORAGE_CLASS
EOF
    
    # Wait for PVC to be bound
    log "Waiting for new PVC to be bound..."
    kubectl wait --for=jsonpath='{.status.phase}'=Bound pvc/$NEW_PVC_NAME -n "$NAMESPACE" --timeout=120s
    success "New PVC created and bound"
}

copy_data() {
    log "Copying data from old PVC to new PV (excluding lost+found folder)..."
    
    if [[ "$DRY_RUN" == "true" ]]; then
        log "[DRY RUN] Would copy data from $PVC_NAME to $NEW_PVC_NAME (excluding lost+found)"
        return
    fi
    
    cat << EOF | kubectl apply -f -
apiVersion: v1
kind: Pod
metadata:
  name: $TEMP_POD_NAME
  namespace: $NAMESPACE
spec:
  containers:
  - name: data-copier
    image: $COPY_IMAGE
    securityContext:
      runAsUser: 0
      runAsGroup: 0
    command: ['sh', '-c', '
      echo "Installing rsync..." && 
      apk add --no-cache rsync && 
      echo "Starting copy process..." && 
      echo "Source data:" && 
      ls -la /old-data/ && 
      echo "Copying with rsync (excluding lost+found)..." && 
      rsync -avH --numeric-ids --exclude="lost+found" /old-data/ /new-data/ && 
      sync && 
      echo "Copy completed. New data:" && 
      ls -la /new-data/ && 
      echo "Disk usage:" && 
      df -h /new-data && 
      echo "Verification - files copied:" && 
      find /new-data -type f | wc -l && 
      echo "lost+found exclusion confirmed - checking if lost+found exists in source:" && 
      if [ -d "/old-data/lost+found" ]; then echo "lost+found exists in source but was excluded"; else echo "No lost+found folder in source"; fi
    ']
    volumeMounts:
    - name: old-data
      mountPath: /old-data
    - name: new-data
      mountPath: /new-data
  volumes:
  - name: old-data
    persistentVolumeClaim:
      claimName: $PVC_NAME
  - name: new-data
    persistentVolumeClaim:
      claimName: $NEW_PVC_NAME
  restartPolicy: Never
EOF
    
    # Wait for pod to start
    log "Waiting for copy pod to start..."
    kubectl wait --for=condition=Ready pod/$TEMP_POD_NAME -n "$NAMESPACE" --timeout=60s 2>/dev/null || true
    
    # Follow logs
    log "Following copy progress..."
    kubectl logs -f $TEMP_POD_NAME -n "$NAMESPACE" &
    LOG_PID=$!
    
    # Wait for pod to complete (change this line)
    log "Waiting for copy to complete..."
    kubectl wait --for=condition=Ready=false pod/$TEMP_POD_NAME -n "$NAMESPACE" --timeout=600s || true
    
    # Wait a bit more to ensure the pod fully transitions to completed state
    sleep 5
    
    # Kill log following process
    if [[ -n "$LOG_PID" ]]; then
        kill $LOG_PID 2>/dev/null || true
    fi
    
    # Check if copy was successful - try multiple times
    local phase
    for i in {1..10}; do
        phase=$(kubectl get pod $TEMP_POD_NAME -n "$NAMESPACE" -o jsonpath='{.status.phase}' 2>/dev/null || echo "Unknown")
        if [[ "$phase" == "Succeeded" ]]; then
            break
        fi
        log "Waiting for pod to reach Succeeded state... (attempt $i/10, current: $phase)"
        sleep 2
    done
    
    if [[ "$phase" == "Succeeded" ]]; then
        success "Data copy completed successfully (lost+found folder excluded)"
    else
        # Check the exit code of the container to see if it actually succeeded
        local exit_code=$(kubectl get pod $TEMP_POD_NAME -n "$NAMESPACE" -o jsonpath='{.status.containerStatuses[0].state.terminated.exitCode}' 2>/dev/null || echo "unknown")
        if [[ "$exit_code" == "0" ]]; then
            success "Data copy completed successfully (container exit code: 0)"
        else
            error "Data copy failed with pod status: $phase, exit code: $exit_code"
            kubectl logs $TEMP_POD_NAME -n "$NAMESPACE"
            exit 1
        fi
    fi
    
    # Cleanup copy pod
    kubectl delete pod $TEMP_POD_NAME -n "$NAMESPACE" --ignore-not-found=true
}

get_pv_name() {
    log "Getting PV name for the new PVC..."
    
    if [[ "$DRY_RUN" == "true" ]]; then
        log "[DRY RUN] Would get PV name for $NEW_PVC_NAME"
        NEW_PV_NAME="pvc-example-uuid"
        return
    fi
    
    NEW_PV_NAME=$(kubectl get pvc "$NEW_PVC_NAME" -n "$NAMESPACE" -o jsonpath='{.spec.volumeName}')
    if [[ -z "$NEW_PV_NAME" ]]; then
        error "Could not get PV name for PVC $NEW_PVC_NAME"
        exit 1
    fi
    
    log "New PV name: $NEW_PV_NAME"
}

delete_pvc_keep_pv() {
    log "Deleting new PVC while keeping the PV..."
    
    if [[ "$DRY_RUN" == "true" ]]; then
        log "[DRY RUN] Would delete PVC $NEW_PVC_NAME and update PV $NEW_PV_NAME policy"
        return
    fi
    
    # Change PV reclaim policy to Retain (if not already)
    log "Setting PV reclaim policy to Retain..."
    kubectl patch pv "$NEW_PV_NAME" -p '{"spec":{"persistentVolumeReclaimPolicy":"Retain"}}'
    
    # Delete the PVC
    log "Deleting PVC $NEW_PVC_NAME..."
    kubectl delete pvc "$NEW_PVC_NAME" -n "$NAMESPACE"
    
    # Wait a moment for the PV status to update
    log "Waiting for PV status to update..."
    sleep 5
    
    # Clear the claimRef to make PV available again
    log "Clearing PV claimRef to make it available for new claims..."
    kubectl patch pv "$NEW_PV_NAME" -p '{"spec":{"claimRef":null}}'
    
    # Verify PV is now Available
    local pv_status
    for i in {1..10}; do
        pv_status=$(kubectl get pv "$NEW_PV_NAME" -o jsonpath='{.status.phase}')
        if [[ "$pv_status" == "Available" ]]; then
            break
        fi
        log "Waiting for PV to become Available... (attempt $i/10)"
        sleep 2
    done
    
    if [[ "$pv_status" == "Available" ]]; then
        success "PVC deleted, PV $NEW_PV_NAME is now Available for reuse"
    else
        warning "PV $NEW_PV_NAME status is '$pv_status' instead of 'Available'"
        log "You may need to manually verify the PV status"
    fi
}

cleanup() {
    log "Cleaning up temporary resources..."
    
    if [[ "$DRY_RUN" == "true" ]]; then
        log "[DRY RUN] Would clean up temporary resources"
        return
    fi
    
    # Remove any remaining temporary pods
    kubectl delete pod $TEMP_POD_NAME -n "$NAMESPACE" --ignore-not-found=true 2>/dev/null || true
    kubectl delete pod ${TEMP_POD_NAME}-usage -n "$NAMESPACE" --ignore-not-found=true 2>/dev/null || true
    
    # Kill any background log processes
    if [[ -n "$LOG_PID" ]]; then
        kill $LOG_PID 2>/dev/null || true
    fi
}

main() {
    log "Starting PV data copy process..."
    log "Source PVC: $PVC_NAME"
    log "Namespace: $NAMESPACE"
    log "New PV Size: $NEW_SIZE"
    log "Note: lost+found folder will be excluded from copy"
    
    if [[ "$DRY_RUN" == "true" ]]; then
        warning "DRY RUN MODE - No changes will be made"
    fi
    
    # Trap cleanup on exit
    trap cleanup EXIT
    
    check_prerequisites
    show_disk_usage
    create_new_pvc
    copy_data
    get_pv_name
    delete_pvc_keep_pv
    
    success "Data copy completed successfully!"
    echo ""
    log "Summary:"
    log "- Data copied from PVC '$PVC_NAME' to PV '$NEW_PV_NAME' (excluding lost+found)"
    log "- New PV size: $NEW_SIZE"
    log "- PV '$NEW_PV_NAME' is Available and ready for use"
    echo ""
    log "Next steps (manual):"
    log "1. Update your deployment to use a new PVC that claims PV '$NEW_PV_NAME'"
    log "2. Test your application"
    log "3. Delete the old PVC '$PVC_NAME' when satisfied"
    echo ""
    log "Example PVC to claim the new PV:"
    echo "---"
    cat << EOF
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: $PVC_NAME
  namespace: $NAMESPACE
spec:
  accessModes:
    - ReadWriteOnce
  resources:
    requests:
      storage: $NEW_SIZE
  storageClassName: $STORAGE_CLASS
  volumeName: $NEW_PV_NAME
EOF
    echo "---"
}

# Run main function
main "$@"