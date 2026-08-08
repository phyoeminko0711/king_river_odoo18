from odoo import fields, models


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    brand_id = fields.Many2one(
        "workshop.product.brand",
        string="Brand",
        related="product_id.brand_id",
        store=True,
        readonly=True,
    )
