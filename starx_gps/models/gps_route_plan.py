# -*- coding: utf-8 -*-
from urllib.parse import quote

from odoo import api, fields, models

# Google Maps' URL API takes a destination + up to 9 intermediate waypoints; beyond
# that it silently drops the rest. Cap it and say so, rather than handing the worker
# a truncated route — same rule StarX's gmapsUrl() enforced.
#
# `origin` is deliberately OMITTED: with no origin param, Maps uses the device's own
# live GPS position as the starting point when the link is opened — which is what a
# worker actually wants (navigate from wherever they are RIGHT NOW), not from
# whatever the planned first stop happened to be, which could already be miles away.
GMAPS_MAX_WAYPOINTS = 9


class GpsRoutePlan(models.Model):
    """A dispatched route for one worker on one day — the output of the Planner
    wizard (wizards/gps_planner_wizard.py). Kept as its own model (not a JSON blob
    in a settings key, unlike the original StarX/Node version) because Odoo's ORM
    makes a proper one2many of stops just as cheap as a text field, and it's more
    useful to the manager as a real, listable/searchable record.
    """
    _name = "gps.route.plan"
    _description = "GPS Intelligence — dispatched route"
    _order = "date desc, id desc"
    _rec_name = "display_name"

    worker_id = fields.Many2one("hr.employee", string="Worker", required=True, index=True)
    date = fields.Date(string="Date", required=True, default=fields.Date.context_today, index=True)
    total_km = fields.Float(string="Total distance (km)", digits=(10, 2))
    total_min = fields.Float(string="Total driving time (min)", digits=(10, 1))
    mode = fields.Selection(
        [("straight", "Straight-line estimate"), ("google", "Real road distance")],
        default="straight", string="Distance basis",
    )
    line_ids = fields.One2many("gps.route.plan.line", "plan_id", string="Stops")
    display_name = fields.Char(compute="_compute_display_name", store=True)
    maps_url = fields.Char(compute="_compute_maps_url", string="Google Maps link")

    @api.depends("worker_id", "date")
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = "%s — %s" % (rec.worker_id.name or "?", rec.date or "")

    @api.depends("line_ids.point_id.partner_latitude", "line_ids.point_id.partner_longitude", "line_ids.sequence")
    def _compute_maps_url(self):
        for rec in self:
            lines = rec.line_ids.sorted("sequence")
            pts = [
                "%s,%s" % (l.point_id.partner_latitude, l.point_id.partner_longitude)
                for l in lines
                if l.point_id.partner_latitude or l.point_id.partner_longitude
            ]
            if not pts:
                rec.maps_url = False
                continue
            # Destination + up to 9 waypoints = 10 stops total, since there's no
            # origin slot to "spend" any more (see the note above).
            capped = pts[: GMAPS_MAX_WAYPOINTS + 1]
            destination = capped[-1]
            mid = capped[:-1]
            url = (
                "https://www.google.com/maps/dir/?api=1&travelmode=driving"
                "&destination=" + quote(destination)
            )
            if mid:
                url += "&waypoints=" + quote("|".join(mid))
            rec.maps_url = url


class GpsRoutePlanLine(models.Model):
    _name = "gps.route.plan.line"
    _description = "GPS Intelligence — dispatched route stop"
    _order = "sequence"

    plan_id = fields.Many2one("gps.route.plan", required=True, ondelete="cascade")
    sequence = fields.Integer(string="#", required=True)
    point_id = fields.Many2one("res.partner", string="Point", required=True)
    eta = fields.Char(string="ETA")
