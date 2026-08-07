from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class ProductTemplate(models.Model):
    _inherit = "product.template"

    is_workshop_service = fields.Boolean(string="Workshop Service")
    is_labour_cost = fields.Boolean(string="Labour Cost")

    @api.constrains("is_workshop_service", "is_labour_cost")
    def _check_workshop_service_flags(self):
        for template in self:
            if template.is_workshop_service and template.is_labour_cost:
                raise ValidationError(
                    _("A product cannot be both Workshop Service and Labour Cost.")
                )

    @api.constrains("type", "is_workshop_service", "is_labour_cost")
    def _check_workshop_service_flags_only_for_services(self):
        for template in self:
            if template.type != "service" and (
                template.is_workshop_service or template.is_labour_cost
            ):
                raise ValidationError(
                    _("Workshop Service and Labour Cost can only be enabled on Service products.")
                )

    @api.onchange("type")
    def _onchange_type_clear_workshop_service_flags(self):
        if self.type != "service":
            self.is_workshop_service = False
            self.is_labour_cost = False
