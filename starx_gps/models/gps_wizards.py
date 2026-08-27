# -*- coding: utf-8 -*-
import json
from datetime import datetime, time as dtime

from odoo import api, fields, models
from odoo.exceptions import UserError

from ..route_engine import audit_worker_day, plan_route

# No per-tenant fuel-price/avg-speed config in this module (unlike the original
# StarX, which read these from env vars) — a single reasonable default. Promote to
# an ir.config_parameter if a real customer ever asks to tune it.
AVG_SPEED_KMH = 30


def _epoch_ms(dt):
    # Odoo stores Datetime fields as naive UTC. We only ever compare DIFFERENCES
    # between two of these (see route_engine.audit_worker_day), so which timezone
    # .timestamp() assumes for the naive value doesn't matter — the same constant
    # offset applies to every check-in and cancels out.
    return int(dt.timestamp() * 1000)


class GpsAuditWizard(models.TransientModel):
    """The historical auditor — Rutas GPS ▸ Audit. Compares a worker's actual
    check-in sequence for one day against the optimal resequencing of those same
    stops, and flags anomalous legs."""
    _name = "gps.audit.wizard"
    _description = "GPS Intelligence — route audit"

    worker_id = fields.Many2one("hr.employee", string="Worker", required=True)
    date = fields.Date(string="Date", required=True, default=fields.Date.context_today)

    ran = fields.Boolean(default=False)
    note = fields.Char(readonly=True)
    actual_km = fields.Float(readonly=True, digits=(10, 2))
    optimal_km = fields.Float(readonly=True, digits=(10, 2))
    efficiency_pct = fields.Float(readonly=True, digits=(5, 1))
    wasted_km = fields.Float(readonly=True, digits=(10, 2))
    legs_html = fields.Html(readonly=True)

    def action_run(self):
        self.ensure_one()
        start = datetime.combine(self.date, dtime.min)
        end = datetime.combine(self.date, dtime.max)
        checkins = self.env["field.checkin"].search([
            ("worker_id", "=", self.worker_id.id),
            ("checkin_at", ">=", start),
            ("checkin_at", "<=", end),
        ], order="checkin_at asc")

        stops = [{
            "ms": _epoch_ms(c.checkin_at),
            "time": c.checkin_at.strftime("%H:%M"),
            "coord": (c.latitude, c.longitude),
            "point": c.point_id.name or "?",
        } for c in checkins]

        result = audit_worker_day(stops, AVG_SPEED_KMH)
        self.actual_km = result["actual_km"]
        self.optimal_km = result["optimal_km"]
        self.efficiency_pct = result["efficiency_pct"] or 0.0
        self.wasted_km = result["wasted_km"]
        self.note = result.get("note") or ""
        self.ran = True

        if not result["legs"]:
            self.legs_html = "<p><i>Not enough check-ins with coordinates on this day to compare.</i></p>"
        else:
            rows = "".join(
                "<tr><td>%d</td><td>%s → %s</td><td>%s → %s</td>"
                "<td>%.2f</td><td>%d min</td><td>%d min</td><td>%d min</td><td>%s</td></tr>" % (
                    leg["seq"], leg["from_point"], leg["to_point"],
                    leg["departure"], leg["arrival"], leg["km"],
                    round(leg["actual_min"]), round(leg["expected_min"]), round(leg["dwell_min"]),
                    ", ".join(leg["tags"]) or "—",
                )
                for leg in result["legs"]
            )
            self.legs_html = (
                "<table class='table table-sm'><thead><tr>"
                "<th>#</th><th>From → To</th><th>Departure → Arrival</th><th>Km</th>"
                "<th>Actual</th><th>Expected</th><th>Dwell</th><th>Flags</th>"
                "</tr></thead><tbody>%s</tbody></table>" % rows
            )

        return {
            "type": "ir.actions.act_window",
            "res_model": self._name, "res_id": self.id,
            "view_mode": "form", "target": "new",
        }


class GpsPlannerWizard(models.TransientModel):
    """The forward planner — Rutas GPS ▸ Planner. Pick a worker's assigned points,
    optimize the visiting order, then dispatch it as a gps.route.plan the worker
    (or their manager) can follow, with a one-tap Google Maps link."""
    _name = "gps.planner.wizard"
    _description = "GPS Intelligence — route planner"

    worker_id = fields.Many2one("hr.employee", string="Worker", required=True)
    date = fields.Date(string="Date", required=True, default=fields.Date.context_today)
    start_time = fields.Char(string="Start time", default="09:00")
    point_ids = fields.Many2many(
        "res.partner", string="Stops",
        domain="[('field_worker_id', '=', worker_id)]",
    )

    optimized = fields.Boolean(default=False)
    preview_html = fields.Html(readonly=True)
    total_km = fields.Float(readonly=True, digits=(10, 2))
    total_min = fields.Float(readonly=True, digits=(10, 1))
    # Serialized optimize() result — action_dispatch reads this instead of
    # recomputing, so what gets dispatched is exactly what was previewed.
    plan_json = fields.Text()

    def action_optimize(self):
        self.ensure_one()
        if len(self.point_ids) < 2:
            raise UserError("Pick at least 2 stops with known coordinates.")
        stops = [{
            "point_id": p.id, "name": p.name,
            "address": ", ".join(filter(None, [p.street, p.city])),
            "coord": (p.partner_latitude, p.partner_longitude) if (p.partner_latitude or p.partner_longitude) else None,
        } for p in self.point_ids]

        result = plan_route(stops, self.start_time, AVG_SPEED_KMH)
        self.total_km = result["total_km"]
        self.total_min = result["total_min"]
        self.optimized = True
        self.plan_json = json.dumps(result["stops"])

        rows = "".join(
            "<tr><td>%d</td><td>%s</td><td>%s</td><td>%s</td></tr>" % (
                s["sequence"], s["name"], s["address"] or "—", s["eta"],
            )
            for s in result["stops"]
        )
        skipped_note = (
            "<p class='text-muted'>%d stop(s) skipped — no coordinates yet (nobody has checked in there).</p>"
            % result["skipped"] if result["skipped"] else ""
        )
        self.preview_html = (
            "<table class='table table-sm'><thead><tr><th>#</th><th>Stop</th>"
            "<th>Address</th><th>ETA</th></tr></thead><tbody>%s</tbody></table>%s"
            % (rows, skipped_note)
        )
        return {
            "type": "ir.actions.act_window",
            "res_model": self._name, "res_id": self.id,
            "view_mode": "form", "target": "new",
        }

    def action_dispatch(self):
        self.ensure_one()
        if not self.optimized or not self.plan_json:
            raise UserError("Optimize the route before dispatching it.")
        stops = json.loads(self.plan_json)
        plan = self.env["gps.route.plan"].create({
            "worker_id": self.worker_id.id,
            "date": self.date,
            "total_km": self.total_km,
            "total_min": self.total_min,
            "mode": "straight",
            "line_ids": [(0, 0, {
                "sequence": s["sequence"], "point_id": s["point_id"], "eta": s["eta"],
            }) for s in stops],
        })
        return {
            "type": "ir.actions.act_window",
            "res_model": "gps.route.plan", "res_id": plan.id,
            "view_mode": "form", "target": "current",
        }
