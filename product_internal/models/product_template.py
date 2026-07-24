from odoo import fields, models


class ProductTemplate(models.Model):
    _inherit = "product.template"

    english_name = fields.Char(string="English Name")
    car_name = fields.Char(string="Car Name")
    lh_rh = fields.Char(string="LH/RH")
    model_engine = fields.Char(string="Model / Engine")
