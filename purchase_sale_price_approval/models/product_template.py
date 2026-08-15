from odoo import fields, models, _


class ProductTemplate(models.Model):
    _inherit = "product.template"

    sale_price_update_count = fields.Integer(
        string="Sale Price History",
        compute="_compute_sale_price_update_count",
    )

    def _compute_sale_price_update_count(self):
        update_model = self.env["sale.price.update"].sudo()
        for template in self:
            template.sale_price_update_count = update_model.search_count(
                [("product_tmpl_id", "=", template.id)]
            )

    def action_view_sale_price_history(self):
        self.ensure_one()
        action = self.env.ref("purchase_sale_price_approval.action_sale_price_updates").read()[0]
        action["domain"] = [("product_tmpl_id", "=", self.id)]
        action["context"] = {
            "search_default_group_source": 1,
            "default_product_id": self.product_variant_id.id,
        }
        action["name"] = _("Sale Price History")
        return action
