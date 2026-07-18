from odoo import _, fields, models
from odoo.exceptions import UserError, ValidationError


class WorkshopAddRepairServiceWizard(models.TransientModel):
    _name = "workshop.add.repair.service.wizard"
    _description = "Add Repair Services to Job Card"

    job_card_id = fields.Many2one(
        "workshop.job.card",
        string="Job Card",
        required=True,
        readonly=True,
        ondelete="cascade",
    )
    repair_service_ids = fields.Many2many(
        "workshop.repair.service",
        string="Repair Services",
    )

    def action_add(self):
        self.ensure_one()
        if not self.repair_service_ids:
            raise ValidationError(_("Please select at least one Repair Service."))
        if self.job_card_id.state not in {"draft", "sent"}:
            raise UserError(
                _("Repair Services can only be added in Draft or Sent to Customer.")
            )

        existing_services = self.job_card_id.service_line_ids.repair_service_id
        services_to_add = self.repair_service_ids - existing_services
        if services_to_add:
            service_lines = self.env["workshop.job.card.service"].with_context(
                skip_option_generation=True
            ).create(
                [
                    {
                        "job_card_id": self.job_card_id.id,
                        "repair_service_id": service.id,
                    }
                    for service in services_to_add
                ]
            )
            service_lines.with_context(
                skip_option_generation=False
            )._generate_option_lines()
        return {"type": "ir.actions.act_window_close"}
