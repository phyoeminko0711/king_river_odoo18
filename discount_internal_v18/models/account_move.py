from odoo import api, fields, models
import logging


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    discount_amt = fields.Float(
        string="Disc.Amt",
        digits='Discount')

    @api.onchange('discount')
    def set_0_to_discount_amt(self):
        for rec in self:
            if rec.discount > 0.0:
                rec.discount_amt = 0.0

    @api.onchange('discount_amt')
    def set_0_to_discount(self):
        for rec in self:
            if rec.discount_amt > 0.0:
                rec.discount = 0.0


class AccountMove(models.Model):
    _inherit = "account.move"

    total_discount = fields.Monetary('Total Disc', compute='compute_total_discount', store=True)

    @api.depends('amount_total', 'invoice_line_ids.price_subtotal', 'invoice_line_ids.discount', 'invoice_line_ids.discount_amt', 'invoice_line_ids.quantity', 'invoice_line_ids.price_unit', 'invoice_line_ids.discount', 'invoice_line_ids.discount_amt')
    def compute_total_discount(self):
        for rec in self:
            discount = 0.0
            if rec.move_type != 'entry':
                if rec.move_type in ['out_invoice', 'out_refund']:
                    discount_product_id = self.company_id.sale_discount_product_id
                else:
                    discount_product_id = self.company_id.purchase_discount_product_id
                for line in rec.invoice_line_ids:
                    if line.product_id == discount_product_id:
                        discount += line.price_subtotal * -1
                    else:
                        if line.discount:
                            discount += (line.discount/100) * (line.price_unit * line.quantity)
                        if line.discount_amt:
                            discount += line.discount_amt
            rec.total_discount = discount

    def _prepare_product_base_line_for_taxes_computation(self, product_line):
        res = super()._prepare_product_base_line_for_taxes_computation(product_line=product_line)
        res.update({'discount_amt': product_line.discount_amt})
        return res
