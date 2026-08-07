from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class AccountPaymentChannel(models.Model):
    _name = "account.payment.channel"
    _description = "Payment Channel"
    _rec_name = "name"
    _order = "sequence, name"

    name = fields.Char(string="Payment Channel", required=True, index=True)
    code = fields.Char(index=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    note = fields.Text()

    @api.constrains("name")
    def _check_name_unique_case_insensitive(self):
        for channel in self:
            if not channel.name or not channel.name.strip():
                raise ValidationError(_("Payment Channel is required."))
            duplicate = self.search(
                [
                    ("id", "!=", channel.id),
                    ("name", "=ilike", channel.name.strip()),
                ],
                limit=1,
            )
            if duplicate:
                raise ValidationError(
                    _("Payment Channel name must be unique.")
                )

    def unlink(self):
        journals = self.env["account.journal"].search(
            [("payment_channel_id", "in", self.ids)],
            limit=1,
        )
        if journals:
            raise ValidationError(
                _(
                    "You cannot delete a Payment Channel that is assigned to a Journal. "
                    "Archive it instead."
                )
            )
        return super().unlink()
