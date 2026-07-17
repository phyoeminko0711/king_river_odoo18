from odoo import fields, models


class ProductProduct(models.Model):
    _inherit = "product.product"

    brand_id = fields.Many2one(
        related="product_tmpl_id.brand_id",
        string="Brand",
        store=True,
        readonly=False,
    )
