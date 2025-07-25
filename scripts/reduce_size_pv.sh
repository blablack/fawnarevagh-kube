#!/bin/bash

# Longhorn PV Resize Script
# This script creates a new smaller PV, copies data, and updates deployments

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
    echo "  -p, --pvc-name          Name of the PVC to resize"
    echo "  -n, --namespace         Namespace (default: default)"
    echo "  -s, --new-size          New size (e.g., 100Mi, 500Mi, 1Gi)"
    echo "  -d, --deployment        Deployment name using the PVC"
    echo "  -c, --storage-class     Storage class (default: longhorn)"
    echo "      --dry-run           Show what would be done without executing"
    echo "  -h, --help              Show this help"
    echo ""
    echo "Example:"
    echo "  $0 -p my-app-data -n production -s 200Mi -d my-app"
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
        -d|--deployment)
            DEPLOYMENT_NAME="$2"
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
if [[ -z "$PVC_NAME" || -z "$NEW_SIZE" || -z "$DEPLOYMENT_NAME" ]]; then
    error "Missing required parameters"
    usage
    exit 1
fi

# Validate new size format
if ! [[ "$NEW_SIZE" =~ ^[0-9]+[MG]i?$ ]]; then
    error "Invalid size format. Use formats like: 100Mi, 500Mi, 1Gi"
    exit 1
fi

NEW_PVC_NAME="${PVC_NAME}-new"
BACKUP_PVC_NAME="${PVC_NAME}-backup"

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
    
    # Check if deployment exists
    if ! kubectl get deployment "$DEPLOYMENT_NAME" -n "$NAMESPACE" &> /dev/null; then
        error "Deployment '$DEPLOYMENT_NAME' not found in namespace '$NAMESPACE'"
        exit 1
    fi
    
    # Get current PVC size
    CURRENT_SIZE=$(kubectl get pvc "$PVC_NAME" -n "$NAMESPACE" -o jsonpath='{.spec.resources.requests.storage}')
    log "Current PVC size: $CURRENT_SIZE"
    log "New PVC size: $NEW_SIZE"
    
    # Get PVC mount path from deployment
    MOUNT_PATH=$(kubectl get deployment "$DEPLOYMENT_NAME" -n "$NAMESPACE" -o jsonpath='{.spec.template.spec.containers[0].volumeMounts[?(@.name=="'$PVC_NAME'")].mountPath}')
    if [[ -z "$MOUNT_PATH" ]]; then
        error "Could not find mount path for PVC '$PVC_NAME' in deployment '$DEPLOYMENT_NAME'"
        exit 1
    fi
    log "Mount path: $MOUNT_PATH"
}

get_actual_usage() {
    log "Checking actual disk usage..."
    
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
    command: ['sh', '-c', 'df -h /data && echo "=== Directory usage ===" && du -sh /data/* 2>/dev/null || echo "No files found" && echo "=== Total usage ===" && du -sh /data']
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

    # Wait for pod to start and complete (but don't wait for "Ready" state)
    log "Waiting for usage check to complete..."
    
    # Wait up to 60 seconds for the pod to complete
    local timeout=60
    local elapsed=0
    while [ $elapsed -lt $timeout ]; do
        local phase=$(kubectl get pod ${TEMP_POD_NAME}-usage -n "$NAMESPACE" -o jsonpath='{.status.phase}' 2>/dev/null || echo "NotFound")
        
        case $phase in
            "Succeeded")
                log "Usage check completed successfully"
                break
                ;;
            "Failed")
                error "Usage check failed"
                kubectl describe pod ${TEMP_POD_NAME}-usage -n "$NAMESPACE"
                kubectl delete pod ${TEMP_POD_NAME}-usage -n "$NAMESPACE" --ignore-not-found=true
                return
                ;;
            "Running"|"Pending"|"ContainerCreating")
                if [ $((elapsed % 10)) -eq 0 ]; then
                    log "Pod status: $phase (waiting...)"
                fi
                ;;
            "NotFound")
                error "Pod not found"
                return
                ;;
        esac
        
        sleep 2
        elapsed=$((elapsed + 2))
    done
    
    if [ $elapsed -ge $timeout ]; then
        warning "Usage check timed out after ${timeout}s"
        kubectl describe pod ${TEMP_POD_NAME}-usage -n "$NAMESPACE"
    fi
    
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
    log "Copying data from old PVC to new PVC..."
    
    if [[ "$DRY_RUN" == "true" ]]; then
        log "[DRY RUN] Would copy data from $PVC_NAME to $NEW_PVC_NAME"
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
    command: ['sh', '-c', 'echo "Starting copy..." && cp -av /old-data/. /new-data/ && sync && echo "Copy completed successfully"']
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
    
    # Wait for pod to start, then follow logs
    log "Waiting for copy pod to start..."
    local timeout=60
    local elapsed=0
    while [ $elapsed -lt $timeout ]; do
        local phase=$(kubectl get pod $TEMP_POD_NAME -n "$NAMESPACE" -o jsonpath='{.status.phase}' 2>/dev/null || echo "NotFound")
        
        if [[ "$phase" == "Running" ]]; then
            log "Copy pod is running, following progress..."
            break
        elif [[ "$phase" == "Failed" ]]; then
            error "Copy pod failed to start"
            kubectl describe pod $TEMP_POD_NAME -n "$NAMESPACE"
            kubectl delete pod $TEMP_POD_NAME -n "$NAMESPACE" --ignore-not-found=true
            exit 1
        fi
        
        if [ $((elapsed % 10)) -eq 0 ]; then
            log "Pod status: $phase (waiting...)"
        fi
        
        sleep 2
        elapsed=$((elapsed + 2))
    done
    
    # Follow logs if pod is running
    if kubectl get pod $TEMP_POD_NAME -n "$NAMESPACE" &>/dev/null; then
        kubectl logs -f $TEMP_POD_NAME -n "$NAMESPACE" &
        LOG_PID=$!
    fi
    
    # Wait for completion
    log "Waiting for copy to complete (this may take a while)..."
    timeout=600
    elapsed=0
    while [ $elapsed -lt $timeout ]; do
        local phase=$(kubectl get pod $TEMP_POD_NAME -n "$NAMESPACE" -o jsonpath='{.status.phase}' 2>/dev/null || echo "NotFound")
        
        case $phase in
            "Succeeded")
                success "Data copy completed successfully"
                break
                ;;
            "Failed")
                error "Data copy failed"
                kubectl logs $TEMP_POD_NAME -n "$NAMESPACE"
                kubectl delete pod $TEMP_POD_NAME -n "$NAMESPACE" --ignore-not-found=true
                exit 1
                ;;
        esac
        
        sleep 5
        elapsed=$((elapsed + 5))
    done
    
    # Kill log following process if it's still running
    if [[ -n "$LOG_PID" ]]; then
        kill $LOG_PID 2>/dev/null || true
    fi
    
    if [ $elapsed -ge $timeout ]; then
        error "Copy operation timed out after ${timeout}s"
        kubectl logs $TEMP_POD_NAME -n "$NAMESPACE"
        kubectl delete pod $TEMP_POD_NAME -n "$NAMESPACE" --ignore-not-found=true
        exit 1
    fi
    
    # Cleanup copy pod
    kubectl delete pod $TEMP_POD_NAME -n "$NAMESPACE" --ignore-not-found=true
}

update_deployment() {
    log "Updating deployment to use new PVC..."
    
    if [[ "$DRY_RUN" == "true" ]]; then
        log "[DRY RUN] Would update deployment $DEPLOYMENT_NAME to use $NEW_PVC_NAME"
        return
    fi
    
    # Scale down deployment
    log "Scaling down deployment..."
    kubectl scale deployment "$DEPLOYMENT_NAME" -n "$NAMESPACE" --replicas=0
    kubectl wait --for=condition=Available=false deployment/$DEPLOYMENT_NAME -n "$NAMESPACE" --timeout=120s
    
    # Update deployment to use new PVC
    log "Updating PVC reference in deployment..."
    kubectl patch deployment "$DEPLOYMENT_NAME" -n "$NAMESPACE" --type='json' \
        -p='[{"op": "replace", "path": "/spec/template/spec/volumes/0/persistentVolumeClaim/claimName", "value": "'$NEW_PVC_NAME'"}]'
    
    # Scale back up
    log "Scaling deployment back up..."
    kubectl scale deployment "$DEPLOYMENT_NAME" -n "$NAMESPACE" --replicas=1
    kubectl wait --for=condition=Available deployment/$DEPLOYMENT_NAME -n "$NAMESPACE" --timeout=120s
    
    success "Deployment updated successfully"
}

backup_old_pvc() {
    log "Renaming old PVC to backup..."
    
    if [[ "$DRY_RUN" == "true" ]]; then
        log "[DRY RUN] Would rename $PVC_NAME to $BACKUP_PVC_NAME"
        return
    fi
    
    # Export old PVC
    kubectl get pvc "$PVC_NAME" -n "$NAMESPACE" -o yaml > "/tmp/${PVC_NAME}-backup.yaml"
    
    # Create backup PVC with different name
    sed "s/name: $PVC_NAME/name: $BACKUP_PVC_NAME/" "/tmp/${PVC_NAME}-backup.yaml" | \
    kubectl apply -f -
    
    log "Old PVC backed up as $BACKUP_PVC_NAME"
}

finalize_rename() {
    log "Finalizing PVC rename..."
    
    if [[ "$DRY_RUN" == "true" ]]; then
        log "[DRY RUN] Would rename $NEW_PVC_NAME to $PVC_NAME"
        return
    fi
    
    # Delete old PVC
    kubectl delete pvc "$PVC_NAME" -n "$NAMESPACE"
    
    # Rename new PVC to original name
    kubectl patch pvc "$NEW_PVC_NAME" -n "$NAMESPACE" --type='json' \
        -p='[{"op": "replace", "path": "/metadata/name", "value": "'$PVC_NAME'"}]'
    
    # Update deployment back to original PVC name
    kubectl patch deployment "$DEPLOYMENT_NAME" -n "$NAMESPACE" --type='json' \
        -p='[{"op": "replace", "path": "/spec/template/spec/volumes/0/persistentVolumeClaim/claimName", "value": "'$PVC_NAME'"}]'
    
    success "PVC resize completed successfully"
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
    log "Starting PVC resize process..."
    log "PVC: $PVC_NAME"
    log "Namespace: $NAMESPACE"
    log "New Size: $NEW_SIZE"
    log "Deployment: $DEPLOYMENT_NAME"
    
    if [[ "$DRY_RUN" == "true" ]]; then
        warning "DRY RUN MODE - No changes will be made"
    fi
    
    # Trap cleanup on exit
    trap cleanup EXIT
    
    check_prerequisites
    get_actual_usage
    
    create_new_pvc
    copy_data
    update_deployment
    
    log "Resize completed! Old PVC is still available as backup."
    log "If everything works correctly, you can delete the old PVC:"
    log "kubectl delete pvc $PVC_NAME -n $NAMESPACE"
    
    success "PVC resize operation completed successfully!"
}

# Run main function
main "$@"
