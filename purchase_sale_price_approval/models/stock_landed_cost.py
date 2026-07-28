from collections import defaultdict

from odoo import _, api, fields, models
from odoo.tools import float_compare
from odoo.tools.float_utils import float_is_zero


class StockLandedCost(models.Model):
    _inherit = "stock.landed.cost"

    sale_price_update_ids = fields.One2many(
        "sale.price.update",
        "landed_cost_id",
        string="Sale Price Updates",
    )
    sale_price_update_count = fields.Integer(
        compute="_compute_sale_price_update_count",
        string="Sale Price Updates",
    )

    @api.depends("sale_price_update_ids")
    def _compute_sale_price_update_count(self):
        for cost in self:
            cost.sale_price_update_count = len(cost.sale_price_update_ids)

    def button_validate(self):
        result = super().button_validate()
        self.filtered(lambda cost: cost.state == "done")._generate_sale_price_updates_from_landed_cost()
        return result

    def _get_landed_cost_product_groups(self):
        """Group validated valuation lines into one weighted landed unit cost per product."""
        self.ensure_one()
        groups = {}
        company_currency = self.company_id.currency_id

        for product in self.valuation_adjustment_lines.mapped("product_id"):
            product_lines = self.valuation_adjustment_lines.filtered(
                lambda line: line.product_id == product and line.move_id
            )
            moves = defaultdict(lambda: {"lines": self.env["stock.valuation.adjustment.lines"], "additional": 0.0})

            for line in product_lines:
                move_values = moves[line.move_id.id]
                move_values["lines"] |= line
                move_values["quantity"] = line.quantity
                move_values["former_cost"] = line.former_cost
                move_values["additional"] += line.additional_landed_cost

            valuation_lines = self.env["stock.valuation.adjustment.lines"]
            total_quantity = 0.0
            total_final_cost = 0.0
            for move_values in moves.values():
                quantity = move_values.get("quantity", 0.0)
                if float_is_zero(quantity, precision_rounding=product.uom_id.rounding):
                    continue
                valuation_lines |= move_values["lines"]
                total_quantity += quantity
                total_final_cost += move_values.get("former_cost", 0.0) + move_values["additional"]

            if (
                valuation_lines
                and not float_is_zero(total_quantity, precision_rounding=product.uom_id.rounding)
                and not company_currency.is_zero(total_final_cost)
            ):
                groups[product] = {
                    "valuation_lines": valuation_lines,
                    "quantity": total_quantity,
                    "landed_unit_cost": total_final_cost / total_quantity if total_quantity else 0.0,
                }

        return groups

    def _resolve_purchase_source_from_landed_lines(self, valuation_lines):
        purchase_orders = valuation_lines.mapped("move_id.purchase_line_id.order_id")
        purchase_lines = valuation_lines.mapped("move_id.purchase_line_id")
        purchase_order = purchase_orders if len(purchase_orders) == 1 else self.env["purchase.order"]
        purchase_line = purchase_lines if len(purchase_lines) == 1 else self.env["purchase.order.line"]
        return purchase_order, purchase_line

    def _prepare_sale_price_update_values_from_landed_cost(
        self,
        product,
        valuation_lines,
        rule_line,
        landed_unit_cost,
        effective_date,
    ):
        """Prepare sale.price.update values from a validated landed cost product group."""
        self.ensure_one()
        sale_price_update_model = self.env["sale.price.update"]
        company_currency = self.company_id.currency_id
        rule_currency = rule_line.currency_id
        converted_landed_unit_cost = company_currency._convert(
            landed_unit_cost,
            rule_currency,
            self.company_id,
            effective_date,
        )
        old_sale_price_company = product.product_tmpl_id.with_company(self.company_id).list_price
        old_sale_price = company_currency._convert(
            old_sale_price_company,
            rule_currency,
            self.company_id,
            effective_date,
        )
        calculated_sale_price = sale_price_update_model._calculate_sale_price(
            converted_landed_unit_cost,
            rule_line.markup_type,
            rule_line.markup_value,
            rule_currency,
        )
        purchase_order, purchase_line = self._resolve_purchase_source_from_landed_lines(valuation_lines)
        return {
            "company_id": self.company_id.id,
            "currency_id": rule_currency.id,
            "landed_cost_id": self.id,
            "valuation_adjustment_line_ids": [(6, 0, valuation_lines.ids)],
            "purchase_order_id": purchase_order.id or False,
            "purchase_order_line_id": purchase_line.id or False,
            "product_id": product.id,
            "purchase_quantity": sum(
                valuation_lines.mapped("move_id").mapped(
                    lambda move: valuation_lines.filtered(lambda line: line.move_id == move)[:1].quantity
                )
            ),
            "purchase_uom_id": product.uom_id.id,
            "purchase_price": landed_unit_cost,
            "source_currency_id": company_currency.id,
            "landed_unit_cost": converted_landed_unit_cost,
            "converted_purchase_price": converted_landed_unit_cost,
            "old_sale_price": old_sale_price,
            "markup_type": rule_line.markup_type,
            "markup_value": rule_line.markup_value,
            "calculated_sale_price": calculated_sale_price,
            "approved_sale_price": calculated_sale_price,
            "rule_line_id": rule_line.id,
            "effective_date": effective_date,
            "conversion_date": effective_date,
            "requested_by": self.env.user.id,
            "cost_source": "landed_cost",
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
                        "Review the proposed sale price %(price)s for %(product)s created from landed cost %(landed_cost)s."
                    )
                    % {
                        "price": update.calculated_sale_price,
                        "product": update.product_id.display_name,
                        "landed_cost": self.display_name,
                    },
                )

    def _cancel_stale_pending_landed_update(self, product):
        self.ensure_one()
        stale_update = self.env["sale.price.update"].sudo().search(
            [
                ("landed_cost_id", "=", self.id),
                ("product_id", "=", product.id),
                ("cost_source", "=", "landed_cost"),
                ("state", "=", "pending"),
            ],
            order="id desc",
            limit=1,
        )
        if stale_update:
            stale_update.with_context(skip_sale_price_update_protection=True).write({"state": "cancelled"})
            stale_update.message_post(
                body=_(
                    "Cancelled because the recalculated landed-cost-based sale price is not greater than the current sale price."
                )
            )

    def _process_landed_cost_price_update(self, product, group_values, effective_date):
        self.ensure_one()
        sale_price_update_model = self.env["sale.price.update"].sudo()
        rule_line_model = self.env["sale.price.rule.line"].sudo()
        company_currency = self.company_id.currency_id
        landed_unit_cost = group_values["landed_unit_cost"]

        rule_line = rule_line_model._find_matching_rule_line(
            product,
            landed_unit_cost,
            self.company_id,
            company_currency,
            effective_date,
        )
        if not rule_line:
            self._cancel_stale_pending_landed_update(product)
            return sale_price_update_model.browse()

        vals = self._prepare_sale_price_update_values_from_landed_cost(
            product,
            group_values["valuation_lines"],
            rule_line,
            landed_unit_cost,
            effective_date,
        )

        if (
            float_compare(
                vals["calculated_sale_price"],
                vals["old_sale_price"],
                precision_rounding=rule_line.currency_id.rounding,
            )
            <= 0
        ):
            self._cancel_stale_pending_landed_update(product)
            return sale_price_update_model.browse()

        existing_updates = sale_price_update_model.search(
            [
                ("landed_cost_id", "=", self.id),
                ("product_id", "=", product.id),
                ("cost_source", "=", "landed_cost"),
            ],
            order="id desc",
        )
        latest_update = existing_updates[:1]

        if latest_update and not latest_update._has_meaningful_update_change(vals):
            return sale_price_update_model.browse()

        if latest_update:
            vals["previous_update_id"] = latest_update.id

        new_update = sale_price_update_model.create(vals)
        if latest_update and latest_update.state == "pending":
            latest_update.with_context(skip_sale_price_update_protection=True).write(
                {
                    "state": "superseded",
                    "superseded_by_id": new_update.id,
                }
            )
        return new_update

    def _generate_sale_price_updates_from_landed_cost(self):
        """Create pending sale price updates from validated landed costs only."""
        for cost in self:
            if cost.state != "done":
                continue

            created_updates = self.env["sale.price.update"]
            effective_date = cost.date or fields.Date.context_today(cost)
            product_groups = cost._get_landed_cost_product_groups()

            for product, group_values in product_groups.items():
                created_updates |= cost._process_landed_cost_price_update(product, group_values, effective_date)

            if created_updates:
                cost.message_post(
                    body=_("%s pending Sale Price Update record(s) created from validated Landed Cost.")
                    % len(created_updates)
                )
                cost._schedule_sale_price_activities(created_updates)
            elif not cost.sale_price_update_ids:
                cost.message_post(
                    body=_(
                        "No Sale Price Update was required because the calculated prices were not greater than the current sale prices."
                    )
                )

    def action_view_sale_price_updates(self):
        self.ensure_one()
        action = self.env.ref("purchase_sale_price_approval.action_sale_price_updates").read()[0]
        action["domain"] = [("landed_cost_id", "=", self.id)]
        action["context"] = {
            "default_landed_cost_id": self.id,
            "search_default_landed_cost_id": self.id,
        }
        return action
