# -*- coding: utf-8 -*-
from odoo import fields, models


class ResPartner(models.Model):
    """The only extension this module makes to res.partner: which field worker this
    point is assigned to. Everything else about a "point" — name, address, contact
    info — is exactly whatever Contacts already has. Without this field, a worker's
    check-in form (or the Planner wizard) would have to search the WHOLE company
    directory instead of just their own stops, which is both a worse experience and
    the "mini-CRM" duplication this module set out to avoid re-creating."""
    _inherit = "res.partner"

    field_worker_id = fields.Many2one(
        "hr.employee", string="Field worker",
        help="The field worker assigned to visit this point. Drives both the "
             "no-login check-in portal's point list and the GPS Planner's "
             "candidate stops for that worker.",
    )
