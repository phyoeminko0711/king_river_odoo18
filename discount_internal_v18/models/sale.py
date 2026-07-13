from odoo import api, fields, models
import logging


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    discount_amt = fields.Float(
        string="Disc.Amt",
        compute='_compute_discount_amt',
        digits='Discount',
        store=True, readonly=False, precompute=True)

    def _prepare_invoice_line(self, **optional_values):
        res = super()._prepare_invoice_line(**optional_values)
        res.update({'discount_amt': self.discount_amt})
        return res

    def _prepare_base_line_for_taxes_computation(self, **kwargs):
        res = super()._prepare_base_line_for_taxes_computation(kwargs=kwargs)
        res.update({'discount_amt': self.discount_amt})
        return res

    @api.depends('product_id', 'product_uom', 'product_uom_qty', 'discount_amt')
    def _compute_discount(self):
        for rec in self:
            if rec.discount_amt > 0.0:
                rec.discount = 0.0
            if rec.discount > 0.0:
                rec.discount_amt = 0.0
        return super()._compute_discount()

    @api.depends('product_id', 'product_uom', 'product_uom_qty', 'discount')
    def _compute_discount_amt(self):
        for rec in self:
            if rec.discount > 0.0:
                rec.discount_amt = 0.0


class SaleOrder(models.Model):
    _inherit = "sale.order"

    total_discount = fields.Monetary('Total Disc', compute='compute_total_discount', store=True)

    @api.depends('amount_total','order_line.price_subtotal', 'order_line.discount', 'order_line.discount_amt', 'order_line.product_uom_qty', 'order_line.price_unit', 'order_line.discount', 'order_line.discount_amt')
    def compute_total_discount(self):
        for rec in self:
            discount = 0.0
            for line in rec.order_line:
                if line.product_id == self.company_id.sale_discount_product_id:
                    discount += line.price_subtotal * -1
                else:
                    if line.discount:
                        discount += (line.discount/100) * (line.price_unit * line.product_uom_qty)
                    if line.discount_amt:
                        discount += line.discount_amt
            rec.total_discount = discount
