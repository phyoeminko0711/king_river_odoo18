from odoo import api, fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    enable_sale_price_approval = fields.Boolean(
        string="Enable Sale Price Approval",
        config_parameter="purchase_sale_price_approval.enable_sale_price_approval",
    )
    include_service_products = fields.Boolean(
        string="Include Service Products",
        config_parameter="purchase_sale_price_approval.include_service_products",
    )
    allow_manual_approved_price = fields.Boolean(
        string="Allow Manual Approved Price",
        config_parameter="purchase_sale_price_approval.allow_manual_approved_price",
        default=True,
    )
    block_price_decrease = fields.Boolean(
        string="Block Price Decrease",
        config_parameter="purchase_sale_price_approval.block_price_decrease",
    )
    sale_price_rounding = fields.Float(
        string="Sale Price Rounding",
        config_parameter="purchase_sale_price_approval.sale_price_rounding",
        digits=(16, 4),
        help="Round calculated sale prices to the nearest configured value. "
        "Examples: 1, 10, 100, 1000.",
    )
    activity_user_ids = fields.Many2many(
        "res.users",
        string="Approval Activity Users",
        help="Users who should receive review activities when purchase orders create pending sale price updates.",
    )

    @api.model
    def get_values(self):
        res = super().get_values()
        params = self.env["ir.config_parameter"].sudo()
        user_ids = params.get_param("purchase_sale_price_approval.activity_user_ids", default="")
        res.update(
            activity_user_ids=[(6, 0, [int(user_id) for user_id in user_ids.split(",") if user_id])],
        )
        return res

    def set_values(self):
        super().set_values()
        params = self.env["ir.config_parameter"].sudo()
        for setting in self:
            params.set_param(
                "purchase_sale_price_approval.activity_user_ids",
                ",".join(str(user.id) for user in setting.activity_user_ids),
            )
