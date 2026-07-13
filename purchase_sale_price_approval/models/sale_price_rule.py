from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class SalePriceRule(models.Model):
    _name = "sale.price.rule"
    _description = "Sale Price Rule"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "priority asc, id desc"
    _check_company_auto = True

    name = fields.Char(required=True, tracking=True, string="Rule Name")
    company_id = fields.Many2one(
        "res.company",
        required=True,
        default=lambda self: self.env.company,
        index=True,
    )
    currency_id = fields.Many2one(
        "res.currency",
        required=True,
        default=lambda self: self.env.company.currency_id,
    )
    active = fields.Boolean(default=True)
    priority = fields.Integer(default=10, string="Priority")
    line_ids = fields.One2many("sale.price.rule.line", "rule_id", string="Pricing Rules")
    note = fields.Text()
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("active", "Active"),
            ("archived", "Archived"),
        ],
        default="draft",
        required=True,
        tracking=True,
    )

    def _validate_before_activation(self):
        for rule in self:
            if not rule.line_ids.filtered("active"):
                raise ValidationError(
                    _("Rule '%s' must contain at least one active pricing line before activation.")
                    % rule.display_name
                )
            invalid_lines = rule.line_ids.filtered(
                lambda line: line.to_amount < 0 or line.from_amount < 0 or line.markup_value < 0
            )
            if invalid_lines:
                raise ValidationError(
                    _("Rule '%s' contains invalid pricing lines. Review line amounts and markup values.")
                    % rule.display_name
                )

    def action_activate(self):
        self._validate_before_activation()
        self.with_context(skip_sale_price_rule_protection=True).write({"state": "active", "active": True})

    def action_set_to_draft(self):
        self.with_context(skip_sale_price_rule_protection=True).write({"state": "draft"})

    def action_archive(self):
        self.with_context(skip_sale_price_rule_protection=True).write({"state": "archived", "active": False})

    def write(self, vals):
        if self.env.context.get("skip_sale_price_rule_protection"):
            return super().write(vals)
        protected_rules = self.filtered(lambda rule: rule.state != "draft")
        if protected_rules:
            raise ValidationError(_("Only Draft rules can be modified."))
        return super().write(vals)

    def unlink(self):
        protected_rules = self.filtered(lambda rule: rule.state != "draft")
        if protected_rules:
            raise ValidationError(_("Only Draft rules can be deleted."))
        return super().unlink()


class SalePriceRuleLine(models.Model):
    _name = "sale.price.rule.line"
    _description = "Sale Price Rule Line"
    _order = "priority asc, sequence asc, valid_from desc, id desc"
    _check_company_auto = True

    rule_id = fields.Many2one("sale.price.rule", required=True, ondelete="cascade")
    company_id = fields.Many2one(related="rule_id.company_id", store=True, readonly=True)
    currency_id = fields.Many2one(related="rule_id.currency_id", store=True, readonly=True)
    sequence = fields.Integer(default=10)
    apply_on = fields.Selection(
        [
            ("all", "All Products"),
            ("category", "Product Category"),
            ("product", "Specific Product"),
        ],
        required=True,
        default="all",
    )
    categ_id = fields.Many2one("product.category", string="Product Category")
    product_tmpl_id = fields.Many2one("product.template", string="Product Template")
    product_id = fields.Many2one("product.product", string="Product")
    from_amount = fields.Monetary(required=True, default=0.0)
    to_amount = fields.Monetary(
        required=True,
        help="Use 0.0 to represent an unlimited upper bound.",
    )
    markup_type = fields.Selection(
        [
            ("percentage", "Percentage"),
            ("fixed", "Fixed Amount"),
        ],
        required=True,
        default="percentage",
    )
    markup_value = fields.Float(required=True)
    valid_from = fields.Date(required=True)
    valid_to = fields.Date()
    active = fields.Boolean(default=True)
    priority = fields.Integer(default=10)

    @api.onchange("apply_on")
    def _onchange_apply_on(self):
        if self.apply_on == "all":
            self.categ_id = False
            self.product_id = False
            self.product_tmpl_id = False
        elif self.apply_on == "category":
            self.product_id = False
            self.product_tmpl_id = False
        elif self.apply_on == "product":
            self.categ_id = False

    @api.onchange("product_id")
    def _onchange_product_id(self):
        for line in self:
            line.product_tmpl_id = line.product_id.product_tmpl_id

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            rule = self.env["sale.price.rule"].browse(vals.get("rule_id"))
            if rule and rule.state != "draft" and not self.env.context.get("skip_sale_price_rule_line_protection"):
                raise ValidationError(_("Pricing rule lines cannot be changed after the rule is activated."))
            product_id = vals.get("product_id")
            if product_id:
                vals["product_tmpl_id"] = self.env["product.product"].browse(product_id).product_tmpl_id.id
        return super().create(vals_list)

    def write(self, vals):
        if not self.env.context.get("skip_sale_price_rule_line_protection"):
            protected_lines = self.filtered(lambda line: line.rule_id.state != "draft")
            if protected_lines:
                raise ValidationError(_("Pricing rule lines cannot be changed after the rule is activated."))
        if vals.get("product_id"):
            vals["product_tmpl_id"] = self.env["product.product"].browse(vals["product_id"]).product_tmpl_id.id
        if vals.get("apply_on") == "all":
            vals.update({"categ_id": False, "product_id": False, "product_tmpl_id": False})
        elif vals.get("apply_on") == "category":
            vals.update({"product_id": False, "product_tmpl_id": False})
        elif vals.get("apply_on") == "product":
            vals.update({"categ_id": False})
        return super().write(vals)

    def unlink(self):
        protected_lines = self.filtered(lambda line: line.rule_id.state != "draft")
        if protected_lines and not self.env.context.get("skip_sale_price_rule_line_protection"):
            raise ValidationError(_("Pricing rule lines cannot be changed after the rule is activated."))
        return super().unlink()

    def name_get(self):
        result = []
        for line in self:
            if line.apply_on == "all":
                scope_name = _("All Products")
            elif line.apply_on == "category":
                scope_name = line.categ_id.display_name or _("Product Category")
            else:
                scope_name = line.product_id.display_name or _("Product")
            amount_range = _("%(from)s - %(to)s") % {
                "from": line.from_amount,
                "to": line.to_amount or _("Unlimited"),
            }
            markup = (
                _("%s%%") % line.markup_value
                if line.markup_type == "percentage"
                else _("%s Fixed") % line.markup_value
            )
            result.append((line.id, _("%(scope)s: %(range)s / %(markup)s") % {
                "scope": scope_name,
                "range": amount_range,
                "markup": markup,
            }))
        return result

    @api.constrains("apply_on", "categ_id", "product_tmpl_id", "product_id")
    def _check_scope_fields(self):
        for line in self:
            if line.apply_on == "all":
                if line.categ_id or line.product_tmpl_id or line.product_id:
                    raise ValidationError(
                        _("All Products rules cannot define product category or product fields.")
                    )
            elif line.apply_on == "category":
                if not line.categ_id:
                    raise ValidationError(_("Product Category is required for category-based rules."))
                if line.product_tmpl_id or line.product_id:
                    raise ValidationError(
                        _("Category rules cannot define Product Template or Product Variant.")
                    )
            elif line.apply_on == "product":
                if not (line.product_tmpl_id or line.product_id):
                    raise ValidationError(
                        _("Specific Product rules require either a Product Template or Product Variant.")
                    )
                if line.categ_id:
                    raise ValidationError(_("Specific Product rules cannot define Product Category."))

    @api.constrains("from_amount", "to_amount", "markup_value", "valid_from", "valid_to")
    def _check_amounts_and_dates(self):
        for line in self:
            if line.from_amount < 0:
                raise ValidationError(_("From Amount must be greater than or equal to zero."))
            if line.to_amount < 0:
                raise ValidationError(_("To Amount must be greater than or equal to zero."))
            if line.to_amount and line.to_amount <= line.from_amount:
                raise ValidationError(_("To Amount must be greater than From Amount unless it is 0 for unlimited."))
            if line.markup_value < 0:
                raise ValidationError(_("Markup Value must be greater than or equal to zero."))
            if line.valid_to and line.valid_to < line.valid_from:
                raise ValidationError(_("Valid To cannot be earlier than Valid From."))

    @api.constrains(
        "rule_id",
        "company_id",
        "currency_id",
        "apply_on",
        "categ_id",
        "product_tmpl_id",
        "product_id",
        "from_amount",
        "to_amount",
        "valid_from",
        "valid_to",
        "active",
    )
    def _check_overlapping_ranges(self):
        for line in self.filtered("active"):
            scope_domain = [
                ("id", "!=", line.id),
                ("active", "=", True),
                ("company_id", "=", line.company_id.id),
                ("currency_id", "=", line.currency_id.id),
                ("apply_on", "=", line.apply_on),
            ]
            if line.apply_on == "category":
                scope_domain.append(("categ_id", "=", line.categ_id.id))
            elif line.apply_on == "product":
                scope_domain.extend(
                    [
                        ("product_tmpl_id", "=", line.product_tmpl_id.id),
                        ("product_id", "=", line.product_id.id),
                    ]
                )
            else:
                scope_domain.extend(
                    [
                        ("categ_id", "=", False),
                        ("product_tmpl_id", "=", False),
                        ("product_id", "=", False),
                    ]
                )

            for other in self.search(scope_domain):
                if not self._ranges_overlap(
                    line.from_amount,
                    line.to_amount,
                    other.from_amount,
                    other.to_amount,
                ):
                    continue
                if not self._dates_overlap(
                    line.valid_from,
                    line.valid_to,
                    other.valid_from,
                    other.valid_to,
                ):
                    continue
                raise ValidationError(
                    _(
                        "Pricing rule line '%(line)s' overlaps with '%(other)s' for the same scope, "
                        "currency, amount range, and validity period."
                    )
                    % {
                        "line": line.display_name,
                        "other": other.display_name,
                    }
                )

    @api.model
    def _ranges_overlap(self, first_from, first_to, second_from, second_to):
        first_upper = float("inf") if not first_to else first_to
        second_upper = float("inf") if not second_to else second_to
        return max(first_from, second_from) < min(first_upper, second_upper)

    @api.model
    def _dates_overlap(self, first_from, first_to, second_from, second_to):
        first_upper = fields.Date.to_date(first_to) if first_to else fields.Date.to_date("9999-12-31")
        second_upper = fields.Date.to_date(second_to) if second_to else fields.Date.to_date("9999-12-31")
        return max(first_from, second_from) <= min(first_upper, second_upper)

    @api.model
    def _get_product_categories(self, product):
        categories = []
        category = product.categ_id
        while category:
            categories.append(category)
            category = category.parent_id
        return categories

    @api.model
    def _get_scope_rank(self, line, product):
        if line.apply_on == "product":
            if line.product_id and line.product_id == product:
                return 1
            if line.product_tmpl_id and line.product_tmpl_id == product.product_tmpl_id:
                return 2
            return False
        if line.apply_on == "category":
            categories = self._get_product_categories(product)
            if line.categ_id in categories:
                return 3 + categories.index(line.categ_id)
            return False
        return 999

    @api.model
    def _get_converted_purchase_price(self, purchase_price, source_currency, target_currency, company, effective_date):
        if source_currency == target_currency:
            return purchase_price
        return source_currency._convert(purchase_price, target_currency, company, effective_date)

    @api.model
    def _find_matching_rule_line(self, product, purchase_price, company, currency, effective_date):
        """Return the best matching rule line for a purchase unit price."""
        effective_date = fields.Date.to_date(effective_date)
        candidate_lines = self.search(
            [
                ("active", "=", True),
                ("rule_id.active", "=", True),
                ("rule_id.state", "=", "active"),
                ("company_id", "=", company.id),
                ("valid_from", "<=", effective_date),
                "|",
                ("valid_to", "=", False),
                ("valid_to", ">=", effective_date),
            ]
        )

        best_line = self.browse()
        best_key = False
        for line in candidate_lines:
            scope_rank = self._get_scope_rank(line, product)
            if scope_rank is False:
                continue
            converted_price = self._get_converted_purchase_price(
                purchase_price,
                currency,
                line.currency_id,
                company,
                effective_date,
            )
            if converted_price < line.from_amount:
                continue
            if line.to_amount and converted_price >= line.to_amount:
                continue

            valid_from = fields.Date.to_date(line.valid_from)
            sort_key = (
                scope_rank,
                line.priority,
                line.sequence,
                -valid_from.toordinal(),
                -line.id,
            )
            if best_key is False or sort_key < best_key:
                best_key = sort_key
                best_line = line
        return best_line
    _rec_name = "display_name"
