from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class AccountJournal(models.Model):
    _inherit = "account.journal"

    payment_channel_id = fields.Many2one(
        "account.payment.channel",
        string="Payment Channel",
        ondelete="restrict",
        index=True,
    )

    @api.constrains("type", "payment_channel_id")
    def _check_payment_channel_journal_type(self):
        for journal in self:
            if journal.payment_channel_id and journal.type not in ("bank", "cash"):
                raise ValidationError(
                    _("Payment Channel can only be set on Bank or Cash journals.")
                )
