from odoo import fields, models


class ProductTemplate(models.Model):
    _inherit = "product.template"

    brand_id = fields.Many2one(
        "workshop.product.brand",
        string="Brand",
        index=True,
        ondelete="restrict",
    )
