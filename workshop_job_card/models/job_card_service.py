from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class WorkshopJobCardService(models.Model):
    _name = "workshop.job.card.service"
    _description = "Job Card Repair Service"
    _rec_name = "repair_service_id"
    _order = "sequence, id"

    sequence = fields.Integer(default=10)
    job_card_id = fields.Many2one(
        "workshop.job.card",
        required=True,
        ondelete="cascade",
        index=True,
    )
    repair_service_id = fields.Many2one(
        "workshop.repair.service",
        string="Repair Service",
        required=True,
        ondelete="restrict",
        index=True,
    )
    part_number = fields.Char(
        string="Part Number",
        help="Enter a product default code to compare same-part options by brand.",
    )
    lh_rh = fields.Selection(
        [("lh", "LH"), ("rh", "RH")],
        string="LH/RH",
    )
    option_line_ids = fields.One2many(
        "workshop.job.card.line",
        "job_card_service_id",
        string="Product Options",
    )
    selected_option_id = fields.Many2one(
        "workshop.job.card.line",
        compute="_compute_selected_option",
        readonly=True,
    )
    selected_amount = fields.Monetary(
        compute="_compute_selected_option",
        readonly=True,
    )
    currency_id = fields.Many2one(
        related="job_card_id.currency_id",
        store=True,
        readonly=True,
    )
    job_card_state = fields.Selection(
        related="job_card_id.state",
        store=True,
        readonly=True,
    )

    # Retained only so databases from the original nested-service version keep
    # their historical text while moving to repair_service_id.
    name = fields.Char(string="Legacy Service Name")

    _sql_constraints = [
        (
            "workshop_job_card_service_unique",
            "unique(job_card_id, repair_service_id)",
            "The same Repair Service cannot be added more than once to one Job Card.",
        ),
    ]

    @api.depends("option_line_ids.selected", "option_line_ids.amount")
    def _compute_selected_option(self):
        for service_line in self:
            selected_option = service_line.option_line_ids.filtered("selected")[:1]
            service_line.selected_option_id = selected_option
            service_line.selected_amount = (
                selected_option.amount if selected_option else 0.0
            )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            card = self.env["workshop.job.card"].browse(vals.get("job_card_id"))
            if card and card.state not in {"draft", "sent"}:
                raise UserError(
                    _(
                        "Repair Services can only be added to a Draft or "
                        "Sent Job Card."
                    )
                )
            if vals.get("repair_service_id") and not vals.get("name"):
                vals["name"] = self.env["workshop.repair.service"].browse(
                    vals["repair_service_id"]
                ).name
        service_lines = super().create(vals_list)
        service_lines._generate_option_lines()
        return service_lines

    def write(self, vals):
        changing_service = "repair_service_id" in vals
        changing_option_basis = bool({"repair_service_id", "part_number", "lh_rh"}.intersection(vals))
        if changing_service and any(line.job_card_id.state != "draft" for line in self):
            raise UserError(
                _("The Repair Service can only be changed on a Draft Job Card.")
            )
        result = super().write(vals)
        if changing_option_basis and not self.env.context.get("skip_option_generation"):
            self._generate_option_lines()
        return result

    def action_remove_service_line(self):
        self.unlink()
        return {"type": "ir.actions.client", "tag": "reload"}

    def unlink(self):
        if any(line.job_card_id.state not in {"draft", "sent"} for line in self):
            raise UserError(
                _(
                    "Repair Services can only be removed while the Job Card is "
                    "in Draft or Sent to Customer state."
                )
            )
        option_lines = self.mapped("option_line_ids")
        if option_lines:
            option_lines.with_context(
                skip_job_card_state_check=True,
                skip_option_generation=True,
                skip_selection_sync=True,
            ).unlink()
        return super().unlink()

    @api.onchange("repair_service_id", "part_number", "lh_rh")
    def _onchange_repair_option_basis(self):
        self._generate_option_lines(onchange=True)

    def _get_comparison_products(self):
        self.ensure_one()
        Product = self.env["product.product"]
        part_number = (self.part_number or "").strip()
        if part_number:
            return Product.search(
                [
                    ("active", "=", True),
                    ("product_tmpl_id.active", "=", True),
                    ("type", "in", ("consu", "service")),
                    ("default_code", "=", part_number),
                ],
                order="brand_id, name, id",
            )
        return self.repair_service_id.product_ids.filtered(
            lambda product: product.active and product.product_tmpl_id.active
        )

    @api.constrains("part_number")
    def _check_part_number_has_products(self):
        for service_line in self.filtered("part_number"):
            if not service_line._get_comparison_products():
                raise ValidationError(
                    _("No active Product Options found for Part Number %s.")
                    % service_line.part_number
                )

    def _prepare_option_line_values(self, product):
        self.ensure_one()
        return {
            "job_card_service_id": self.id,
            "product_id": product.id,
            "lh_rh": self.lh_rh,
            "quantity": 1.0,
            "product_uom_id": product.uom_id.id,
            "unit_price": product.lst_price,
            "selected": False,
            "generated_by_service": True,
        }

    def _generate_option_lines(self, onchange=False):
        """Synchronize product options from part number without overwriting user prices."""
        if self.env.context.get("skip_option_generation"):
            return

        OptionLine = self.env["workshop.job.card.line"]
        for service_line in self:
            products = service_line._get_comparison_products()
            obsolete = service_line.option_line_ids.filtered(
                lambda option: option.generated_by_service
                and not option.selected
                and option.product_id not in products
            )

            if onchange:
                kept_lines = service_line.option_line_ids - obsolete
                existing_products = kept_lines.mapped("product_id")
                new_lines = OptionLine
                for product in products - existing_products:
                    option = OptionLine.new(service_line._prepare_option_line_values(product))
                    option.job_card_service_id = service_line
                    new_lines |= option
                for option in kept_lines.filtered("generated_by_service"):
                    option.lh_rh = service_line.lh_rh
                service_line.option_line_ids = kept_lines | new_lines
                continue

            if service_line.job_card_id.state not in {"draft", "sent"}:
                continue
            if obsolete:
                obsolete.with_context(skip_option_generation=True).unlink()
            existing_products = service_line.option_line_ids.mapped("product_id")
            values = [
                service_line._prepare_option_line_values(product)
                for product in products - existing_products
            ]
            if values:
                OptionLine.with_context(
                    skip_option_generation=True,
                    skip_job_card_state_check=True,
                ).create(values)
            generated_options = service_line.option_line_ids.filtered("generated_by_service")
            if generated_options:
                generated_options.with_context(
                    skip_job_card_state_check=True,
                    skip_selection_sync=True,
                ).write({"lh_rh": service_line.lh_rh})
