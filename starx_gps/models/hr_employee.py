# -*- coding: utf-8 -*-
import secrets

from odoo import fields, models


class HrEmployee(models.Model):
    """The only extension to hr.employee: an unguessable token so a field worker can
    open their check-in page (controllers/portal_checkin.py) without an Odoo user
    account or password — matching the phone-only, no-login worker experience the
    original StarX PWA had. The token is the security boundary here: anyone who has
    it can check in as that employee, so treat the link like a password (share it
    over the same private channel you'd use for one)."""
    _inherit = "hr.employee"

    checkin_token = fields.Char(
        string="Check-in link token", copy=False, readonly=True,
        default=lambda self: secrets.token_urlsafe(24),
    )
    checkin_url = fields.Char(string="Check-in link", compute="_compute_checkin_url")

    def _compute_checkin_url(self):
        # web.base.url is Odoo's own record of its public URL (set automatically to
        # whatever domain served the current request, e.g. the Railway URL) — this is
        # what turns the bare, easy-to-miss token into a full link you can actually
        # click or copy, instead of expecting someone to assemble
        # "<their domain> + /checkin/ + <token>" by hand.
        base_url = self.env["ir.config_parameter"].sudo().get_param("web.base.url", "")
        for rec in self:
            rec.checkin_url = ("%s/checkin/%s" % (base_url, rec.checkin_token)) if rec.checkin_token else False

    def action_regenerate_checkin_token(self):
        for rec in self:
            rec.checkin_token = secrets.token_urlsafe(24)
