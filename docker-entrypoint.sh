#!/bin/sh
# Starts the application as an unprivileged user, whatever owns the mounted data folder on the host.
# (A folder created by the host's installer belongs to root; the application must not run as root.)
set -e
umask 077   # patient data is readable by the application's user only
if [ "$(id -u)" = "0" ]; then
  mkdir -p /data
  # Repair ownership only when the top of the tree is wrong, so a restart is instant on a large data folder.
  if [ "$(stat -c %u /data)" != "10001" ]; then
    chown -R gms:gms /data
  fi
  chmod 700 /data
  exec setpriv --reuid=gms --regid=gms --init-groups -- "$@"
fi
exec "$@"
