from odoo import api, fields, models


class WorkshopProductBrandType(models.Model):
    """Deprecated compatibility model with no UI or business logic."""

    _name = "workshop.product.brand.type"
    _description = "Legacy Workshop Product Brand Type"
    _order = "name, id"

    name = fields.Char(required=True, index=True)
    code = fields.Char(index=True)
    active = fields.Boolean(default=True)


class WorkshopProductBrand(models.Model):
    _name = "workshop.product.brand"
    _description = "Workshop Product Brand"
    _order = "name, id"

    name = fields.Char(string="Brand Name", required=True, index=True)
    code = fields.Char(string="Code", index=True)
    active = fields.Boolean(default=True)

    # Compatibility only. These fields are intentionally absent from all views
    # and have no workflow, default master data, or business logic.
    brand_type_id = fields.Many2one(
        "workshop.product.brand.type",
        string="Legacy Brand Type",
        ondelete="set null",
    )
    state = fields.Selection(
        [("draft", "Draft"), ("confirmed", "Confirmed")],
        string="Legacy State",
        default="draft",
    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            self._normalize_values(vals)
        return super().create(vals_list)

    def write(self, vals):
        self._normalize_values(vals)
        return super().write(vals)

    @staticmethod
    def _normalize_values(vals):
        for field_name in ("name", "code"):
            value = vals.get(field_name)
            if isinstance(value, str):
                vals[field_name] = value.strip() or False

