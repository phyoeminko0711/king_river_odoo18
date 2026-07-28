from odoo import _, api, fields, models


class PurchaseOrder(models.Model):
    _inherit = "purchase.order"

    sale_price_update_ids = fields.One2many("sale.price.update", "purchase_order_id", string="Sale Price Updates")
    sale_price_update_count = fields.Integer(compute="_compute_sale_price_update_counts")
    pending_sale_price_update_count = fields.Integer(compute="_compute_sale_price_update_counts")

    @api.depends("sale_price_update_ids.state")
    def _compute_sale_price_update_counts(self):
        for order in self:
            order.sale_price_update_count = len(order.sale_price_update_ids)
            order.pending_sale_price_update_count = len(
                order.sale_price_update_ids.filtered(lambda update: update.state == "pending")
            )

    @api.model
    def _get_sale_price_approval_settings(self):
        return {
            "enabled": True,
            "include_service_products": False,
        }

    def button_confirm(self):
        return super().button_confirm()

    def button_done(self):
        return super().button_done()

    def button_cancel(self):
        result = super().button_cancel()
        self._cancel_related_sale_price_updates()
        return result

    def _should_create_sale_price_update(self, vals):
        return False

    def _prepare_sale_price_update_values(self, order_line, rule_line, effective_date):
        self.ensure_one()
        sale_price_update_model = self.env["sale.price.update"]
        company_currency = self.company_id.currency_id
        converted_purchase_price = order_line.currency_id._convert(
            order_line.price_unit,
            rule_line.currency_id,
            self.company_id,
            effective_date,
        )
        old_sale_price_company = order_line.product_id.product_tmpl_id.with_company(self.company_id).list_price
        old_sale_price = company_currency._convert(
            old_sale_price_company,
            rule_line.currency_id,
            self.company_id,
            effective_date,
        )
        calculated_sale_price = sale_price_update_model._calculate_sale_price(
            converted_purchase_price,
            rule_line.markup_type,
            rule_line.markup_value,
            rule_line.currency_id,
        )
        return {
            "company_id": self.company_id.id,
            "currency_id": rule_line.currency_id.id,
            "purchase_order_id": self.id,
            "purchase_order_line_id": order_line.id,
            "product_id": order_line.product_id.id,
            "purchase_quantity": order_line.product_qty,
            "purchase_uom_id": order_line.product_uom.id,
            "purchase_price": order_line.price_unit,
            "source_currency_id": order_line.currency_id.id,
            "converted_purchase_price": converted_purchase_price,
            "old_sale_price": old_sale_price,
            "markup_type": rule_line.markup_type,
            "markup_value": rule_line.markup_value,
            "calculated_sale_price": calculated_sale_price,
            "approved_sale_price": calculated_sale_price,
            "rule_line_id": rule_line.id,
            "effective_date": effective_date,
            "conversion_date": effective_date,
            "requested_by": self.env.user.id,
        }

    def _schedule_sale_price_activities(self, updates):
        if not updates:
            return
        users = self.env.ref(
            "purchase_sale_price_approval.group_sale_price_manager"
        ).users.filtered(lambda user: self.company_id in user.company_ids)
        activity_type = self.env.ref("purchase_sale_price_approval.mail_activity_sale_price_review")
        for update in updates:
            for user in users:
                update.activity_schedule(
                    activity_type_id=activity_type.id,
                    user_id=user.id,
                    note=_(
                        "Review the proposed sale price %(price)s for %(product)s created from purchase order %(po)s."
                    )
                    % {
                        "price": update.calculated_sale_price,
                        "product": update.product_id.display_name,
                        "po": update.purchase_order_id.display_name,
                    },
                )

    def _has_meaningful_update_change(self, existing_update, new_vals):
        monetary_fields = [
            "purchase_price",
            "converted_purchase_price",
            "calculated_sale_price",
            "approved_sale_price",
        ]
        for field_name in monetary_fields:
            if existing_update[field_name] != new_vals.get(field_name):
                return True
        if existing_update.rule_line_id.id != new_vals.get("rule_line_id"):
            return True
        return False

    def _generate_pending_sale_price_updates(self):
        return self.env["sale.price.update"]

    def _cancel_related_sale_price_updates(self):
        for order in self:
            pending_updates = order.sale_price_update_ids.filtered(lambda update: update.state == "pending")
            approved_updates = order.sale_price_update_ids.filtered(lambda update: update.state == "approved")
            if pending_updates:
                pending_updates.with_context(skip_sale_price_update_protection=True).write({"state": "cancelled"})
                pending_updates.message_post(
                    body=_("Cancelled because the source Purchase Order was cancelled.")
                )
            if approved_updates:
                approved_updates.message_post(
                    body=_(
                        "The source Purchase Order was cancelled. The approved sale price was kept for audit integrity and was not reverted automatically."
                    )
                )
            if pending_updates or approved_updates:
                order.message_post(
                    body=_(
                        "Sale Price Update records were reviewed after Purchase Order cancellation. Pending records were cancelled; approved records were kept unchanged."
                    )
                )

    def action_view_sale_price_updates(self):
        self.ensure_one()
        action = self.env.ref("purchase_sale_price_approval.action_sale_price_updates").read()[0]
        action["domain"] = [("purchase_order_id", "=", self.id)]
        action["context"] = {
            "default_purchase_order_id": self.id,
            "search_default_purchase_order_id": self.id,
        }
        return action
