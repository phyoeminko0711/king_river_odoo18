from odoo import api, fields, models
import logging


class PurchaseOrderLine(models.Model):
    _inherit = "purchase.order.line"

    discount_amt = fields.Float(
        string="Disc.Amt",
        compute='_compute_discount_amt',
        digits='Discount',
        store=True, readonly=False, precompute=True)

    def _prepare_account_move_line(self, move=False):
        res = super()._prepare_account_move_line(move=move)
        res.update({'discount_amt': self.discount_amt})
        return res

    @api.depends('product_qty', 'price_unit', 'taxes_id', 'discount', 'discount_amt')
    def _compute_amount(self):
        return super()._compute_amount()

    def _prepare_base_line_for_taxes_computation(self):
        res = super()._prepare_base_line_for_taxes_computation()
        res.update({'discount_amt': self.discount_amt})
        return res

    @api.depends('product_qty', 'product_uom', 'company_id', 'order_id.partner_id', 'discount_amt')
    def _compute_price_unit_and_date_planned_and_name(self):
        for rec in self:
            if rec.discount_amt > 0.0:
                rec.discount = 0.0
            if rec.discount > 0.0:
                rec.discount_amt = 0.0
        return super()._compute_price_unit_and_date_planned_and_name()

    @api.depends('product_id', 'product_uom', 'product_qty', 'discount')
    def _compute_discount_amt(self):
        for rec in self:
            if rec.discount > 0.0:
                rec.discount_amt = 0.0


class PurchaseOrder(models.Model):
    _inherit = "purchase.order"

    total_discount = fields.Monetary('Total Disc', compute='compute_total_discount', store=True)

    @api.depends('amount_total', 'order_line.price_subtotal', 'order_line.discount', 'order_line.discount_amt', 'order_line.product_qty', 'order_line.price_unit', 'order_line.discount', 'order_line.discount_amt')
    def compute_total_discount(self):
        for rec in self:
            discount = 0.0
            for line in rec.order_line:
                if line.product_id == self.company_id.purchase_discount_product_id:
                    discount += line.price_subtotal * -1
                else:
                    if line.discount:
                        discount += (line.discount/100) * (line.price_unit * line.product_qty)
                    if line.discount_amt:
                        discount += line.discount_amt
            rec.total_discount = discount
