from odoo import _, api, fields, models
from odoo.exceptions import ValidationError
from collections import defaultdict
from odoo.tools import float_repr


class SaleOrderDiscount(models.TransientModel):
    _inherit = 'sale.order.discount'

    sol_disc_type = fields.Selection(
        selection=[
            ('per', "%"),
            ('amt', "Amt"),
        ]
    )

    @api.constrains('discount_type', 'discount_percentage', 'sol_disc_type')
    def _check_discount_amount(self):
        for wizard in self:
            if (
                wizard.discount_type in ('sol_discount', 'so_discount')
                and wizard.discount_percentage > 1.0 and not wizard.sol_disc_type
            ):
                raise ValidationError(_("Invalid discount amount"))

    def action_apply_discount(self):
        self.ensure_one()
        self = self.with_company(self.company_id)
        if self.discount_type == 'sol_discount':
            if self.sol_disc_type == 'amt':
                self.sale_order_id.order_line.write({'discount_amt': self.discount_percentage})
            else:
                self.sale_order_id.order_line.write({'discount': self.discount_percentage})
        else:
            return super().action_apply_discount()

    def _create_discount_lines(self):
        """Create SOline(s) according to wizard configuration"""
        self.ensure_one()
        discount_product = self._get_discount_product()

        if self.discount_type == 'amount':
            if not self.sale_order_id.amount_total:
                return
            so_amount = self.sale_order_id.amount_total
            # Fixed taxes cannot be discounted, so they cannot be considered in the total amount
            # when computing the discount percentage.
            if any(tax.amount_type == 'fixed' for tax in self.sale_order_id.order_line.tax_id.flatten_taxes_hierarchy()):
                fixed_taxes_amount = 0
                for line in self.sale_order_id.order_line:
                    taxes = line.tax_id.flatten_taxes_hierarchy()
                    for tax in taxes.filtered(lambda tax: tax.amount_type == 'fixed'):
                        fixed_taxes_amount += tax.amount * line.product_uom_qty
                so_amount -= fixed_taxes_amount
            discount_percentage = self.discount_amount / so_amount
        else: # so_discount
            discount_percentage = self.discount_percentage
        total_price_per_tax_groups = defaultdict(float)
        for line in self.sale_order_id.order_line:
            if not line.product_uom_qty or not line.price_unit:
                continue
            # Fixed taxes cannot be discounted.
            taxes = line.tax_id.flatten_taxes_hierarchy()
            fixed_taxes = taxes.filtered(lambda t: t.amount_type == 'fixed')
            taxes -= fixed_taxes
            if line.discount_amt > 0.0:
                total_price_per_tax_groups[taxes] += (line.price_unit * line.product_uom_qty) - line.discount_amt
            else:
                total_price_per_tax_groups[taxes] += line.price_unit * (1 - (line.discount or 0.0) / 100) * line.product_uom_qty

        discount_dp = self.env['decimal.precision'].precision_get('Discount')
        context = {'lang': self.sale_order_id._get_lang()}  # noqa: F841
        if not total_price_per_tax_groups:
            # No valid lines on which the discount can be applied
            return
        if len(total_price_per_tax_groups) == 1:
            # No taxes, or all lines have the exact same taxes
            taxes = next(iter(total_price_per_tax_groups.keys()))
            subtotal = total_price_per_tax_groups[taxes]
            vals_list = [{
                **self._prepare_discount_line_values(
                    product=discount_product,
                    amount=subtotal * discount_percentage,
                    taxes=taxes,
                    description=_(
                        "Discount %(percent)s%%",
                        percent=float_repr(discount_percentage * 100, discount_dp),
                    ),
                ),
            }]
        else:
            vals_list = []
            for taxes, subtotal in total_price_per_tax_groups.items():
                discount_line_value = self._prepare_discount_line_values(
                    product=discount_product,
                    amount=subtotal * discount_percentage,
                    taxes=taxes,
                    description=_(
                        "Discount %(percent)s%%"
                        "- On products with the following taxes %(taxes)s",
                        percent=float_repr(discount_percentage * 100, discount_dp),
                        taxes=", ".join(taxes.mapped('name')),
                    ) if self.discount_type != 'amount' else _(
                        "Discount"
                        "- On products with the following taxes %(taxes)s",
                        taxes=", ".join(taxes.mapped('name')),
                    )
                )
                vals_list.append(discount_line_value)
        return self.env['sale.order.line'].create(vals_list)

