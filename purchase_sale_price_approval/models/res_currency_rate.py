from odoo import api, fields, models


class ResCurrencyRate(models.Model):
    _inherit = "res.currency.rate"

    def _trigger_sale_price_currency_revaluation(self):
        if self.env.context.get("skip_sale_price_currency_revaluation"):
            return

        update_model = self.env["sale.price.update"].sudo()
        seen = set()
        for rate in self:
            currency = rate.currency_id
            company = rate.company_id or self.env.company
            if not currency or currency == company.currency_id:
                continue
            key = (currency.id, company.id, rate.name)
            if key in seen:
                continue
            seen.add(key)
            update_model.with_context(
                skip_sale_price_currency_revaluation=True
            )._run_currency_sale_price_revaluation(
                currency,
                company,
                rate.name or fields.Date.context_today(rate),
            )

    @api.model_create_multi
    def create(self, vals_list):
        rates = super().create(vals_list)
        rates._trigger_sale_price_currency_revaluation()
        return rates

    def write(self, vals):
        result = super().write(vals)
        if {"rate", "name", "currency_id", "company_id"}.intersection(vals):
            self._trigger_sale_price_currency_revaluation()
        return result
