from odoo import models

REVIEW_THRESHOLD = 500.0


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    def _action_launch_stock_rule(self, *, previous_product_uom_qty=False):
        lines_ok = self.filtered(lambda l: l.order_id.amount_total <= REVIEW_THRESHOLD)
        if not lines_ok:
            return True
        return super(SaleOrderLine, lines_ok)._action_launch_stock_rule(
            previous_product_uom_qty=previous_product_uom_qty
        )
