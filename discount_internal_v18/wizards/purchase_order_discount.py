from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class PurchaseOrderDiscount(models.TransientModel):
    _inherit = 'purchase.order.discount'

    pol_disc_type = fields.Selection(
        selection=[
            ('per', "%"),
            ('amt', "Amt"),
        ]
    )

    @api.constrains('discount_type', 'discount_percentage')
    def check_discount_amount(self):
        for wizard in self:
            if (
                wizard.discount_type in ('pol_discount', 'po_discount')
                and (wizard.discount_percentage > 1.0 or wizard.discount_percentage < 0.0) and not wizard.pol_disc_type
            ):
                raise ValidationError(_("Invalid discount amount"))

    def action_discount_apply(self):
        self.ensure_one()
        self = self.with_company(self.company_id)
        if self.discount_type == 'pol_discount':
            if self.pol_disc_type == 'amt':
                self.purchase_order_id.order_line.write({'discount_amt': self.discount_percentage})
            else:
                self.purchase_order_id.order_line.write({'discount': self.discount_percentage})
        else:
            return super().action_discount_apply()
