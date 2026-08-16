from odoo import api, fields, models
from odoo.tools import float_compare


class ResCurrencyRate(models.Model):
    _inherit = "res.currency.rate"

    def _get_currency_revaluation_companies(self):
        self.ensure_one()
        if self.company_id:
            return self.company_id
        sources = self.env["sale.price.update"].sudo().search(
            [
                ("state", "=", "approved"),
                ("cost_source", "in", ["landed_cost", "currency_revaluation"]),
                ("source_currency_id", "=", self.currency_id.id),
            ]
        )
        return sources.mapped("company_id")

    def _get_currency_rate_revaluation_snapshots(self):
        self.ensure_one()
        revaluation_date = fields.Date.to_date(self.name) or fields.Date.context_today(self)
        snapshots = []
        for company in self._get_currency_revaluation_companies():
            company_currency = company.currency_id
            effective_value = self.currency_id._convert(
                1.0,
                company_currency,
                company,
                revaluation_date,
            )
            snapshots.append(
                {
                    "currency": self.currency_id,
                    "company": company,
                    "date": revaluation_date,
                    "effective_value": effective_value,
                }
            )
        return snapshots

    def _run_currency_rate_revaluations(self, work_items):
        sale_price_update_model = self.env["sale.price.update"].with_context(
            skip_currency_sale_price_revaluation=True
        )
        grouped = {}
        for currency, company, revaluation_date in work_items:
            grouped[(currency.id, company.id, revaluation_date)] = (currency, company, revaluation_date)
        for currency, company, revaluation_date in grouped.values():
            stats = sale_price_update_model._revalue_products_for_currency(
                currency=currency,
                company=company,
                revaluation_date=revaluation_date,
            )
            sale_price_update_model._log_currency_revaluation_summary(
                stats,
                currency=currency,
                revaluation_date=revaluation_date,
                rate_change=True,
            )

    @api.model_create_multi
    def create(self, vals_list):
        rates = super().create(vals_list)
        if not self.env.context.get("skip_currency_sale_price_revaluation"):
            work_items = []
            for rate in rates:
                for snapshot in rate._get_currency_rate_revaluation_snapshots():
                    work_items.append(
                        (snapshot["currency"], snapshot["company"], snapshot["date"])
                    )
            if work_items:
                rates._run_currency_rate_revaluations(work_items)
        return rates

    def write(self, vals):
        relevant_fields = {"rate", "name", "currency_id", "company_id"}
        if self.env.context.get("skip_currency_sale_price_revaluation") or not relevant_fields.intersection(vals):
            return super().write(vals)

        old_snapshots = {}
        for rate in self:
            old_snapshots[rate.id] = rate._get_currency_rate_revaluation_snapshots()

        result = super().write(vals)

        work_items = []
        for rate in self:
            old_values_by_company = {
                snapshot["company"].id: snapshot["effective_value"]
                for snapshot in old_snapshots.get(rate.id, [])
            }
            for snapshot in rate._get_currency_rate_revaluation_snapshots():
                company = snapshot["company"]
                old_effective_value = old_values_by_company.get(company.id)
                if old_effective_value is None:
                    work_items.append((snapshot["currency"], company, snapshot["date"]))
                    continue
                if (
                    float_compare(
                        snapshot["effective_value"],
                        old_effective_value,
                        precision_rounding=company.currency_id.rounding,
                    )
                    > 0
                ):
                    work_items.append((snapshot["currency"], company, snapshot["date"]))
        if work_items:
            self._run_currency_rate_revaluations(work_items)
        return result