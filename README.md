# StarX GPS Intelligence — an Odoo module

Self-contained Odoo 17 addon: a no-login portal for field workers to check in with
GPS + a photo (over Odoo's own Contacts/Employees — no separate CRM), plus a route
intelligence engine (audit + planner + Google Maps link) with no equivalent in Odoo
Community or Enterprise. Full background/decisions: see `Plan-StarX-Odoo.md` in
`Downloads` (the planning doc this project was scoped from).

## Deploying on Railway (no local Docker needed)

1. **New Railway project** → *Deploy from GitHub repo* → pick this repo.
2. **Add a Postgres plugin** to the same Railway project (one click, from the
   project dashboard). Railway auto-injects `PGHOST`/`PGPORT`/`PGUSER`/
   `PGPASSWORD`/`PGDATABASE` — `entrypoint.sh` reads these, nothing to configure
   by hand.
3. Railway builds the `Dockerfile` (the official `odoo:17.0` image + this addon
   copied into `/mnt/extra-addons`) and deploys it, listening on Railway's own
   `$PORT`.
4. **First boot — do this once:** open the deployed URL. Odoo shows its own
   "Create Database" screen:
   - Pick a database name, a login email/password for yourself.
   - **Check "Load demonstration data"** — seeds one demo worker (Carlos Ruiz)
     with 4 points and check-ins in a deliberately bad order, so the Audit
     screen has a real detour to show immediately.
   - Odoo logs you in. Go to **Apps**, remove the "Apps" filter, search
     **"StarX"**, click **Install**.
5. Menu **GPS Intelligence** appears in the main nav: *Audit a day*,
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
