from odoo import _, api, fields, models
from odoo.exceptions import AccessError, ValidationError
from odoo.tools import float_compare


class SaleOrder(models.Model):
    _inherit = "sale.order"

    available_sale_product_ids = fields.Many2many(
        "product.product",
        compute="_compute_available_sale_products",
    )
    available_sale_template_ids = fields.Many2many(
        "product.template",
        compute="_compute_available_sale_products",
    )

    stock_requester_id = fields.Many2one(
        "hr.employee",
        string="Stock Requester",
        tracking=True,
        check_company=True,
    )
    stock_issuer_id = fields.Many2one(
        "hr.employee",
        string="Stock Issuer",
        tracking=True,
        check_company=True,
    )
    analytic_account_id = fields.Many2one(
        "account.analytic.account",
        string="Analytic Account",
        check_company=True,
        tracking=True,
    )

    def _get_available_sale_products(self):
        self.ensure_one()
        if not self.warehouse_id:
            return self.env["product.product"]
        products = self.env["product.product"].with_company(self.company_id).sudo()
        quant_domain = products.with_context(
            warehouse_id=self.warehouse_id.id
        )._get_domain_locations()[0]
        quantities = self.env["stock.quant"].sudo()._read_group(
            quant_domain, ["product_id"], ["available_quantity:sum"]
        )
        product_ids = [
            product.id
            for product, quantity in quantities
            if product.is_storable
            and float_compare(quantity, 0.0, precision_rounding=product.uom_id.rounding) > 0
        ]
        return products.browse(product_ids)

    @api.depends("warehouse_id")
    def _compute_available_sale_products(self):
        for order in self:
            products = order._get_available_sale_products()
            order.available_sale_product_ids = products
            order.available_sale_template_ids = products.product_tmpl_id

    def _check_warehouse_sale_stock(self):
        for order in self.filtered(lambda order: order.state in ("draft", "sent")):
            quantities = {}
            for line in order.order_line:
                product = line.product_id
                if line.display_type or line.is_downpayment or not product.is_storable:
                    continue
                quantity = line.product_uom._compute_quantity(
                    line.product_uom_qty, product.uom_id, round=False
                )
                quantities[product] = quantities.get(product, 0.0) + quantity
            if not quantities:
                continue
            if not order.warehouse_id:
                raise ValidationError(_("Select a warehouse before adding stocked products."))
            products = self.env["product.product"].sudo().with_company(
                order.company_id
            ).with_context(warehouse_id=order.warehouse_id.id)
            for product, requested in quantities.items():
                available = products.browse(product.id).free_qty
                rounding = product.uom_id.rounding
                if float_compare(available, 0.0, precision_rounding=rounding) <= 0:
                    raise ValidationError(
                        _("%(product)s has no available stock in %(warehouse)s.",
                          product=product.display_name, warehouse=order.warehouse_id.name)
                    )
                if float_compare(requested, available, precision_rounding=rounding) > 0:
                    raise ValidationError(
                        _("%(product)s: requested %(requested)g exceeds %(available)g available in %(warehouse)s.",
                          product=product.display_name, requested=requested,
                          available=available, warehouse=order.warehouse_id.name)
                    )

    @api.constrains("warehouse_id", "team_id", "order_line")
    def _check_warehouse_sale_stock_constraint(self):
        self._check_warehouse_sale_stock()

    def action_confirm(self):
        self._check_warehouse_sale_stock()
        return super().action_confirm()

    def _get_product_catalog_domain(self):
        domain = super()._get_product_catalog_domain()
        self.ensure_one()
        return domain + [
            "|", ("is_storable", "=", False),
            ("id", "in", self._get_available_sale_products().ids),
        ]

    @api.constrains("pricelist_id")
    def _check_line_pricelist_currencies(self):
        for order in self:
            if any(
                line.pricelist_override_id
                and line.pricelist_override_id.currency_id != order.currency_id
                for line in order.order_line
            ):
                raise ValidationError(
                    _("Line pricelists must use the same currency as the sale order.")
                )

    def _get_header_analytic_distribution(self):
        self.ensure_one()
        if not self.analytic_account_id:
            return False
        return {str(self.analytic_account_id.id): 100.0}

    def _apply_header_analytic_distribution(self):
        for order in self:
            distribution = order._get_header_analytic_distribution()
            order.order_line.filtered(lambda line: not line.display_type).analytic_distribution = distribution

    @api.onchange("analytic_account_id")
    def _onchange_analytic_account_id(self):
        self._apply_header_analytic_distribution()

    def _get_sales_team_warehouse(self, team, company):
        """Return the team's warehouse after validating company consistency."""
        if not team or not team.warehouse_id:
            return self.env["stock.warehouse"]
        warehouse = team.warehouse_id
        if company and warehouse.company_id and warehouse.company_id != company:
            raise ValidationError(
                _("The selected Warehouse must belong to the same company as the Sales Team.")
            )
        return warehouse

    def _apply_sales_team_warehouse(self):
        """Set the sale order warehouse from its sales team when configured."""
        for order in self:
            warehouse = order._get_sales_team_warehouse(order.team_id, order.company_id)
            if warehouse:
                order.warehouse_id = warehouse

    @api.onchange("team_id")
    def _onchange_team_id_set_warehouse(self):
        self._apply_sales_team_warehouse()

    @api.onchange("user_id")
    def _onchange_user_id_set_team_warehouse(self):
        self._compute_team_id()
        self._apply_sales_team_warehouse()

    @api.model_create_multi
    def create(self, vals_list):
        team_model = self.env["crm.team"]
        for vals in vals_list:
            team_id = vals.get("team_id")
            if team_id and "warehouse_id" not in vals:
                company = self.env["res.company"].browse(
                    vals.get("company_id") or self.env.company.id
                )
                warehouse = self._get_sales_team_warehouse(team_model.browse(team_id), company)
                if warehouse:
                    vals["warehouse_id"] = warehouse.id

        orders = super().create(vals_list)

        for order, vals in zip(orders, vals_list):
            if "warehouse_id" not in vals and order.team_id.warehouse_id:
                order.with_context(skip_sale_team_warehouse=True)._apply_sales_team_warehouse()
            if vals.get("analytic_account_id"):
                order._apply_header_analytic_distribution()
        return orders

    def write(self, vals):
        result = super().write(vals)
        if (
            not self.env.context.get("skip_sale_team_warehouse")
            and "warehouse_id" not in vals
            and ("team_id" in vals or "user_id" in vals)
        ):
            self.with_context(skip_sale_team_warehouse=True)._apply_sales_team_warehouse()
        if "analytic_account_id" in vals:
            self._apply_header_analytic_distribution()
        return result



class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    @api.constrains("product_id", "product_uom_qty", "product_uom", "order_id")
    def _check_warehouse_sale_stock_constraint(self):
        self.mapped("order_id")._check_warehouse_sale_stock()

    pricelist_override_id = fields.Many2one(
        "product.pricelist",
        string="Pricelist Override",
        copy=False,
    )
    pricelist_type_id = fields.Many2one(
        "product.pricelist",
        string="Pricelist Type",
        compute="_compute_pricelist_type_id",
        inverse="_inverse_pricelist_type_id",
        store=True,
        readonly=False,
        precompute=True,
    )

    @api.depends("order_id.pricelist_id", "pricelist_override_id")
    def _compute_pricelist_type_id(self):
        for line in self:
            line.pricelist_type_id = line.pricelist_override_id or line.order_id.pricelist_id

    def _inverse_pricelist_type_id(self):
        for line in self:
            order_pricelist = line.order_id.pricelist_id
            line.pricelist_override_id = (
                line.pricelist_type_id
                if line.pricelist_type_id != order_pricelist
                else False
            )

    @api.constrains("pricelist_override_id", "pricelist_type_id", "order_id")
    def _check_pricelist_type_currency(self):
        for line in self:
            if (
                line.pricelist_type_id
                and line.order_id.currency_id
                and line.pricelist_type_id.currency_id != line.order_id.currency_id
            ):
                raise ValidationError(
                    _("The line pricelist must use the same currency as the sale order.")
                )

    @api.depends("product_id", "product_uom", "product_uom_qty", "pricelist_type_id")
    def _compute_pricelist_item_id(self):
        for line in self:
            pricelist = line.pricelist_type_id or line.order_id.pricelist_id
            if not line.product_id or line.display_type or not pricelist:
                line.pricelist_item_id = False
            else:
                line.pricelist_item_id = pricelist._get_product_rule(
                    line.product_id,
                    quantity=line.product_uom_qty or 1.0,
                    uom=line.product_uom,
                    date=line._get_order_date(),
                )

    @api.depends("product_id", "product_uom", "product_uom_qty", "pricelist_type_id")
    def _compute_price_unit(self):
        return super()._compute_price_unit()

    @api.depends("product_id", "product_uom", "product_uom_qty", "pricelist_type_id")
    def _compute_discount(self):
        return super()._compute_discount()

    def _get_pricelist_price_context(self):
        context = super()._get_pricelist_price_context()
        context["pricelist"] = self.pricelist_type_id.id or self.order_id.pricelist_id.id
        return context

    @api.onchange("pricelist_type_id")
    def _onchange_pricelist_type_id(self):
        for line in self:
            line._inverse_pricelist_type_id()
            line._check_pricelist_type_currency()
            if line.product_id and not line.display_type and not line.qty_invoiced:
                line._compute_pricelist_item_id()
                line._reset_price_unit()
                line._compute_discount()

    def _check_pricelist_type_access(self, vals):
        if (
            (vals.get("pricelist_type_id") or vals.get("pricelist_override_id"))
            and not self.env.su
            and not self.env.user.has_group("sale_team_warehouse.group_allow_pricelist_type")
        ):
            raise AccessError(_("You are not allowed to change the line pricelist."))

    @api.onchange("product_id", "product_template_id")
    def _onchange_product_apply_order_analytic_account(self):
        for line in self:
            if line.order_id.analytic_account_id and not line.display_type:
                line.analytic_distribution = line.order_id._get_header_analytic_distribution()

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            self._check_pricelist_type_access(vals)
            if vals.get("analytic_distribution") or not vals.get("order_id"):
                continue
            order = self.env["sale.order"].browse(vals["order_id"])
            if order.analytic_account_id:
                vals["analytic_distribution"] = order._get_header_analytic_distribution()
        lines = super().create(vals_list)
        for line, vals in zip(lines, vals_list):
            if vals.get("pricelist_type_id") and "price_unit" not in vals:
                line._compute_pricelist_item_id()
                line._reset_price_unit()
                line._compute_discount()
        return lines

    def write(self, vals):
        self._check_pricelist_type_access(vals)
        result = super().write(vals)
        if "pricelist_type_id" in vals and "price_unit" not in vals:
            for line in self.filtered(lambda line: line.product_id and not line.display_type and not line.qty_invoiced):
                line._compute_pricelist_item_id()
                line._reset_price_unit()
                line._compute_discount()
        return result
