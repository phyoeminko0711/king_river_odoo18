from odoo import _, fields, models
from odoo.exceptions import AccessError, ValidationError


class BatchSalePriceApprovalWizard(models.TransientModel):
    _name = "batch.sale.price.approval.wizard"
    _description = "Batch Sale Price Approval Wizard"

    action_type = fields.Selection(
        [
            ("approve", "Approve"),
            ("reject", "Reject"),
        ],
        required=True,
        default="approve",
    )
    update_ids = fields.Many2many("sale.price.update", string="Sale Price Updates")
    rejection_reason = fields.Text()

    def default_get(self, field_list):
        res = super().default_get(field_list)
        active_ids = self.env.context.get("active_ids", [])
        if active_ids:
            res["update_ids"] = [(6, 0, active_ids)]
        return res

    def _check_manager_access(self):
        if not self.env.user.has_group("purchase_sale_price_approval.group_sale_price_manager"):
            raise AccessError(_("You are not allowed to batch approve or reject sale price updates."))

    def action_process(self):
        self.ensure_one()
        self._check_manager_access()
        updates = self.update_ids.filtered(lambda update: update.state == "pending")
        if len(updates) != len(self.update_ids):
            raise ValidationError(_("All selected records must be in Pending state."))
        if self.action_type == "reject" and not self.rejection_reason:
            raise ValidationError(_("Rejection Reason is required for batch rejection."))

        if self.action_type == "approve":
            updates.action_approve()
        else:
            updates.write({"rejection_reason": self.rejection_reason})
            updates.action_reject()
        return {"type": "ir.actions.act_window_close"}
