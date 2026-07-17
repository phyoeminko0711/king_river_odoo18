from odoo import api, fields, models


class RepairOrder(models.Model):
    _inherit = "repair.order"

    job_card_id = fields.Many2one(
        "workshop.job.card",
        string="Job Card",
        readonly=True,
        copy=False,
        ondelete="restrict",
        index=True,
    )
    customer_vehicle_id = fields.Many2one(
        "workshop.customer.vehicle",
        string="Customer Vehicle",
        readonly=True,
        copy=False,
        ondelete="restrict",
        index=True,
    )
    # Upgrade compatibility for the first module version. Its inherited Repair
    # view referenced ``vehicle_id`` and can still be present until an upgrade
    # finishes obsolete-record cleanup. Keep this alias out of current views.
    vehicle_id = fields.Many2one(
        related="customer_vehicle_id",
        string="Legacy Customer Vehicle",
        store=True,
        readonly=True,
    )

    _sql_constraints = [
        (
            "repair_order_job_card_unique",
            "unique(job_card_id)",
            "Only one Repair Order can be created for a Job Card.",
        )
    ]

    def action_view_job_card(self):
        self.ensure_one()
        if not self.job_card_id:
            return False
        return {
            "type": "ir.actions.act_window",
            "name": "Job Card",
            "res_model": "workshop.job.card",
            "view_mode": "form",
            "res_id": self.job_card_id.id,
        }


class WorkshopCustomerVehicle(models.Model):
    _inherit = "workshop.customer.vehicle"

    job_card_ids = fields.One2many(
        "workshop.job.card", "vehicle_id", string="Job Cards", readonly=True
    )

    @api.depends("job_card_ids")
    def _compute_job_card_count(self):
        grouped = self.env["workshop.job.card"]._read_group(
            [("vehicle_id", "in", self.ids)], ["vehicle_id"], ["__count"]
        )
        counts = {vehicle.id: count for vehicle, count in grouped}
        for vehicle in self:
            vehicle.job_card_count = counts.get(vehicle.id, 0)
