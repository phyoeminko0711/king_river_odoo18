from odoo import api, fields, models
from odoo.osv import expression


class ProductTemplate(models.Model):
    _inherit = "product.template"

    english_name = fields.Char(string="English Name")
    car_name = fields.Char(string="Car Name")
    lh_rh = fields.Char(string="LH/RH")
    model_engine = fields.Char(string="Model / Engine")

    def _get_internal_product_display_name(self):
        self.ensure_one()
        parts = []
        if self.default_code:
            parts.append("[%s]" % self.default_code)
        parts.append(self.name or "")
        suffix = ""
        if self.brand_id:
            suffix += "[%s]" % self.brand_id.display_name
        if self.model_engine:
            suffix += "[%s]" % self.model_engine
        if suffix:
            parts.append(suffix)
        return " ".join(part for part in parts if part).strip()

    @api.depends("default_code", "name", "brand_id.name", "model_engine")
    def _compute_display_name(self):
        super()._compute_display_name()
        for template in self:
            template.display_name = template._get_internal_product_display_name()

    @api.model
    def name_search(self, name="", args=None, operator="ilike", limit=100):
        args = list(args or [])
        domain = args
        if name:
            search_domain = expression.OR(
                [
                    [("default_code", operator, name)],
                    [("name", operator, name)],
                    [("brand_id.name", operator, name)],
                    [("model_engine", operator, name)],
                ]
            )
            domain = expression.AND([args, search_domain])
        templates = self.search(domain, limit=limit)
        return [
            (template.id, template._get_internal_product_display_name())
            for template in templates
        ]

    def web_read(self, specification):
        result = super().web_read(specification)
        names_by_id = {
            template.id: template._get_internal_product_display_name()
            for template in self
        }
        for values in result:
            if "display_name" in values and values.get("id") in names_by_id:
                values["display_name"] = names_by_id[values["id"]]
        return result
