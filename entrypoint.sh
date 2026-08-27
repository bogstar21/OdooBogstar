#!/bin/sh
# Two DISTINCT ports are in play here — mixing them up breaks Railway's routing:
#   - $PORT       — injected automatically BY RAILWAY, the HTTP port it routes public
#                    traffic to. Odoo must listen on THIS one.
#   - $PGPORT     — injected by RAILWAY'S POSTGRES PLUGIN, the database port (5432).
#                    Completely separate from $PORT; only used for the DB connection.
set -e

# admin_passwd guards Odoo's DATABASE MANAGER (create/backup/duplicate/drop a
# database) — it is NOT the login password for your own Odoo user account. Written
# into a real odoo.conf (no reliable CLI flag for this across Odoo versions).
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

DEMO_FLAG=""
[ "${LOAD_DEMO:-true}" = "false" ] && DEMO_FLAG="--without-demo=all"

# Always (re)install starx_gps before starting the web server, instead of trying to
# detect "is the DB fresh" first. Odoo's `-i` on an already-installed module is a
# safe, idempotent no-extra-op (it behaves like `-u`) — so this correctly covers
# EVERY case with one code path: a totally empty database (bootstraps base +
# dependencies + starx_gps), and the partial-failure case where base/contacts/hr
# already installed successfully on a previous boot but starx_gps itself didn't
# (a schema-existence check alone would silently skip it forever in that case,
# which is exactly what happened once already — see git history).
echo ">>> Ensuring starx_gps is installed..."
odoo --config="$CONF" --stop-after-init -i starx_gps $DEMO_FLAG
echo ">>> Install/update step complete."

exec odoo --config="$CONF" --http-port="${PORT:-8069}" "$@"
