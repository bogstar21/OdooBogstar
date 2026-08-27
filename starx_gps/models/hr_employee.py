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
        help="Part of this employee's no-login check-in URL. Use "
             "'Regenerate check-in link' if it leaks.",
    )

    def action_regenerate_checkin_token(self):
        for rec in self:
            rec.checkin_token = secrets.token_urlsafe(24)
