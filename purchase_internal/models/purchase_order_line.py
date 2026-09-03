from odoo import api, fields, models


class PurchaseOrderLine(models.Model):
    _inherit = "purchase.order.line"

    car_name = fields.Char(
        string="Car Name",
        related="product_id.product_tmpl_id.car_name",
        store=True,
        readonly=True,
    )
    lh_rh = fields.Char(
        string="LH/RH",
        related="product_id.product_tmpl_id.lh_rh",
        store=True,
        readonly=True,
    )
    model_engine = fields.Char(
        string="Model / Engine",
        related="product_id.product_tmpl_id.model_engine",
        store=True,
        readonly=True,
    )


    @api.onchange("product_id")
    def _onchange_product_apply_order_analytic_account(self):
        for line in self:
            if line.order_id.analytic_account_id and not line.display_type:
                line.analytic_distribution = line.order_id._get_header_analytic_distribution()

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("analytic_distribution") or not vals.get("order_id"):
                continue
            order = self.env["purchase.order"].browse(vals["order_id"])
            if order.analytic_account_id:
                vals["analytic_distribution"] = order._get_header_analytic_distribution()
        return super().create(vals_list)
