from odoo import fields, models


class ProductTemplate(models.Model):
    _inherit = "product.template"

    english_name = fields.Char(
        string="English Name",
        index=True,
    )
    brand_id = fields.Many2one(
        "workshop.product.brand",
        string="Brand",
        index=True,
        ondelete="restrict",
    )
