from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class WorkshopCustomerVehicle(models.Model):
    _name = "workshop.customer.vehicle"
    _description = "Customer Vehicle"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _rec_name = "plate_no"
    _order = "name desc, id desc"

    name = fields.Char(
        string="Vehicle Reference",
        required=True,
        readonly=True,
        copy=False,
        default=lambda self: _("New"),
        index=True,
    )
    customer_id = fields.Many2one(
        "res.partner",
        string="Customer",
        required=True,
        index=True,
        ondelete="restrict",
        tracking=True,
    )
    vehicle_brand_id = fields.Many2one(
        "workshop.vehicle.brand",
        string="Vehicle Brand",
        required=True,
        index=True,
        ondelete="restrict",
        tracking=True,
    )
    vehicle_model_id = fields.Many2one(
        "workshop.vehicle.model",
        string="Vehicle Model",
        required=True,
        index=True,
        ondelete="restrict",
        tracking=True,
    )
    model_year = fields.Integer(tracking=True)
    plate_no = fields.Char(string="Plate Number", required=True, index=True, tracking=True)
    chassis_no = fields.Char(string="Chassis Number", index=True, tracking=True)
    engine_no = fields.Char(string="Engine Number", index=True)
    color = fields.Char(tracking=True)
    mileage = fields.Float(tracking=True)
    mileage_uom = fields.Selection(
        [("km", "KM"), ("mile", "Mile")],
        string="Mileage Unit",
        required=True,
        default="km",
    )
    transmission = fields.Selection(
        [
            ("manual", "Manual"),
            ("automatic", "Automatic"),
            ("cvt", "CVT"),
            ("other", "Other"),
        ]
    )
    fuel_type = fields.Selection(
        [
            ("petrol", "Petrol"),
            ("diesel", "Diesel"),
            ("hybrid", "Hybrid"),
            ("electric", "Electric"),
            ("other", "Other"),
        ],
        tracking=True,
    )
    image_1920 = fields.Image(string="Vehicle Photo", max_width=1920, max_height=1920)
    active = fields.Boolean(default=True, tracking=True)
    note = fields.Text(string="Notes")
    job_card_count = fields.Integer(compute="_compute_job_card_count")

    _sql_constraints = [
        (
            "workshop_customer_vehicle_name_unique",
            "unique(name)",
            "The vehicle reference must be unique.",
        ),
        (
            "workshop_customer_vehicle_customer_plate_unique",
            "unique(customer_id, plate_no)",
            "This customer already has a vehicle with the same plate number.",
        ),
        (
            "workshop_customer_vehicle_mileage_nonnegative",
            "check(mileage >= 0)",
            "Mileage cannot be negative.",
        ),
    ]

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get("name") or vals.get("name") == _("New"):
                vals["name"] = self.env["ir.sequence"].next_by_code(
                    "workshop.customer.vehicle"
                ) or _("New")
            self._normalize_identifiers(vals)
        return super().create(vals_list)

    def write(self, vals):
        self._normalize_identifiers(vals)
        return super().write(vals)

    @staticmethod
    def _normalize_identifiers(vals):
        for field_name in ("plate_no", "chassis_no", "engine_no"):
            if field_name not in vals or not isinstance(vals[field_name], str):
                continue
            normalized = vals[field_name].strip().upper()
            vals[field_name] = normalized or False

    @api.depends("plate_no", "vehicle_brand_id.name", "vehicle_model_id.name")
    def _compute_display_name(self):
        for record in self:
            details = " ".join(
                part
                for part in (record.vehicle_brand_id.name, record.vehicle_model_id.name)
                if part
            )
            plate = record.plate_no or _("No Plate")
            record.display_name = f"[{plate}] {details}".strip()

    def _compute_job_card_count(self):
        """Extension point for the future workshop Job Card module."""
        for record in self:
            record.job_card_count = 0

    @api.onchange("vehicle_brand_id")
    def _onchange_vehicle_brand_id(self):
        if self.vehicle_model_id.brand_id != self.vehicle_brand_id:
            self.vehicle_model_id = False

    @api.constrains("vehicle_brand_id", "vehicle_model_id")
    def _check_vehicle_model_brand(self):
        for record in self:
            if record.vehicle_model_id.brand_id != record.vehicle_brand_id:
                raise ValidationError(
                    _("The selected vehicle model does not belong to the selected brand.")
                )

    @api.constrains("mileage")
    def _check_mileage(self):
        if any(record.mileage < 0 for record in self):
            raise ValidationError(_("Mileage cannot be negative."))

    @api.constrains("customer_id", "plate_no")
    def _check_duplicate_customer_plate(self):
        for record in self:
            if record.customer_id and record.plate_no and self.search_count(
                [
                    ("customer_id", "=", record.customer_id.id),
                    ("plate_no", "=", record.plate_no),
                    ("id", "!=", record.id),
                ],
                limit=1,
            ):
                raise ValidationError(
                    _("This customer already has a vehicle with the same plate number.")
                )
