{
    "name": "StarX GPS Intelligence",
    "summary": "Field check-ins (GPS + photo) with route auditing and dispatch planning.",
    "description": """
StarX GPS Intelligence
=======================
A self-contained field-ops module: a no-login portal for workers to check in with
GPS + a photo (over their own Contacts/Employees, no separate CRM), and a route
intelligence engine with no equivalent in Odoo Community or Enterprise:

* **Audit** — for one worker's day, compares the actual visit order (from their
  check-ins) against the mathematically optimal order of the same stops, and flags
  anomalous legs (excessive idle time, route detours).
* **Planner** — pick a worker's assigned points, optimize the visiting order
  (nearest-neighbour + 2-opt), and dispatch it with a one-tap Google Maps
  turn-by-turn link.

Ported from a standalone Node.js SaaS (StarX) built by the same author — the route
math (haversine distance, 2-opt local search, anomaly tagging) is a direct
translation, not a redesign.
""",
    "version": "17.0.1.0.0",
    "category": "Operations/Field Service",
    "author": "Bogdan Starchenko",
    "license": "LGPL-3",
    "depends": ["base", "contacts", "hr", "web"],
    "data": [
        "security/ir.model.access.csv",
        "views/field_checkin_views.xml",
        "views/gps_wizard_views.xml",
        "views/portal_templates.xml",
        "views/report_checkin.xml",
        "views/menus.xml",
    ],
    # Demo data only loads if the database was created with "Load demonstration
    # data" checked — never on a real customer's production Odoo.
    "demo": [
        "data/demo_data.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "starx_gps/static/src/css/gps.css",
        ],
    },
    "images": [],
    "installable": True,
    "application": True,
}
