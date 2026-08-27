# -*- coding: utf-8 -*-
from odoo import api, fields, models


class FieldCheckin(models.Model):
    """A worker's visit to a point (a Contact), captured with GPS + an optional
    photo. Written from the no-login portal (controllers/portal_checkin.py) — the
    worker never needs an Odoo user account, matching the phone-only/no-login worker
    experience the original StarX PWA had.

    Deliberately reuses res.partner and hr.employee instead of inventing separate
    "point"/"worker" models — see the project plan: duplicating Odoo's own contact/
    employee management was the exact "mini-CRM" redundancy this module set out to
    avoid.
    """
    _name = "field.checkin"
    _description = "Field check-in (GPS + photo)"
    _order = "checkin_at desc"
    _rec_name = "display_name"

    worker_id = fields.Many2one("hr.employee", string="Worker", required=True, index=True)
    point_id = fields.Many2one("res.partner", string="Point", required=True, index=True)
    checkin_at = fields.Datetime(string="Check-in time", required=True, default=fields.Datetime.now, index=True)
    latitude = fields.Float(string="Latitude", digits=(10, 7), required=True)
    longitude = fields.Float(string="Longitude", digits=(10, 7), required=True)
    photo = fields.Binary(string="Photo", attachment=True)
    signature = fields.Binary(string="Signature", attachment=True)
    note = fields.Char(string="Note")
    display_name = fields.Char(compute="_compute_display_name", store=True)

    @api.depends("worker_id", "point_id", "checkin_at")
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = "%s — %s (%s)" % (
                rec.worker_id.name or "?",
                rec.point_id.name or "?",
                rec.checkin_at or "",
            )

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        # First check-in geolocates the point — mirrors StarX's ensurePointLocation:
        # only fills coordinates that are still empty, never overwrites a point that
        # already has a known location.
        for rec in records:
            partner = rec.point_id
            if not partner.partner_latitude and not partner.partner_longitude:
                partner.sudo().write({
                    "partner_latitude": rec.latitude,
                    "partner_longitude": rec.longitude,
                })
        return records

    def coord(self):
        self.ensure_one()
        return (self.latitude, self.longitude)
