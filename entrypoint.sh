#!/bin/sh
# Started as root: the bind-mounted dirs (models/logs/recs) arrive owned by
# the host user, which the unprivileged stt user cannot write - the chown
# baked into the image cannot reach them. Fix ownership here, then drop
# privileges and run the command.
set -eu
chown -R stt:stt /opt/models /opt/logs /opt/recs
# The inner `exec` matters: without it the shell stays PID 1 as the server's parent and does not
# forward SIGTERM, so every stop and redeploy waited out Docker's 10 s grace period and then
# SIGKILLed the server with requests still in flight.
exec setpriv --reuid stt --regid stt --clear-groups /bin/sh -c "exec $*"
