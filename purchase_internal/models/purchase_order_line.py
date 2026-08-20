from odoo import fields, models


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
