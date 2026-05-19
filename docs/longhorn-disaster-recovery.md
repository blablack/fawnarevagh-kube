# Longhorn Disaster Recovery

Full cluster loss scenario — restoring Longhorn volumes from backup.

## Steps

1. Set up a new Kubernetes cluster (see README for k3s install via Ansible)

2. Install Longhorn on the new cluster:
```bash
kubectl apply -f https://raw.githubusercontent.com/longhorn/longhorn/master/deploy/longhorn.yaml
```

3. Configure the same backup target settings as the original cluster (S3 credentials and endpoint) so Longhorn can reach the backups

4. List available backups:
```bash
kubectl -n longhorn-system get backupvolume
```

5. Restore a volume — via UI or CLI:

**UI:** Backup page → find backup → Restore → specify new volume name

**CLI:**
```bash
kubectl create -f - <<EOF
apiVersion: longhorn.io/v1beta1
kind: Volume
metadata:
  name: restore-volume-name
  namespace: longhorn-system
spec:
  fromBackup: backupstore-url/backup-volume/backup-name
  numberOfReplicas: 3
  size: "size-of-original-volume"
EOF
```

6. Create a PVC bound to the restored volume:
```yaml
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: restored-pvc
spec:
  accessModes:
    - ReadWriteOnce
  storageClassName: longhorn
  resources:
    requests:
      storage: size-of-volume
  volumeName: name-of-restored-pv
```

7. Update application manifests to reference the restored PVC

## Checklist

- New cluster has enough storage capacity
- Backup target is reachable from the new cluster
- Restored volumes have correct access permissions
- Test restore periodically — don't wait for a real disaster
