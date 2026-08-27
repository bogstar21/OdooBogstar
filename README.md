# StarX GPS Intelligence — an Odoo module

Self-contained Odoo 17 addon: a no-login portal for field workers to check in with
GPS + a photo (over Odoo's own Contacts/Employees — no separate CRM), plus a route
intelligence engine (audit + planner + Google Maps link) with no equivalent in Odoo
Community or Enterprise. Full background/decisions: see `Plan-StarX-Odoo.md` in
`Downloads` (the planning doc this project was scoped from).

## Deploying on Railway (no local Docker needed)

1. **New Railway project** → *Deploy from GitHub repo* → pick this repo.
2. **Add a Postgres plugin** to the same Railway project (one click, from the
   project dashboard).
3. **Create a dedicated, non-superuser role for Odoo.** Odoo refuses to start
   against Railway's default `postgres` superuser role on purpose (it would give
   Odoo unrestricted access to the whole Postgres instance, not just its own
   database) — you'll see `Using the database user 'postgres' is a security
   risk, aborting.` crash-looping in the logs if you skip this. In the Postgres
   service's query tool, run (replace `railway` with your actual `PGDATABASE`
   value, and pick a real password):
   ```sql
   CREATE USER odoo_app WITH PASSWORD 'pick-a-strong-password-here' CREATEDB;
   ALTER DATABASE railway OWNER TO odoo_app;
   GRANT ALL PRIVILEGES ON DATABASE railway TO odoo_app;
   ```
4. In the `starx-gps` service's **Variables** tab, set:
   ```
   PGHOST=${{Postgres.PGHOST}}
   PGPORT=${{Postgres.PGPORT}}
   PGDATABASE=${{Postgres.PGDATABASE}}
   PGUSER=odoo_app
   PGPASSWORD=pick-a-strong-password-here
   ```
   (`PGUSER`/`PGPASSWORD` are the role you just created — NOT a reference to the
   plugin's own superuser credentials. Adjust `Postgres` in `${{...}}` if your
   Postgres service has a different name.)
5. Also set **`MASTER_PASSWORD`** — a password of your choice for Odoo's
   *database manager* (create/backup/duplicate/drop a database; this is
   **different** from your own Odoo login, which you set on the next screen).
   Without it, Odoo falls back to its insecure default (`admin`).
6. Railway builds the `Dockerfile` (the official `odoo:17.0` image + this addon
   copied into `/mnt/extra-addons`) and deploys it, listening on Railway's own
   `$PORT`.
7. **First boot — do this once:** open the deployed URL. Odoo shows a
   simplified "Create Database" screen (the database name is already fixed to
   `PGDATABASE`, so it only asks for the master password, your login, and
   whether to load demo data):
   - Enter the `MASTER_PASSWORD` you set above (or `admin` if you skipped it).
   - Pick a login email/password for yourself.
   - **Check "Load demonstration data"** — seeds one demo worker (Carlos Ruiz)
     with 4 points and check-ins in a deliberately bad order, so the Audit
     screen has a real detour to show immediately.
   - Odoo logs you in. Go to **Apps**, remove the "Apps" filter, search
     **"StarX"**, click **Install**.
8. Menu **GPS Intelligence** appears in the main nav: *Audit a day*,
   *Plan & dispatch*, *Dispatched routes*, *Check-ins*.

### The worker's check-in link

Open **Employees** → pick an employee → the "StarX GPS — Check-in link" section
on their form has a `checkin_token`. The worker's URL is:

```
https://<your-railway-domain>/checkin/<checkin_token>
```

No Odoo account needed to open it — GPS + photo + a stop picker, same as the
original StarX PWA. Share that link like a password: anyone who has it can check in
as that employee (see the field's help text). "Regenerate check-in link" on the
employee form rotates it if it ever leaks.

### Known gap, on purpose (demo scope)

Odoo's database-manager screen uses a **default master password** unless
`odoo.conf` sets one explicitly — fine for a demo behind a not-yet-shared URL, but
tighten this (a mounted `odoo.conf` with `admin_passwd` set, or `--db-filter`) before
this is ever near real customer data.

## Local development (no Docker, no Python here)

This machine has neither Docker nor a real Python install, so the module was written
and reviewed carefully but not run locally — Railway's first deploy IS the first real
test. If something in a view/model is wrong, the error will show in Railway's build/
runtime logs; fix, commit, push, redeploy. If you want fast local iteration later,
installing Docker Desktop (or just Python + PostgreSQL natively) unlocks a
`docker compose up` / local Odoo dev loop — see the earlier planning discussion for
the tradeoffs.

## Module layout

```
starx_gps/
├── __manifest__.py
├── route_engine.py          # pure-Python port of StarX's routing.js/routeEngine.js
├── models/
│   ├── res_partner.py       # +field_worker_id (the only res.partner extension)
│   ├── hr_employee.py       # +checkin_token (the only hr.employee extension)
│   ├── field_checkin.py     # the check-in record itself
│   ├── gps_route_plan.py    # a dispatched route + its stops
│   └── gps_wizards.py       # Audit wizard + Planner wizard
├── controllers/
│   └── portal_checkin.py    # the no-login worker page
├── views/                   # backend views, wizard forms, the portal QWeb template, menu
├── security/ir.model.access.csv
└── data/demo_data.xml       # only loads with "Load demonstration data" checked
```
