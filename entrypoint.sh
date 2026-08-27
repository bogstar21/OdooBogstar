#!/bin/sh
# Two DISTINCT ports are in play here — mixing them up breaks Railway's routing:
#   - $PORT       — injected automatically BY RAILWAY, the HTTP port it routes public
#                    traffic to. Odoo must listen on THIS one.
#   - $PGPORT     — injected by RAILWAY'S POSTGRES PLUGIN, the database port (5432).
#                    Completely separate from $PORT; only used for the DB connection.
set -e

# workers > 0 switches Odoo from its single-threaded dev server (which processes
# requests ONE AT A TIME — a single backend page load fires off dozens of separate
# asset/RPC requests that then queue up behind each other) to multiple worker
# processes handled in parallel. This is what actually fixes "pages are slow" when
# CPU/memory graphs show the container barely being used — the old setup wasn't
# resource-starved, it was serializing everything through one thread. Override with
# the ODOO_WORKERS variable if this ever needs tuning down for a smaller Railway plan.
#
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
workers = ${ODOO_WORKERS:-2}
max_cron_threads = 1
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

# The database was bootstrapped from the command line (-i above), never through the
# web "Create Database" wizard — so nobody ever typed in an admin login/password for
# it. Set (or reset) it here from $ADMIN_PASSWORD on every boot, idempotently, so
# access is always recoverable by changing a Railway variable and redeploying — no
# working email/SMTP required (none is configured in this deployment, so the "forgot
# password" flow cannot work either).
# NOTE: keep ADMIN_PASSWORD free of single-quote characters — it's embedded in a
# single-quoted Python string below.
if [ -n "$ADMIN_PASSWORD" ]; then
  echo ">>> Setting the 'admin' user's password from \$ADMIN_PASSWORD..."
  echo "env['res.users'].search([('login','=','admin')]).write({'password': '$ADMIN_PASSWORD'}); env.cr.commit()" \
    | odoo shell --config="$CONF" -d "${PGDATABASE:-}" --no-http
  echo ">>> Admin password set."
fi

exec odoo --config="$CONF" --http-port="${PORT:-8069}" "$@"
