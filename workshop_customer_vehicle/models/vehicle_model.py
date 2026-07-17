from odoo import api, fields, models


class WorkshopVehicleModel(models.Model):
    _name = "workshop.vehicle.model"
    _description = "Vehicle Model"
    _order = "brand_id, name, id"

    name = fields.Char(required=True, index=True)
    brand_id = fields.Many2one(
        "workshop.vehicle.brand",
        required=True,
        index=True,
        ondelete="restrict",
    )
    active = fields.Boolean(default=True)

    _sql_constraints = [
        (
            "workshop_vehicle_model_brand_name_unique",
            "unique(brand_id, name)",
            "This vehicle model already exists for the selected brand.",
        ),
    ]

    @api.depends("name", "brand_id.name")
    def _compute_display_name(self):
        for record in self:
            record.display_name = (
                f"{record.brand_id.name} / {record.name}"
                if record.brand_id
                else record.name
            )

