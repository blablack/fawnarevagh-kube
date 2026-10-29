#include <tunables/global>

# Patched copy of the default AppArmor profile that k3s's bundled containerd
# (LoadDefaultProfile) applies to every non-privileged container. containerd
# skips loading its built-in profile if one of the same name is already loaded,
# so this host copy wins.
#
# Why this exists: on Ubuntu with kernel.apparmor_restrict_unprivileged_unconfined=1
# (the default from the apparmor package's /usr/lib/sysctl.d/10-apparmor.conf,
# enforced strictly from kernel 7.0.0-42), runc runs unconfined and without
# CAP_MAC_OVERRIDE, so its change_onexec to the container profile is converted
# to a stack: container tasks carry the label "cri-containerd.apparmor.d//&unconfined".
# containerd's upstream template only allows "signal/ptrace peer=cri-containerd.apparmor.d"
# (the literal name), so intra-container signalling is DENIED under the stacked
# label - PostgreSQL fails with "could not signal for checkpoint: Permission
# denied" and never finishes starting, and gosu spins at 100% CPU retrying a
# denied kill(). This took authentik, immich and paperless down on 2026-10-29
# after quario rebooted onto 7.0.0-42. See containerd#14485.
#
# The body below is containerd v2.3.4's generated default profile verbatim
# (contrib/apparmor/template.go, Name=cri-containerd.apparmor.d,
# DaemonProfile=unconfined, InnerImports=<abstractions/base>); the only additions
# are the two "//&unconfined" stacked-peer lines marked FIX below. Keep it in
# sync with the containerd version k3s ships if that ever changes.
#
# Alternative one-liner fix is `sysctl kernel.apparmor_restrict_unprivileged_unconfined=0`,
# but that weakens host hardening cluster-wide; this profile keeps it at 1.

profile cri-containerd.apparmor.d flags=(attach_disconnected,mediate_deleted) {
  #include <abstractions/base>

  network,
  capability,
  file,
  umount,
  # Host (privileged) processes may send signals to container processes.
  signal (receive) peer=unconfined,
  # runc may send signals to container processes.
  signal (receive) peer=runc,
  # crun may send signals to container processes.
  signal (receive) peer=crun,
  # Manager may send signals to container processes.
  signal (receive) peer=unconfined,
  # Container processes may send signals amongst themselves.
  signal (send,receive) peer=cri-containerd.apparmor.d,
  # FIX (containerd#14485): same, for the stacked label that non-privileged
  # containers actually carry under apparmor_restrict_unprivileged_unconfined=1.
  signal (send,receive) peer=cri-containerd.apparmor.d//&unconfined,

  deny @{PROC}/* w,   # deny write for all files directly in /proc (not in a subdir)
  # deny write to files not in /proc/<number>/** or /proc/sys/**
  deny @{PROC}/{[^1-9/],[^1-9/][^0-9/],[^1-9s/][^0-9y/][^0-9s/],[^1-9/][^0-9/][^0-9/][^0-9/]*}/** w,
  deny @{PROC}/sys/[^k]** w,  # deny /proc/sys except /proc/sys/k* (effectively /proc/sys/kernel)
  deny @{PROC}/sys/kernel/{?,??,[^s][^h][^m]**} w,  # deny everything except shm* in /proc/sys/kernel/
  deny @{PROC}/sysrq-trigger rwklx,
  deny @{PROC}/kcore rwklx,

  deny mount,

  deny /sys/[^f]*/** wklx,
  deny /sys/f[^s]*/** wklx,
  deny /sys/fs/[^c]*/** wklx,
  deny /sys/fs/c[^g]*/** wklx,
  deny /sys/fs/cg[^r]*/** wklx,
  deny /sys/firmware/** rwklx,
  deny /sys/devices/virtual/powercap/** rwklx,
  deny /sys/kernel/security/** rwklx,

  # allow processes within the container to trace each other,
  # provided all other LSM and yama setting allow it.
  ptrace (trace,tracedby,read,readby) peer=cri-containerd.apparmor.d,
  # FIX (containerd#14485): same, for the stacked label form.
  ptrace (trace,tracedby,read,readby) peer=cri-containerd.apparmor.d//&unconfined,
}
