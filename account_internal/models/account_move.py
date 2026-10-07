from odoo import models


class AccountMove(models.Model):
    _inherit = "account.move"

    def action_print_sale_invoice_direct(self):
        self.ensure_one()
        return self.env.ref(
            "account_internal.action_report_sale_invoice_direct_print"
        ).report_action(self)
