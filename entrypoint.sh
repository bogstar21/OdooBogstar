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

export PGPASSWORD  # so psql below picks it up without prompting

DEMO_FLAG=""
[ "${LOAD_DEMO:-true}" = "false" ] && DEMO_FLAG="--without-demo=all"

# First boot: Railway's Postgres plugin creates the DATABASE, but it has no Odoo
# SCHEMA in it yet. Relying on the web "Create Database" wizard to bootstrap this is
# fragile — a wrong master password (or db_name being pinned in config, as it is
# above) can leave it half-done, and every request after that crash-loops with
# "KeyError: 'ir.http'" because the registry can't load against an empty database.
# So: initialize it here, once, automatically, before ever starting the web server.
if command -v psql >/dev/null 2>&1; then
  HAS_SCHEMA=$(psql -h "$PGHOST" -p "${PGPORT:-5432}" -U "$PGUSER" -d "$PGDATABASE" -tAc \
    "SELECT to_regclass('public.ir_module_module') IS NOT NULL;" 2>/dev/null || echo "f")
  if [ "$HAS_SCHEMA" != "t" ]; then
    echo ">>> No Odoo schema in '$PGDATABASE' yet — initializing base + starx_gps..."
    odoo --config="$CONF" --stop-after-init -i base,starx_gps $DEMO_FLAG
    echo ">>> Initialization complete."
  fi
else
  echo ">>> psql not found in image — skipping auto-init check, assuming DB is already set up."
fi

exec odoo --config="$CONF" --http-port="${PORT:-8069}" "$@"
