# Copyright 2019 Kitti Upariphutthiphong <kittiu@ecosoft.co.th>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import Command, api, fields, models
from odoo.exceptions import ValidationError


class HrExpense(models.Model):
    _inherit = "hr.expense"

    advance = fields.Boolean(string="Employee Advance", default=False)
    clearing_product_id = fields.Many2one(
        comodel_name="product.product",
        string="Clearing Product",
        tracking=True,
        domain="[('can_be_expensed', '=', True),"
        "'|', ('company_id', '=', False), ('company_id', '=', company_id)]",
        ondelete="restrict",
        help="Optional: On the clear advance, the clearing "
        "product will create default product line.",
    )
    av_line_id = fields.Many2one(
        comodel_name="hr.expense",
        string="Ref: Advance",
        ondelete="set null",
        help="Expense created from this advance expense line",
    )

    def _get_product_advance(self):
        return self.env.ref("hr_expense_advance_clearing.product_emp_advance", False)

    @api.constrains("advance")
    def _check_advance(self):
        for expense in self.filtered("advance"):
            emp_advance = expense._get_product_advance()
            if not emp_advance.property_account_expense_id:
                raise ValidationError(
                    self.env._("Employee advance product has no payable account")
                )
            if expense.product_id != emp_advance:
                raise ValidationError(
                    self.env._("Employee advance, selected product is not valid")
                )
            if expense.account_id != emp_advance.property_account_expense_id:
                raise ValidationError(
                    self.env._(
                        "Employee advance, account must be the same payable account"
                    )
                )
            if expense.tax_ids:
                raise ValidationError(
                    self.env._("Employee advance, all taxes must be removed")
                )
            if expense.payment_mode != "own_account":
                raise ValidationError(
                    self.env._("Employee advance, paid by must be employee")
                )
        return True

    @api.onchange("advance")
    def onchange_advance(self):
        self.tax_ids = False
        if self.advance:
            self.product_id = self._get_product_advance()

    def _get_move_line_src(self, move_line_name, partner_id):
        self.ensure_one()
        price_unit = self.price_unit or self.total_amount
        quantity = self.quantity if self.price_unit else 1
        taxes = self.tax_ids.with_context(round=True).compute_all(
            price_unit, self.currency_id, quantity, self.product_id
        )
        ml_src_dict = {
            "name": move_line_name,
            "quantity": quantity,
            "amount_currency": self.total_amount_currency,
            "account_id": self.account_id.id,
            "product_id": self.product_id.id,
            "product_uom_id": self.product_uom_id.id,
            # "analytic_distribution": self.analytic_distribution,
            "expense_id": self.id,
            "partner_id": partner_id,
            "tax_ids": [Command.set(self.tax_ids.ids)],
            "tax_tag_ids": [Command.set(taxes["base_tags"])],
            "currency_id": self.currency_id.id,
        }
        return ml_src_dict

    def _get_move_line_dst(
        self,
        move_line_name,
        partner_id,
        total_amount,
        total_amount_currency,
        account_advance,
    ):
        account_date = (
            self.date
            or self.sheet_id.accounting_date
            or fields.Date.context_today(self)
        )
        ml_dst_dict = {
            "name": move_line_name,
            "debit": total_amount > 0 and total_amount,
            "credit": total_amount < 0 and -total_amount,
            "account_id": account_advance.id,
            "date_maturity": account_date,
            "amount_currency": total_amount_currency,
            "currency_id": self.currency_id.id,
            "expense_id": self.id,
            "partner_id": partner_id,
        }
        return ml_dst_dict

    # @api.depends('product_id', 'account_id', 'employee_id')
    # def _compute_analytic_distribution(self):
    #     super(HrExpense, self)._compute_analytic_distribution()
    #
    #     for expense in self:
            # If compute did not return any analytic distribution
            # if not expense.analytic_distribution:
                # employee = expense.employee_id
                # if employee.department_id and employee.department_id.analytic_distribution:
                #     expense.analytic_distribution = dict(employee.department_id.analytic_distribution)

    # @api.onchange('employee_id')
    # def _onchange_employee_analytic_distribution(self):
    #     """Handle UI changes"""
    #     if self.employee_id and self.employee_id.department_id:
    #         analytic_dist = self.employee_id.department_id.analytic_distribution
    #         self.analytic_distribution = dict(analytic_dist) if analytic_dist else False
    #     else:
    #         self.analytic_distribution = False

    # @api.model_create_multi
    # def create(self, vals_list):
    #     """Handle programmatic creation"""
    #     for vals in vals_list:
    #         if vals.get('employee_id') and not vals.get('analytic_distribution'):
    #             employee = self.env['hr.employee'].browse(vals['employee_id'])
    #             # if employee.department_id and employee.department_id.analytic_distribution:
    #             #     vals['analytic_distribution'] = dict(employee.department_id.analytic_distribution)
    #
    #     return super().create(vals_list)
    #
    # def write(self, vals):
    #     """Handle updates"""
    #     if 'employee_id' in vals and 'analytic_distribution' not in vals:
    #         employee = self.env['hr.employee'].browse(vals['employee_id'])
    #         if employee.department_id and employee.department_id.analytic_distribution:
    #             vals['analytic_distribution'] = dict(employee.department_id.analytic_distribution)
    #         else:
    #             vals['analytic_distribution'] = False
    #
    #     return super().write(vals)

    # def _prepare_payments_vals(self):
    #     move_vals, payment_vals = super()._prepare_payments_vals()
    #
    #     # Add branch to payment
    #     payment_vals.update({
    #         'res_branch_id': self.branch_id.id,
    #         'analytic_distribution': self.analytic_distribution,
    #     })
    #
    #     return move_vals, payment_vals