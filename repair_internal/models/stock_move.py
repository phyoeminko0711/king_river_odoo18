from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class StockMove(models.Model):
    _inherit = "stock.move"

    stock_out = fields.Boolean(string="Stock Out", tracking=True)
    stock_return = fields.Boolean(string="Stock Return", tracking=True)

    @api.onchange("stock_out")
    def _onchange_stock_out(self):
        if self.stock_out:
            self.stock_return = False

    @api.onchange("stock_return")
    def _onchange_stock_return(self):
        if self.stock_return:
            self.stock_out = False

    @api.constrains("stock_out", "stock_return")
    def _check_stock_out_return_exclusive(self):
        for move in self:
            if move.stock_out and move.stock_return:
                raise ValidationError(_("Stock Out and Stock Return cannot both be selected."))
