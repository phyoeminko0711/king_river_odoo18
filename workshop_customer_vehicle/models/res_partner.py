from odoo import api, fields, models


class ResPartner(models.Model):
    _inherit = "res.partner"

    vehicle_ids = fields.One2many(
        "workshop.customer.vehicle",
        "customer_id",
        string="Vehicles",
    )
    vehicle_count = fields.Integer(compute="_compute_vehicle_count")

    @api.depends("vehicle_ids")
    def _compute_vehicle_count(self):
        counts = self.env["workshop.customer.vehicle"]._read_group(
            [("customer_id", "in", self.ids)],
            ["customer_id"],
            ["__count"],
        )
        count_by_partner = {partner.id: count for partner, count in counts}
        for partner in self:
            partner.vehicle_count = count_by_partner.get(partner.id, 0)

    def action_view_vehicles(self):
        self.ensure_one()
        action = self.env["ir.actions.actions"]._for_xml_id(
            "workshop_customer_vehicle.action_customer_vehicle"
        )
        action["domain"] = [("customer_id", "=", self.id)]
        action["context"] = {
            "default_customer_id": self.id,
            "search_default_customer_id": self.id,
        }
        return action

