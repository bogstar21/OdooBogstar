#!/bin/sh
# Two DISTINCT ports are in play here — mixing them up breaks Railway's routing:
#   - $PORT       — injected automatically BY RAILWAY, the HTTP port it routes public
#                    traffic to. Odoo must listen on THIS one.
#   - $PGPORT     — injected by RAILWAY'S POSTGRES PLUGIN, the database port (5432).
#                    Completely separate from $PORT; only used for the DB connection.
#
# PGHOST/PGPORT/PGUSER/PGPASSWORD/PGDATABASE are the standard names Railway's own
# Postgres plugin exposes — add that plugin to the project and reference them into
# this service's Variables tab (see README), no manual wiring needed beyond that.
set -e

# admin_passwd guards Odoo's DATABASE MANAGER (create/backup/duplicate/drop a
# database) — it is NOT the login password for your own Odoo user account, which you
# set separately on the "Create Database" screen itself. There is no reliable CLI
# flag for this across Odoo versions, so it's written into a real odoo.conf instead
# of guessed at on the command line. Falls back to Odoo's own insecure default
# ("admin") if MASTER_PASSWORD isn't set — set it in Railway's Variables tab and
# redeploy before this is anything more than a private demo.
CONF=/tmp/odoo.conf
cat > "$CONF" <<CONFEOF
[options]
admin_passwd = ${MASTER_PASSWORD:-admin}
db_host = ${PGHOST}
db_port = ${PGPORT:-5432}
db_user = ${PGUSER}
db_password = ${PGPASSWORD}
db_name = ${PGDATABASE:-}
addons_path = /mnt/extra-addons,/usr/lib/python3/dist-packages/odoo/addons
CONFEOF

exec odoo --config="$CONF" --http-port="${PORT:-8069}" "$@"
