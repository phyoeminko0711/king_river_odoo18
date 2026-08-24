from odoo import api, models
from odoo.osv import expression


class ProductProduct(models.Model):
    _inherit = "product.product"

    def _get_workshop_product_display_name(self):
        self.ensure_one()
        parts = []
        if self.default_code:
            parts.append("[%s]" % self.default_code)
        parts.append(self.name or self.product_tmpl_id.name or "")
        if self.brand_id:
            parts.append("[%s]" % self.brand_id.display_name)
        return " ".join(part for part in parts if part).strip()

    @api.model
    def name_search(self, name="", args=None, operator="ilike", limit=100):
        if not self.env.context.get("workshop_product_display"):
            return super().name_search(name=name, args=args, operator=operator, limit=limit)

        args = list(args or [])
        domain = args
        if name:
            search_domain = expression.OR(
                [
                    [("default_code", operator, name)],
                    [("name", operator, name)],
                    [("brand_id.name", operator, name)],
                ]
            )
            domain = expression.AND([args, search_domain])
        products = self.search(domain, limit=limit)
        return [(product.id, product._get_workshop_product_display_name()) for product in products]

    def web_read(self, specification):
        result = super().web_read(specification)
        if not self.env.context.get("workshop_product_display"):
            return result

        names_by_id = {
            product.id: product._get_workshop_product_display_name()
            for product in self
        }
        for values in result:
            if "display_name" in values and values.get("id") in names_by_id:
                values["display_name"] = names_by_id[values["id"]]
        return result