from odoo import fields, models


class StockMove(models.Model):
    _inherit = "stock.move"

    stock_out = fields.Boolean(string="Stock Out", tracking=True)
    stock_return = fields.Boolean(string="Stock Return", tracking=True)
