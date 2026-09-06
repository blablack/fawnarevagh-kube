# Longhorn Disaster Recovery

Full cluster loss scenario — restoring Longhorn volumes from backup.

## Backups already exist

This cluster already has a working Longhorn backup target and recurring backup schedule,
configured live on the cluster (via the Longhorn UI / kubectl) — **not** tracked in this repo's
manifests, so a from-scratch cluster rebuild needs it reconfigured manually (step 3 below) before
backups resume.

- **Backup target**: `nfs://192.168.2.4:/volume1/public/MyBackup/Longhorn` — an NFS export on the
  NAS (`nasio`), the same one that backs `nasio-nfs-pvc` elsewhere in this cluster, under a
  `MyBackup/Longhorn` subfolder. Not S3. Browsable from a machine that mounts the NAS share at
  `/home/blablack/Nasio/MyBackup/Longhorn`.
- **Recurring jobs** (Longhorn `RecurringJob` resources in `longhorn-system`, all in the `default`
  recurring-job-group, which every volume in this cluster is currently enrolled in):

  | Name | Cron | Task | Retain |
  |---|---|---|---|
  | `backup-monthly` | `0 3 1 * *` | backup | 1 |
  | `snapshot-delete-daily` | `0 5 * * *` | snapshot-delete | 1 |
  | `snapshot-cleanup-weekly` | `0 4 * * 0` | snapshot-cleanup | 0 |
  | `trim-daily` | `0 1 * * *` | filesystem-trim | 0 |

  Check current state any time with:
  ```bash
  kubectl -n longhorn-system get backuptargets.longhorn.io
  kubectl -n longhorn-system get recurringjobs.longhorn.io
  kubectl -n longhorn-system get backups.longhorn.io
  ```

## Steps

1. Set up a new Kubernetes cluster (see README for k3s install via Ansible)

2. Install Longhorn on the new cluster:
```bash
kubectl apply -f https://raw.githubusercontent.com/longhorn/longhorn/master/deploy/longhorn.yaml
```

3. Point Longhorn at the same backup target as the original cluster — the NFS share above.
   Via the UI: Settings → General → Backup Target → `nfs://192.168.2.4:/volume1/public/MyBackup/Longhorn`
   (leave Backup Target Credential Secret empty, as on the original cluster). Confirm the new
   cluster's nodes can actually reach the NAS at 192.168.2.4 first.

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
  fromBackup: nfs://192.168.2.4:/volume1/public/MyBackup/Longhorn?backup=backup-name&volume=backup-volume-name
  numberOfReplicas: 2
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
  storageClassName: my-longhorn
  resources:
    requests:
      storage: size-of-volume
  volumeName: name-of-restored-pv
```

7. Update application manifests to reference the restored PVC

## Checklist

- New cluster has enough storage capacity
- New cluster's nodes can reach the NAS (192.168.2.4) over NFS
- Backup target has been reconfigured (step 3) — it does not carry over from git
- Restored volumes have correct access permissions
- Test restore periodically — don't wait for a real disaster
