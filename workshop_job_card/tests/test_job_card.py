from lxml import etree

from odoo.exceptions import UserError, ValidationError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install")
class TestWorkshopJobCard(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.customer = cls.env["res.partner"].create(
            {"name": "Job Card Customer", "phone": "01 555 0100"}
        )
        cls.other_customer = cls.env["res.partner"].create({"name": "Other Customer"})
        cls.vehicle_brand = cls.env["workshop.vehicle.brand"].create(
            {"name": "JC Test Hyundai 18"}
        )
        cls.vehicle_model = cls.env["workshop.vehicle.model"].create(
            {"name": "JC Test Grand Starex 18", "brand_id": cls.vehicle_brand.id}
        )
        vehicle_values = {
            "vehicle_brand_id": cls.vehicle_brand.id,
            "vehicle_model_id": cls.vehicle_model.id,
            "chassis_no": "JC-CHASSIS",
            "engine_no": "JC-ENGINE",
            "color": "Silver",
        }
        cls.vehicle = cls.env["workshop.customer.vehicle"].create(
            {
                **vehicle_values,
                "customer_id": cls.customer.id,
                "plate_no": "JC-TEST-001",
                "mileage": 45000,
            }
        )
        cls.other_vehicle = cls.env["workshop.customer.vehicle"].create(
            {
                **vehicle_values,
                "customer_id": cls.other_customer.id,
                "plate_no": "JC-TEST-002",
            }
        )
        cls.job_position = cls.env["hr.job"].create({"name": "Technician"})
        cls.technician = cls.env["hr.employee"].create(
            {"name": "Workshop Technician", "job_id": cls.job_position.id}
        )
        cls.part_brand = cls.env["workshop.product.brand"].create(
            {"name": "JC Test Korea 18"}
        )
        cls.products = cls.env["product.product"]
        for name, code, price in (
            ("Brake Pad", "JC-BP", 125000),
            ("Premium Brake Pad", "JC-BP-P", 185000),
            ("Oil Filter", "JC-OF", 25000),
        ):
            cls.products |= cls.env["product.product"].create(
                {
                    "name": name,
                    "default_code": code,
                    "type": "consu",
                    "brand_id": cls.part_brand.id,
                    "list_price": price,
                }
            )

    def _create_card(self, **values):
        vals = {
            "customer_id": self.customer.id,
            "vehicle_id": self.vehicle.id,
            "technician_id": self.technician.id,
        }
        vals.update(values)
        return self.env["workshop.job.card"].create(vals)

    def _add_line(
        self, card, product=None, selected=False, service="Front Brake Repair", quantity=1
    ):
        product = product or self.products[0]
        return self.env["workshop.job.card.line"].create(
            {
                "job_card_id": card.id,
                "repair_service": service,
                "product_id": product.id,
                "quantity": quantity,
                "product_uom_id": product.uom_id.id,
                "unit_price": product.lst_price,
                "selected": selected,
            }
        )

    def test_header_related_details_and_mileage(self):
        card = self._create_card()
        self.assertRegex(card.name, rf"^JC/{card.job_card_date.year}/\d{{5}}$")
        self.assertEqual(card.mileage, self.vehicle.mileage)
        self.assertEqual(card.customer_phone, self.customer.phone)
        self.assertEqual(card.plate_no, self.vehicle.plate_no)
        self.assertEqual(card.vehicle_brand_id, self.vehicle_brand)
        self.assertEqual(card.vehicle_model_id, self.vehicle_model)
        self.assertEqual(card.technician_job_id, self.job_position)
        self.assertEqual(card.currency_id, self.env.company.currency_id)

    def test_vehicle_must_belong_to_customer(self):
        with self.assertRaisesRegex(ValidationError, "does not belong"):
            self._create_card(vehicle_id=self.other_vehicle.id)

    def test_direct_line_fields_amount_and_product_defaults(self):
        card = self._create_card()
        product = self.products[0]
        line = self.env["workshop.job.card.line"].new(
            {"job_card_id": card.id, "repair_service": "Brake", "product_id": product.id}
        )
        line._onchange_product_id()
        self.assertEqual(line.product_uom_id, product.uom_id)
        self.assertEqual(line.unit_price, product.lst_price)

        line = self._add_line(card, quantity=2)
        self.assertEqual(line.brand_id, self.part_brand)
        self.assertEqual(line.part_number, line.product_id.default_code)
        self.assertEqual(line.amount, 2 * line.unit_price)
        self.assertFalse(
            {"labour_rate", "labor_rate", "employee_cost"}.intersection(line._fields)
        )

    def test_only_one_selected_option_per_service(self):
        card = self._create_card()
        first = self._add_line(card, product=self.products[0], selected=True)
        second = self._add_line(card, product=self.products[1], selected=True)
        self.assertFalse(first.selected)
        self.assertTrue(second.selected)

        other_service = self._add_line(
            card, product=self.products[2], selected=True, service="Oil Service"
        )
        self.assertTrue(second.selected)
        self.assertTrue(other_service.selected)
        self.assertEqual(card.selected_line_count, 2)
        self.assertEqual(card.selected_total, second.amount + other_service.amount)

    def test_send_approve_and_backend_protection(self):
        card = self._create_card()
        with self.assertRaisesRegex(ValidationError, "at least one Repair Option"):
            card.action_send_to_customer()
        line = self._add_line(card)
        card.action_send_to_customer()
        with self.assertRaisesRegex(ValidationError, "Select at least one"):
            card.action_approve()
        line.selected = True
        card.action_approve()
        self.assertEqual(card.state, "approved")
        with self.assertRaisesRegex(UserError, "cannot be modified"):
            card.write({"diagnosis": "Changed through RPC"})
        with self.assertRaisesRegex(UserError, "cannot be modified"):
            line.write({"selected": False})

    def test_reject_cancel_and_reset(self):
        rejected = self._create_card()
        self._add_line(rejected)
        rejected.action_send_to_customer()
        rejected.action_reject()
        rejected.action_reset_to_draft()
        self.assertEqual(rejected.state, "draft")

        cancelled = self._create_card()
        cancelled.action_cancel()
        cancelled.action_reset_to_draft()
        self.assertEqual(cancelled.state, "draft")

    def test_repair_order_receives_only_selected_line(self):
        card = self._create_card()
        selected = self._add_line(card, product=self.products[0], selected=True)
        unselected = self._add_line(card, product=self.products[1])
        card.action_send_to_customer()
        card.action_approve()
        action = card.action_create_repair_order()

        repair = card.repair_order_id
        self.assertEqual(card.state, "repair_created")
        self.assertEqual(repair.job_card_id, card)
        self.assertEqual(repair.customer_vehicle_id, self.vehicle)
        self.assertEqual(repair.partner_id, self.customer)
        self.assertFalse(repair.product_id)
        self.assertEqual(repair.move_ids.product_id, selected.product_id)
        self.assertNotIn(unselected.product_id, repair.move_ids.product_id)
        self.assertEqual(repair.move_ids.product_uom_qty, selected.quantity)
        self.assertEqual(repair.move_ids.product_uom, selected.product_uom_id)
        self.assertEqual(repair.move_ids.price_unit, selected.unit_price)
        self.assertEqual(action["res_id"], repair.id)
        with self.assertRaisesRegex(UserError, "already exists"):
            card.action_create_repair_order()

    def test_form_has_one_direct_repair_options_design(self):
        form = etree.fromstring(self.env.ref("workshop_job_card.view_job_card_form").arch_db)
        option_fields = form.xpath("//field[@name='line_ids']")
        self.assertEqual(len(option_fields), 3)
        self.assertFalse(form.xpath("//field[@name='option_line_ids']"))
        self.assertFalse(form.xpath("//field[@name='service_line_ids']"))
        draft_columns = option_fields[0].xpath("./list/field/@name")
        for field_name in (
            "repair_service", "product_id", "brand_id", "part_number", "warranty",
            "quantity", "product_uom_id", "unit_price", "amount", "selected",
        ):
            self.assertIn(field_name, draft_columns)
        self.assertTrue(form.xpath("//field[@name='selected_line_count']"))
        self.assertTrue(form.xpath("//field[@name='selected_total']"))

        sent = form.xpath("//field[@name='line_ids'][@invisible=\"state != 'sent'\"]")[0]
        self.assertEqual(sent.xpath("./list/@create"), ["0"])
        self.assertEqual(sent.xpath("./list/field[@name='selected']/@readonly"), [])

    def test_exact_workflow_states(self):
        selection = dict(self.env["workshop.job.card"]._fields["state"].selection)
        self.assertEqual(
            set(selection),
            {"draft", "sent", "approved", "repair_created", "rejected", "cancelled"},
        )
        self.assertFalse({"inspection", "prepared"}.intersection(selection))
