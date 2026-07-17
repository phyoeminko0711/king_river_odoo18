from odoo import fields, models


class WorkshopVehicleBrand(models.Model):
    _name = "workshop.vehicle.brand"
    _description = "Vehicle Brand"
    _order = "name, id"

    name = fields.Char(required=True, index=True)
    active = fields.Boolean(default=True)

    _sql_constraints = [
        (
            "workshop_vehicle_brand_name_unique",
            "unique(name)",
            "A vehicle brand with this name already exists.",
        ),
    ]

