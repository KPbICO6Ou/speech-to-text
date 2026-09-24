#!/bin/sh
# Started as root: the bind-mounted dirs (models/logs/recs) arrive owned by
# the host user, which the unprivileged stt user cannot write - the chown
# baked into the image cannot reach them. Fix ownership here, then drop
# privileges and run the command.
set -eu
chown -R stt:stt /opt/models /opt/logs /opt/recs
exec setpriv --reuid stt --regid stt --clear-groups /bin/sh -c "$*"
