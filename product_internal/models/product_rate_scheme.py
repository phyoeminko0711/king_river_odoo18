from odoo import fields, models


class ProductRateScheme(models.Model):
    _name = "product.rate.scheme"
    _description = "Product Rate Scheme"
    _order = "name, id"

    name = fields.Char(required=True)
    code = fields.Char()
    active = fields.Boolean(default=True)
