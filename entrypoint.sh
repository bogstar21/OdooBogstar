#!/bin/sh
# Two DISTINCT ports are in play here — mixing them up breaks Railway's routing:
#   - $PORT       — injected automatically BY RAILWAY, the HTTP port it routes public
#                    traffic to. Odoo must listen on THIS one.
#   - $PGPORT     — injected by RAILWAY'S POSTGRES PLUGIN, the database port (5432).
#                    Completely separate from $PORT; only used for the DB connection.
#
# PGHOST/PGPORT/PGUSER/PGPASSWORD/PGDATABASE are the standard names Railway's own
# Postgres plugin exposes — add that plugin to the project and these appear
# automatically, no manual wiring needed beyond this script.
set -e

exec odoo \
  --addons-path=/mnt/extra-addons,/usr/lib/python3/dist-packages/odoo/addons \
  --http-port="${PORT:-8069}" \
  --db_host="$PGHOST" --db_port="${PGPORT:-5432}" \
  --db_user="$PGUSER" --db_password="$PGPASSWORD" \
  --database="${PGDATABASE:-}" \
  "$@"
