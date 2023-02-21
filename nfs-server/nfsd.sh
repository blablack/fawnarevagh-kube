#!/bin/bash

# Make sure we react to these signals by running stop() when we see them - for clean shutdown
# And then exiting
trap "stop; exit 0;" SIGTERM SIGINT

stop()
{
  # We're here because we've seen SIGTERM, likely via a Docker stop command or similar
  # Let's shutdown cleanly
  echo "SIGTERM caught, terminating NFS process(es)..."
  /usr/sbin/exportfs -uav
  /usr/sbin/rpc.nfsd 0
  pid1=`pidof rpc.nfsd`
  pid2=`pidof rpc.mountd`
  # For IPv6 bug:
  pid3=`pidof rpcbind`
  kill -TERM $pid1 $pid2 $pid3 > /dev/null 2>&1
  echo "Terminated."
  exit
}

echo "Displaying /etc/exports contents:"
cat /etc/exports
echo ""

# Normally only required if v3 will be used
# But currently enabled to overcome an NFS bug around opening an IPv6 socket
echo "Starting rpcbind..."
/sbin/rpcbind -w
echo "Displaying rpcbind status..."
/sbin/rpcinfo

echo "Starting NFS in the background..."
/usr/sbin/rpc.nfsd --debug 8 --no-udp --no-nfs-version 3

#echo "Exporting File System..."
#/usr/sbin/exportfs

echo "Starting Mountd in the background..."These
/usr/sbin/rpc.mountd --debug all --no-udp --no-nfs-version 3

sleep 5

echo "Exporting File System..."
/usr/sbin/exportfs -a

echo "List of share..."
/usr/sbin/showmount -e localhost


while true; do

  # Check if NFS is STILL running by recording it's PID (if it's not running $pid will be null):
  pid=`pidof rpc.mountd`
  # If it is not, lets kill our PID1 process (this script) by breaking out of this while loop:
  # This ensures Docker observes the failure and handles it as necessary
  if [ -z "$pid" ]; then
    echo "NFS has failed, exiting, so Docker can restart the container..."
    break
  fi

  # If it is, give the CPU a rest
  sleep 120

done

sleep 1
exit 1
