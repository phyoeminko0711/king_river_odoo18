from odoo import _, fields, models
from odoo.exceptions import UserError


class SalePriceHistory(models.Model):
    _name = "sale.price.history"
    _description = "Sale Price History"
    _order = "approved_date desc, id desc"
    _rec_name = "name"
    _check_company_auto = True

    name = fields.Char(required=True, readonly=True, copy=False)
    company_id = fields.Many2one("res.company", required=True, index=True, readonly=True)
    product_id = fields.Many2one("product.product", required=True, index=True, readonly=True)
    product_tmpl_id = fields.Many2one("product.template", required=True, index=True, readonly=True)
    product_category_id = fields.Many2one("product.category", readonly=True, index=True)
    purchase_order_id = fields.Many2one("purchase.order", readonly=True, index=True)
    purchase_order_line_id = fields.Many2one("purchase.order.line", readonly=True, index=True)
    sale_price_update_id = fields.Many2one("sale.price.update", readonly=True, ondelete="restrict")
    vendor_id = fields.Many2one("res.partner", readonly=True, index=True)
    rule_line_id = fields.Many2one("sale.price.rule.line", readonly=True)
    old_sale_price = fields.Monetary(readonly=True, currency_field="currency_id")
    purchase_price = fields.Monetary(readonly=True, currency_field="currency_id")
    markup_type = fields.Selection(
        [("percentage", "Percentage"), ("fixed", "Fixed Amount")],
        readonly=True,
    )
    markup_value = fields.Float(readonly=True)
    calculated_sale_price = fields.Monetary(readonly=True, currency_field="currency_id")
    approved_sale_price = fields.Monetary(readonly=True, currency_field="currency_id")
    currency_id = fields.Many2one("res.currency", readonly=True, required=True)
    effective_date = fields.Date(readonly=True)
    approved_by = fields.Many2one("res.users", readonly=True, index=True)
    approved_date = fields.Datetime(readonly=True, index=True)

    def write(self, vals):
        if not self.env.su:
            raise UserError(_("Sale Price History records are immutable."))
        return super().write(vals)

    def unlink(self):
        if not self.env.user.has_group("base.group_system"):
            raise UserError(_("Only system administrators can delete Sale Price History records."))
        return super().unlink()
