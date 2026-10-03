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

# Always (re)install our addons before starting the web server, instead of trying
# to detect "is the DB fresh" first. Odoo's `-i` on an already-installed module is a
# safe, idempotent no-extra-op (it behaves like `-u`) — so this correctly covers
# EVERY case with one code path: a totally empty database (bootstraps base +
# dependencies + both addons), and the partial-failure case where base/contacts/hr
# already installed successfully on a previous boot but one of ours didn't
# (a schema-existence check alone would silently skip it forever in that case,
# which is exactly what happened once already — see git history).
# demo_manufacturing_data only installs the seeder tool itself (Settings ▸
# Technical ▸ Demo Data) — it does NOT run the data generation automatically,
# since that's additive each time and would otherwise pile up on every redeploy.
echo ">>> Ensuring starx_gps and demo_manufacturing_data are installed..."
odoo --config="$CONF" --stop-after-init -i starx_gps,demo_manufacturing_data $DEMO_FLAG
echo ">>> Install/update step complete."

# Two settings the database was never given a chance to get right, since it was
# bootstrapped from the command line (-i above), never through the web "Create
# Database" wizard where a human would normally set both:
#   - the admin login password ($ADMIN_PASSWORD) — with no SMTP configured either,
#     "forgot password" can't work, so this is applied on EVERY boot, idempotently,
#     making access always recoverable: change the Railway variable, redeploy.
#   - web.base.url ($RAILWAY_PUBLIC_DOMAIN, injected by Railway automatically) — the
#     employee check-in link (hr_employee.py's checkin_url) is built FROM this
#     setting, so a wrong or unset value here silently produces a broken link
#     (e.g. pointing at localhost) rather than an obvious error.
# NOTE: keep ADMIN_PASSWORD free of single-quote characters — it's embedded in a
# single-quoted Python string below.
SHELL_SCRIPT=""
if [ -n "$ADMIN_PASSWORD" ]; then
  SHELL_SCRIPT="${SHELL_SCRIPT}env['res.users'].search([('login','=','admin')]).write({'password': '$ADMIN_PASSWORD'})
"
fi
if [ -n "$RAILWAY_PUBLIC_DOMAIN" ]; then
  SHELL_SCRIPT="${SHELL_SCRIPT}env['ir.config_parameter'].sudo().set_param('web.base.url', 'https://$RAILWAY_PUBLIC_DOMAIN')
"
fi
if [ -n "$SHELL_SCRIPT" ]; then
  echo ">>> Applying runtime settings (admin password / web.base.url)..."
  printf '%s\nenv.cr.commit()\n' "$SHELL_SCRIPT" | odoo shell --config="$CONF" -d "${PGDATABASE:-}" --no-http
  echo ">>> Runtime settings applied."
fi

exec odoo --config="$CONF" --http-port="${PORT:-8069}" "$@"
