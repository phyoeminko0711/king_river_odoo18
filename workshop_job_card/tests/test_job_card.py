import base64

from lxml import etree
from psycopg2 import IntegrityError

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

    def _complete_inspection_action(self, action):
        wizard = self.env[action["res_model"]].browse(action["res_id"])
        while wizard.current_line_id:
            option = wizard.current_line_id.result_type_id.option_ids.filtered(
                lambda result: result.active and result.is_positive
            )[:1]
            wizard.current_result_option_id = option.id
            wizard.action_answer_selected()
        return wizard.job_card_id._get_latest_inspection(wizard.inspection_type)

    def _wizard_from_action(self, action):
        return self.env[action["res_model"]].browse(action["res_id"])

    def _complete_pre_customer_inspections(self, card):
        customer_check = card._get_latest_inspection("customer_check")
        if not customer_check or customer_check.state != "completed":
            customer_check = self._complete_inspection_action(card.action_customer_check())
        technician_inspection = card._get_latest_inspection("technician_inspection")
        if not technician_inspection or technician_inspection.state != "completed":
            technician_inspection = self._complete_inspection_action(card.action_technician_inspection())
        return customer_check, technician_inspection

    def _add_line(
        self,
        card,
        product=None,
        selected=False,
        service="Front Brake Repair",
        quantity=1,
        service_line=None,
    ):
        product = product or self.products[0]
        if not service_line:
            service_master = self.env["workshop.repair.service"].search(
                [("name", "=", service)], limit=1
            ) or self.env["workshop.repair.service"].create({"name": service})
            service_line = self.env["workshop.job.card.service"].search(
                [
                    ("job_card_id", "=", card.id),
                    ("repair_service_id", "=", service_master.id),
                ],
                limit=1,
            ) or self.env["workshop.job.card.service"].create(
                {
                    "job_card_id": card.id,
                    "repair_service_id": service_master.id,
                }
            )
        return self.env["workshop.job.card.line"].create(
            {
                "job_card_service_id": service_line.id,
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
            {
                "job_card_service_id": self.env["workshop.job.card.service"].create(
                    {
                        "job_card_id": card.id,
                        "repair_service_id": self.env["workshop.repair.service"].create(
                            {"name": "Brake Product Default Test"}
                        ).id,
                    }
                ).id,
                "product_id": product.id,
            }
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
        self.assertEqual(card.total_amount, second.amount + other_service.amount)

        first.write({"selected": True})
        self.assertTrue(first.selected)
        self.assertFalse(second.selected)
        self.assertTrue(other_service.selected)

    def test_selection_onchange_replaces_sibling_immediately(self):
        card = self._create_card()
        service = self.env["workshop.repair.service"].create(
            {"name": "Selection Onchange Service"}
        )
        service_line = self.env["workshop.job.card.service"].new(
            {"job_card_id": card.id, "repair_service_id": service.id}
        )
        first = self.env["workshop.job.card.line"].new(
            {
                "product_id": self.products[0].id,
                "selected": True,
            }
        )
        second = self.env["workshop.job.card.line"].new(
            {
                "product_id": self.products[1].id,
                "selected": True,
            }
        )
        first.job_card_service_id = service_line
        second.job_card_service_id = service_line
        service_line.option_line_ids = first | second

        second._onchange_selected()

        self.assertFalse(first.selected)
        self.assertTrue(second.selected)

    def test_selection_context_flag_cannot_bypass_validation(self):
        card = self._create_card()
        first = self._add_line(card, product=self.products[0], selected=True)
        second = self._add_line(card, product=self.products[1])

        with self.assertRaisesRegex(ValidationError, "Only one Product Option"):
            with self.env.cr.savepoint():
                second.with_context(skip_selection_sync=True).write(
                    {"selected": True}
                )

        first.invalidate_recordset(["selected"])
        second.invalidate_recordset(["selected"])
        self.assertTrue(first.selected)
        self.assertFalse(second.selected)

    def test_send_approve_and_backend_protection(self):
        card = self._create_card()
        with self.assertRaisesRegex(ValidationError, "at least one Repair Service"):
            self._complete_pre_customer_inspections(card)
            card.action_send_to_customer()
        line = self._add_line(card)
        self._complete_pre_customer_inspections(card)
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

    def test_send_requires_options_for_every_repair_service(self):
        card = self._create_card()
        empty_service = self.env["workshop.repair.service"].create(
            {"name": "Empty Brake Inspection"}
        )
        self.env["workshop.job.card.service"].create(
            {"job_card_id": card.id, "repair_service_id": empty_service.id}
        )

        with self.assertRaisesRegex(
            ValidationError,
            "(?s)Product Option.*Empty Brake Inspection",
        ):
            self._complete_pre_customer_inspections(card)
            card.action_send_to_customer()

    def test_approve_requires_one_selection_for_each_service(self):
        card = self._create_card()
        selected = self._add_line(
            card,
            product=self.products[0],
            service="Selected General Service",
            selected=True,
        )
        brake = self._add_line(
            card,
            product=self.products[1],
            service="Front Brake Repair Approval",
        )
        oil = self._add_line(
            card,
            product=self.products[2],
            service="Engine Oil Change Approval",
        )
        self._complete_pre_customer_inspections(card)
        card.action_send_to_customer()

        with self.assertRaises(ValidationError) as error:
            card.action_approve()
        message = str(error.exception)
        self.assertIn("Please select one Product Option", message)
        self.assertIn("- Front Brake Repair Approval", message)
        self.assertIn("- Engine Oil Change Approval", message)

        brake.selected = True
        oil.selected = True
        card.action_approve()
        self.assertEqual(card.state, "approved")
        self.assertTrue(selected.selected)

    def test_reject_cancel_and_reset(self):
        rejected = self._create_card()
        self._add_line(rejected)
        self._complete_pre_customer_inspections(rejected)
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
        self._complete_pre_customer_inspections(card)
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

    def test_workshop_service_product_flags_are_validated(self):
        with self.assertRaisesRegex(
            ValidationError,
            "A product cannot be both Workshop Service and Labour Cost",
        ):
            self.env["product.template"].create(
                {
                    "name": "Invalid Dual Service Flag",
                    "type": "service",
                    "is_workshop_service": True,
                    "is_labour_cost": True,
                }
            )
        with self.assertRaisesRegex(
            ValidationError,
            "can only be enabled on Service products",
        ):
            self.env["product.template"].create(
                {
                    "name": "Invalid Stock Service Flag",
                    "type": "consu",
                    "is_labour_cost": True,
                }
            )

    def test_repair_order_receives_labour_and_service_charge_lines(self):
        labour_product = self.env["product.product"].create(
            {
                "name": "Job Card Labour Cost",
                "type": "service",
                "is_labour_cost": True,
            }
        )
        service_product = self.env["product.product"].create(
            {
                "name": "Job Card Workshop Service Cost",
                "type": "service",
                "is_workshop_service": True,
            }
        )
        card = self._create_card(labour_cost=15000.0, service_cost=25000.0)
        self._add_line(card, product=self.products[0], selected=True)
        self._complete_pre_customer_inspections(card)
        card.action_send_to_customer()
        card.action_approve()
        card.action_create_repair_order()

        repair = card.repair_order_id
        self.assertEqual(len(repair.move_ids), 1)
        self.assertEqual(len(repair.repair_charge_line_ids), 2)
        labour_line = repair.repair_charge_line_ids.filtered(
            lambda line: line.charge_type == "labour"
        )
        service_line = repair.repair_charge_line_ids.filtered(
            lambda line: line.charge_type == "service"
        )
        self.assertEqual(labour_line.product_id, labour_product)
        self.assertEqual(labour_line.price_unit, 15000.0)
        self.assertEqual(service_line.product_id, service_product)
        self.assertEqual(service_line.price_unit, 25000.0)

    def test_repair_charge_product_configuration_is_required(self):
        card = self._create_card(labour_cost=15000.0)
        self._add_line(card, product=self.products[0], selected=True)
        self._complete_pre_customer_inspections(card)
        card.action_send_to_customer()
        card.action_approve()

        with self.assertRaisesRegex(
            ValidationError,
            "No Labour Cost service product is configured",
        ):
            card.action_create_repair_order()

    def test_inspections_are_created_only_from_workflow_buttons(self):
        card = self._create_card()
        template = self.env.ref("workshop_job_card.inspection_template_customer_check")

        with self.assertRaisesRegex(UserError, "Inspection history can only be created"):
            self.env["workshop.job.card.inspection"].create(
                {
                    "job_card_id": card.id,
                    "inspection_type": "customer_check",
                    "template_id": template.id,
                    "creation_source": "job_card_button",
                }
            )

        action = card.action_customer_check()
        self.assertEqual(action["res_model"], "workshop.inspection.check.wizard")
        self.assertFalse(card.inspection_ids)
        inspection = self._complete_inspection_action(action)
        self.assertEqual(inspection.creation_source, "job_card_button")
        self.assertEqual(inspection.inspection_type, "customer_check")
        self.assertTrue(inspection.line_ids)

    def test_inspection_buttons_do_not_create_duplicates(self):
        card = self._create_card()
        first_action = card.action_customer_check()
        second_action = card.action_customer_check()
        self.assertEqual(first_action["res_model"], second_action["res_model"])
        self.assertEqual(
            len(card.inspection_ids.filtered(lambda inspection: inspection.inspection_type == "customer_check")),
            0,
        )

        customer_check = self._complete_inspection_action(first_action)
        self.assertTrue(card.customer_check_completed)

        technician_first = card.action_technician_inspection()
        technician_second = card.action_technician_inspection()
        self.assertEqual(technician_first["res_model"], technician_second["res_model"])

    def test_single_checkpoint_wizard_dynamic_result_navigation(self):
        card = self._create_card()
        wizard = self._wizard_from_action(card.action_customer_check())
        first_line = wizard.line_ids.sorted(lambda line: (line.sequence, line.id))[0]
        second_line = wizard.line_ids.sorted(lambda line: (line.sequence, line.id))[1]
        positive_option = first_line.result_type_id.option_ids.filtered(lambda option: option.is_positive)[:1]
        remark_option = second_line.result_type_id.option_ids.filtered("requires_remark")[:1]

        self.assertEqual(wizard.current_line_id, first_line)
        self.assertEqual(wizard.progress_text, "Checkpoint 1 of %s" % len(wizard.line_ids))
        self.assertFalse(card.inspection_ids)

        wizard.current_result_option_id = positive_option.id
        wizard.action_answer_selected()
        self.assertEqual(first_line.result_option_id, positive_option)
        self.assertEqual(wizard.current_line_id, second_line)

        wizard.current_remark = "Glass cracked"
        wizard.current_result_option_id = remark_option.id
        wizard.action_answer_selected()
        self.assertEqual(second_line.result_option_id, remark_option)
        self.assertEqual(second_line.remark, "Glass cracked")

        wizard.action_previous_checkpoint()
        self.assertEqual(wizard.current_line_id, second_line)
        self.assertEqual(second_line.result_option_id, remark_option)

    def test_single_checkpoint_no_requires_remark_when_configured(self):
        card = self._create_card()
        wizard = self._wizard_from_action(card.action_customer_check())
        required_line = wizard.line_ids.filtered(
            lambda line: line.result_type_id.option_ids.filtered("requires_remark")
        )[:1]
        remark_option = required_line.result_type_id.option_ids.filtered("requires_remark")[:1]
        wizard.current_line_id = required_line.id
        wizard.current_result_option_id = remark_option.id
        wizard.current_remark = required_line.remark or False

        with self.assertRaisesRegex(ValidationError, "Please enter a remark"):
            wizard.action_answer_selected()

        wizard.current_remark = "Customer items in vehicle"
        wizard.action_answer_selected()
        self.assertEqual(required_line.result_option_id, remark_option)

    def test_history_is_created_on_final_answer_only(self):
        card = self._create_card()
        wizard = self._wizard_from_action(card.action_customer_check())

        self.assertFalse(card.inspection_ids)

        total = len(wizard.line_ids)
        while wizard.current_line_id and not card.inspection_ids:
            option = wizard.current_line_id.result_type_id.option_ids.filtered(
                lambda result: result.active and result.is_positive
            )[:1]
            wizard.current_result_option_id = option.id
            wizard.action_answer_selected()

        inspection = card._get_latest_inspection("customer_check")
        self.assertEqual(inspection.state, "completed")
        self.assertEqual(len(inspection.line_ids), total)
        self.assertTrue(card.customer_check_completed)

    def test_inspection_required_photo_is_copied_to_history_line(self):
        card = self._create_card()
        template = self.env.ref("workshop_job_card.inspection_template_customer_check")
        template_line = template.line_ids.sorted(lambda line: (line.sequence, line.id))[0]
        template_line.write(
            {
                "photo_required": True,
                "allow_multiple_photos": False,
            }
        )
        wizard = self._wizard_from_action(card.action_customer_check())
        first_line = wizard.current_line_id
        option = first_line.result_type_id.option_ids.filtered(
            lambda result: result.active and result.is_positive
        )[:1]
        wizard.current_result_option_id = option.id

        with self.assertRaisesRegex(
            ValidationError,
            "Please attach at least one photo for this checkpoint.",
        ):
            wizard.action_answer_selected()

        attachment = self.env["ir.attachment"].create(
            {
                "name": "windshield.jpg",
                "type": "binary",
                "datas": base64.b64encode(b"fake image"),
                "mimetype": "image/jpeg",
                "res_model": "workshop.inspection.check.wizard.line",
                "res_id": first_line.id,
            }
        )
        first_line.attachment_ids = attachment
        wizard.action_answer_selected()

        wizard.action_previous_checkpoint()
        self.assertEqual(wizard.current_line_id, first_line)
        self.assertEqual(first_line.attachment_ids, attachment)
        wizard.current_result_option_id = option.id
        wizard.action_answer_selected()

        while wizard.current_line_id:
            option = wizard.current_line_id.result_type_id.option_ids.filtered(
                lambda result: result.active and result.is_positive
            )[:1]
            wizard.current_result_option_id = option.id
            wizard.action_answer_selected()

        inspection = card._get_latest_inspection("customer_check")
        history_line = inspection.line_ids.sorted(lambda line: (line.sequence, line.id))[0]
        self.assertEqual(len(history_line.attachment_ids), 1)
        self.assertNotEqual(history_line.attachment_ids, attachment)
        self.assertEqual(
            history_line.attachment_ids.res_model,
            "workshop.job.card.inspection.line",
        )
        self.assertEqual(history_line.attachment_ids.res_id, history_line.id)

    def test_template_change_does_not_change_completed_history(self):
        card = self._create_card()
        wizard = self._wizard_from_action(card.action_customer_check())
        original_name = wizard.current_checkpoint_name
        while wizard.current_line_id:
            option = wizard.current_line_id.result_type_id.option_ids.filtered(
                lambda result: result.active and result.is_positive
            )[:1]
            wizard.current_result_option_id = option.id
            wizard.action_answer_selected()
        inspection = card._get_latest_inspection("customer_check")
        first_history_line = inspection.line_ids.sorted(lambda line: (line.sequence, line.id))[0]

        template_line = inspection.template_id.line_ids.sorted(lambda line: (line.sequence, line.id))[0]
        template_line.description = "Changed Template Checkpoint"

        self.assertEqual(first_history_line.checkpoint_name, original_name)

    def test_send_to_customer_requires_inspections(self):
        card = self._create_card()
        self._add_line(card, selected=True)

        with self.assertRaisesRegex(ValidationError, "Customer Check and Technician Inspection"):
            card.action_send_to_customer()

        self._complete_inspection_action(card.action_customer_check())
        with self.assertRaisesRegex(ValidationError, "Technician Inspection"):
            card.action_send_to_customer()

        self._complete_inspection_action(card.action_technician_inspection())
        card.action_send_to_customer()
        self.assertEqual(card.state, "sent")

    def test_delivery_inspection_blocks_repair_done_and_no_duplicates(self):
        card = self._create_card()
        self._add_line(card, selected=True)
        self._complete_pre_customer_inspections(card)
        card.action_send_to_customer()
        card.action_approve()
        card.action_create_repair_order()
        repair = card.repair_order_id

        first_action = repair.action_repair_done()
        second_action = repair.action_repair_done()
        self.assertEqual(first_action["res_model"], second_action["res_model"])

        delivery = self._complete_inspection_action(first_action)
        self.assertTrue(repair.delivery_inspection_completed)

    def test_repair_order_receives_one_selected_product_per_service(self):
        card = self._create_card()
        selected_brake = self._add_line(
            card,
            product=self.products[0],
            selected=True,
            service="Repair Transfer Brake Service",
            quantity=2,
        )
        unselected_brake = self._add_line(
            card,
            product=self.products[1],
            service="Repair Transfer Brake Service",
        )
        selected_oil = self._add_line(
            card,
            product=self.products[2],
            selected=True,
            service="Repair Transfer Oil Service",
            quantity=3,
        )
        self._complete_pre_customer_inspections(card)
        card.action_send_to_customer()
        card.action_approve()
        card.action_create_repair_order()

        moves = card.repair_order_id.move_ids
        self.assertEqual(moves.product_id, selected_brake.product_id | selected_oil.product_id)
        self.assertNotIn(unselected_brake.product_id, moves.product_id)
        brake_move = moves.filtered(
            lambda move: move.product_id == selected_brake.product_id
        )
        oil_move = moves.filtered(
            lambda move: move.product_id == selected_oil.product_id
        )
        self.assertEqual(brake_move.product_uom_qty, selected_brake.quantity)
        self.assertEqual(brake_move.product_uom, selected_brake.product_uom_id)
        self.assertEqual(brake_move.price_unit, selected_brake.unit_price)
        self.assertEqual(oil_move.product_uom_qty, selected_oil.quantity)
        self.assertEqual(oil_move.product_uom, selected_oil.product_uom_id)
        self.assertEqual(oil_move.price_unit, selected_oil.unit_price)
        self.assertEqual(card.state, "repair_created")

    def test_repair_creation_revalidates_every_service_selection(self):
        card = self._create_card()
        self._add_line(
            card,
            product=self.products[0],
            selected=True,
            service="Ready Repair Transfer Service",
        )
        self._add_line(
            card,
            product=self.products[1],
            service="Missing Repair Transfer Selection",
        )
        card._workflow_write({"state": "approved"})

        with self.assertRaisesRegex(
            ValidationError,
            "(?s)Please select one Product Option.*Missing Repair Transfer Selection",
        ):
            card.action_create_repair_order()
        self.assertFalse(card.repair_order_id)
        self.assertFalse(
            self.env["repair.order"].search([("job_card_id", "=", card.id)])
        )

    def test_form_has_one_direct_repair_options_design(self):
        form = etree.fromstring(self.env.ref("workshop_job_card.view_job_card_form").arch_db)
        option_fields = form.xpath("//field[@name='line_ids']")
        self.assertEqual(len(option_fields), 1)
        self.assertEqual(
            form.xpath("//field[@name='option_line_ids']"),
            [],
        )
        service_fields = form.xpath("//field[@name='service_line_ids']")
        self.assertFalse(service_fields)
        add_button = form.xpath(
            "//button[@name='action_open_add_repair_service_wizard']"
        )
        self.assertEqual(len(add_button), 1)
        self.assertEqual(
            add_button[0].get("invisible"),
            "state not in ['draft', 'sent']",
        )
        remove_button = form.xpath(
            "//button[@name='action_open_remove_repair_service_wizard']"
        )
        self.assertEqual(len(remove_button), 1)
        self.assertEqual(
            remove_button[0].get("invisible"),
            "state not in ['draft', 'sent'] or not service_line_ids",
        )
        self.assertEqual(
            remove_button[0].getparent(),
            add_button[0].getparent(),
        )
        draft_columns = option_fields[0].xpath("./list/field/@name")
        for field_name in (
            "repair_service_id", "product_id", "brand_id", "part_number", "warranty",
            "quantity", "product_uom_id", "unit_price", "amount", "selected",
        ):
            self.assertIn(field_name, draft_columns)
        self.assertFalse(form.xpath("//field[@name='repair_service']"))
        self.assertFalse(form.xpath("//field[@name='selected_line_count']"))
        self.assertFalse(form.xpath("//field[@name='selected_total']"))
        self.assertTrue(form.xpath("//field[@name='total_amount']"))
        self.assertEqual(option_fields[0].xpath("./list/@create"), ["0"])
        self.assertEqual(option_fields[0].xpath("./list/@delete"), ["0"])
        self.assertEqual(
            option_fields[0].xpath("./list/field[@name='selected']/@readonly"),
            ["parent.state not in ['draft', 'sent']"],
        )

        list_view = etree.fromstring(
            self.env.ref("workshop_job_card.view_job_card_list").arch_db
        )
        self.assertEqual(
            list_view.xpath("//list/field/@name"),
            [
                "name", "job_card_date", "customer_id", "vehicle_id", "plate_no",
                "technician_id", "total_amount", "state",
            ],
        )

    def test_exact_workflow_states(self):
        selection = dict(self.env["workshop.job.card"]._fields["state"].selection)
        self.assertEqual(
            set(selection),
            {
                "draft",
                "sent",
                "approved",
                "repair_created",
                "repair_completed",
                "rejected",
                "cancelled",
            },
        )
        self.assertFalse({"inspection", "prepared"}.intersection(selection))

    def test_repair_service_master_links_product_variants_directly(self):
        service = self.env["workshop.repair.service"].create(
            {
                "name": "Front Brake Repair Test",
                "code": "FBR-TEST",
                "product_ids": [(6, 0, self.products.ids[:2])],
                "description": "Front brake product options.",
            }
        )
        self.assertEqual(service.product_ids, self.products[:2])
        self.assertEqual(service.product_option_count, 2)
        self.assertTrue(service.active)
        self.assertEqual(service.sequence, 10)
        self.assertNotIn("categ_id", service._fields)
        self.assertNotIn("product_tmpl_ids", service._fields)

    def test_repair_service_views_action_and_menu(self):
        list_view = etree.fromstring(
            self.env.ref("workshop_job_card.view_repair_service_list").arch_db
        )
        self.assertEqual(
            list_view.xpath("//list/field/@name"),
            ["name", "code", "product_option_count"],
        )

        form = etree.fromstring(
            self.env.ref("workshop_job_card.view_repair_service_form").arch_db
        )
        self.assertEqual(form.xpath("//field[@name='active']/@invisible"), ["1"])
        self.assertTrue(form.xpath("//field[@name='product_ids']"))

        search = etree.fromstring(
            self.env.ref("workshop_job_card.view_repair_service_search").arch_db
        )
        self.assertTrue(search.xpath("//filter[@name='active']"))
        self.assertTrue(search.xpath("//filter[@name='archived']"))

        action = self.env.ref("workshop_job_card.action_repair_service")
        self.assertEqual(action.res_model, "workshop.repair.service")
        menu = self.env.ref("workshop_job_card.menu_repair_service")
        self.assertEqual(menu.parent_id, self.env.ref("repair.repair_menu_config"))

    def test_job_card_supports_multiple_service_lines(self):
        card = self._create_card()
        brake_service = self.env["workshop.repair.service"].create(
            {"name": "Brake Service Line Test", "product_ids": [(6, 0, self.products[:2].ids)]}
        )
        oil_service = self.env["workshop.repair.service"].create(
            {"name": "Oil Service Line Test", "product_ids": [(6, 0, self.products[2:].ids)]}
        )
        brake_line = self.env["workshop.job.card.service"].create(
            {"job_card_id": card.id, "repair_service_id": brake_service.id}
        )
        oil_line = self.env["workshop.job.card.service"].create(
            {"job_card_id": card.id, "repair_service_id": oil_service.id}
        )
        selected = brake_line.option_line_ids.filtered(
            lambda option: option.product_id == self.products[0]
        )
        selected.selected = True

        self.assertEqual(card.service_line_ids, brake_line | oil_line)
        self.assertEqual(brake_line.option_line_ids.product_id, self.products[:2])
        self.assertIn(selected, brake_line.option_line_ids)
        self.assertEqual(brake_line.selected_option_id, selected)
        self.assertEqual(brake_line.selected_amount, selected.amount)
        self.assertFalse(oil_line.selected_option_id)

        with self.assertRaises(IntegrityError):
            with self.env.cr.savepoint():
                self.env["workshop.job.card.service"].create(
                    {"job_card_id": card.id, "repair_service_id": brake_service.id}
                )

    def test_service_products_generate_options_on_create_and_write(self):
        card = self._create_card()
        first_service = self.env["workshop.repair.service"].create(
            {
                "name": "Generated Brake Options Test",
                "product_ids": [(6, 0, self.products[:2].ids)],
            }
        )
        second_service = self.env["workshop.repair.service"].create(
            {
                "name": "Generated Maintenance Options Test",
                "product_ids": [(6, 0, self.products[1:].ids)],
            }
        )
        service_line = self.env["workshop.job.card.service"].create(
            {"job_card_id": card.id, "repair_service_id": first_service.id}
        )
        self.assertEqual(service_line.option_line_ids.product_id, self.products[:2])
        self.assertTrue(all(service_line.option_line_ids.mapped("generated_by_service")))
        self.assertTrue(all(quantity == 1 for quantity in service_line.option_line_ids.mapped("quantity")))

        shared_option = service_line.option_line_ids.filtered(
            lambda option: option.product_id == self.products[1]
        )
        shared_option.write({"quantity": 3, "unit_price": 222000})
        service_line.repair_service_id = second_service

        self.assertEqual(
            service_line.option_line_ids.product_id,
            self.products[1:],
        )
        self.assertEqual(shared_option.quantity, 3)
        self.assertEqual(shared_option.unit_price, 222000)
        self.assertEqual(len(service_line.option_line_ids), 2)

        service_line.write({"repair_service_id": second_service.id})
        self.assertEqual(len(service_line.option_line_ids), 2)

    def test_service_product_generation_supports_onchange(self):
        card = self._create_card()
        service = self.env["workshop.repair.service"].create(
            {
                "name": "Onchange Generation Test",
                "product_ids": [(6, 0, self.products.ids)],
            }
        )
        service_line = self.env["workshop.job.card.service"].new(
            {"job_card_id": card.id, "repair_service_id": service.id}
        )
        service_line._onchange_repair_service_id()
        self.assertEqual(service_line.option_line_ids.product_id, self.products)
        self.assertTrue(all(service_line.option_line_ids.mapped("generated_by_service")))

    def test_add_repair_service_wizard_generates_options_and_skips_duplicates(self):
        card = self._create_card()
        first_service = self.env["workshop.repair.service"].create(
            {
                "name": "Wizard Brake Service Test",
                "product_ids": [(6, 0, self.products[:2].ids)],
            }
        )
        second_service = self.env["workshop.repair.service"].create(
            {
                "name": "Wizard Oil Service Test",
                "product_ids": [(6, 0, self.products[2:].ids)],
            }
        )

        action = card.action_open_add_repair_service_wizard()
        self.assertEqual(
            action["res_model"], "workshop.add.repair.service.wizard"
        )
        self.assertEqual(action["target"], "new")
        self.assertEqual(action["context"]["default_job_card_id"], card.id)

        wizard = self.env["workshop.add.repair.service.wizard"].create(
            {
                "job_card_id": card.id,
                "repair_service_ids": [(6, 0, (first_service | second_service).ids)],
            }
        )
        self.assertEqual(
            wizard.action_add(), {"type": "ir.actions.act_window_close"}
        )

        self.assertEqual(card.service_line_ids.repair_service_id, first_service | second_service)
        first_line = card.service_line_ids.filtered(
            lambda line: line.repair_service_id == first_service
        )
        second_line = card.service_line_ids.filtered(
            lambda line: line.repair_service_id == second_service
        )
        self.assertEqual(first_line.option_line_ids.product_id, self.products[:2])
        self.assertEqual(second_line.option_line_ids.product_id, self.products[2:])
        self.assertFalse(card.line_ids.filtered(lambda line: not line.product_id))

        duplicate_wizard = self.env["workshop.add.repair.service.wizard"].create(
            {
                "job_card_id": card.id,
                "repair_service_ids": [(6, 0, first_service.ids)],
            }
        )
        duplicate_wizard.action_add()
        self.assertEqual(len(card.service_line_ids), 2)
        self.assertEqual(len(card.line_ids), 3)

    def test_add_repair_service_wizard_validation_and_sent_state(self):
        card = self._create_card()
        empty_wizard = self.env["workshop.add.repair.service.wizard"].create(
            {"job_card_id": card.id}
        )
        with self.assertRaisesRegex(
            ValidationError, "Please select at least one Repair Service"
        ):
            empty_wizard.action_add()

        sent_service = self.env["workshop.repair.service"].create(
            {
                "name": "Sent Wizard Service Test",
                "product_ids": [(6, 0, self.products[:1].ids)],
            }
        )
        card._workflow_write({"state": "sent"})
        wizard = self.env["workshop.add.repair.service.wizard"].create(
            {
                "job_card_id": card.id,
                "repair_service_ids": [(6, 0, sent_service.ids)],
            }
        )
        wizard.action_add()
        self.assertEqual(card.service_line_ids.repair_service_id, sent_service)
        self.assertEqual(card.line_ids.product_id, self.products[:1])

        card._workflow_write({"state": "approved"})
        with self.assertRaisesRegex(UserError, "current state"):
            card.action_open_add_repair_service_wizard()

    def test_remove_repair_service_wizard_keeps_unselected_services(self):
        card = self._create_card()
        services = self.env["workshop.repair.service"]
        for index, product in enumerate(self.products):
            services |= self.env["workshop.repair.service"].create(
                {
                    "name": f"Remove Wizard Service {index}",
                    "product_ids": [(6, 0, product.ids)],
                }
            )
        self.env["workshop.add.repair.service.wizard"].create(
            {
                "job_card_id": card.id,
                "repair_service_ids": [(6, 0, services.ids)],
            }
        ).action_add()
        service_lines = card.service_line_ids
        removed_line = service_lines.filtered(
            lambda line: line.repair_service_id == services[0]
        )
        kept_lines = service_lines - removed_line
        removed_options = removed_line.option_line_ids
        kept_options = kept_lines.option_line_ids

        action = card.action_open_remove_repair_service_wizard()
        self.assertEqual(
            action["res_model"], "workshop.remove.repair.service.wizard"
        )
        self.assertEqual(action["target"], "new")
        self.assertEqual(action["context"]["default_job_card_id"], card.id)

        result = self.env["workshop.remove.repair.service.wizard"].create(
            {
                "job_card_id": card.id,
                "job_card_service_ids": [(6, 0, removed_line.ids)],
            }
        ).action_remove_services()
        self.assertEqual(result, {"type": "ir.actions.client", "tag": "reload"})
        self.assertFalse(removed_line.exists())
        self.assertFalse(removed_options.exists())
        self.assertEqual(card.service_line_ids, kept_lines)
        self.assertEqual(card.line_ids, kept_options)
        self.assertTrue(services[0].exists())
        self.assertTrue(self.products[0].exists())

    def test_remove_multiple_services_and_last_service_resets_total(self):
        card = self._create_card()
        services = self.env["workshop.repair.service"]
        for index, product in enumerate(self.products):
            services |= self.env["workshop.repair.service"].create(
                {
                    "name": f"Multiple Removal Service {index}",
                    "product_ids": [(6, 0, product.ids)],
                }
            )
        self.env["workshop.add.repair.service.wizard"].create(
            {
                "job_card_id": card.id,
                "repair_service_ids": [(6, 0, services.ids)],
            }
        ).action_add()
        card.line_ids[0].write({"selected": True})
        card.line_ids[1].write({"selected": True})
        self.assertGreater(card.total_amount, 0)
        card._workflow_write({"state": "sent"})

        first_two = card.service_line_ids.filtered(
            lambda line: line.repair_service_id in services[:2]
        )
        self.env["workshop.remove.repair.service.wizard"].create(
            {
                "job_card_id": card.id,
                "job_card_service_ids": [(6, 0, first_two.ids)],
            }
        ).action_remove_services()
        self.assertEqual(card.service_line_ids.repair_service_id, services[2])
        self.assertEqual(card.total_amount, 0)

        self.env["workshop.remove.repair.service.wizard"].create(
            {
                "job_card_id": card.id,
                "job_card_service_ids": [(6, 0, card.service_line_ids.ids)],
            }
        ).action_remove_services()
        self.assertFalse(card.service_line_ids)
        self.assertFalse(card.line_ids)
        self.assertEqual(card.total_amount, 0)

    def test_remove_repair_service_wizard_validates_selection_state_and_card(self):
        card = self._create_card()
        empty_wizard = self.env["workshop.remove.repair.service.wizard"].create(
            {"job_card_id": card.id}
        )
        with self.assertRaisesRegex(
            ValidationError,
            "Please select at least one Repair Service to remove",
        ):
            empty_wizard.action_remove_services()

        service = self.env["workshop.repair.service"].create(
            {
                "name": "Protected Removal Service",
                "product_ids": [(6, 0, self.products[:1].ids)],
            }
        )
        service_line = self.env["workshop.job.card.service"].create(
            {"job_card_id": card.id, "repair_service_id": service.id}
        )
        card._workflow_write({"state": "approved"})
        with self.assertRaisesRegex(UserError, "Draft or Sent to Customer state"):
            card.action_open_remove_repair_service_wizard()
        protected_wizard = self.env["workshop.remove.repair.service.wizard"].create(
            {
                "job_card_id": card.id,
                "job_card_service_ids": [(6, 0, service_line.ids)],
            }
        )
        with self.assertRaisesRegex(UserError, "Draft or Sent to Customer state"):
            protected_wizard.action_remove_services()
        self.assertTrue(service_line.exists())

        other_card = self._create_card()
        other_service = self.env["workshop.repair.service"].create(
            {"name": "Other Card Removal Service"}
        )
        other_line = self.env["workshop.job.card.service"].create(
            {"job_card_id": other_card.id, "repair_service_id": other_service.id}
        )
        wrong_card_wizard = self.env[
            "workshop.remove.repair.service.wizard"
        ].create(
            {
                "job_card_id": other_card.id,
                "job_card_service_ids": [(6, 0, service_line.ids)],
            }
        )
        with self.assertRaisesRegex(ValidationError, "current Job Card"):
            wrong_card_wizard.action_remove_services()
        self.assertTrue(service_line.exists())
        self.assertTrue(other_line.exists())

    def test_complete_two_service_job_card_demo_flow(self):
        product_values = (
            ("Brake Pad Korea", "FLOW-BP-KR", 200000),
            ("Brake Pad OEM", "FLOW-BP-OEM", 250000),
            ("Brake Pad Thailand", "FLOW-BP-TH", 180000),
            ("Engine Oil 5W30 OEM", "FLOW-OIL-OEM", 360000),
            ("Engine Oil 5W30 Shell", "FLOW-OIL-SHELL", 380000),
            ("Engine Oil 5W30 Castrol", "FLOW-OIL-CASTROL", 400000),
        )
        products = self.env["product.product"]
        for name, code, price in product_values:
            products |= self.env["product.product"].create(
                {
                    "name": name,
                    "default_code": code,
                    "type": "consu",
                    "brand_id": self.part_brand.id,
                    "list_price": price,
                }
            )

        brake_service = self.env["workshop.repair.service"].create(
            {
                "name": "Front Brake Repair",
                "code": "BRAKE-FRONT",
                "sequence": 10,
                "product_ids": [(6, 0, products[:3].ids)],
            }
        )
        oil_service = self.env["workshop.repair.service"].create(
            {
                "name": "Engine Oil Change",
                "code": "OIL-CHANGE",
                "sequence": 20,
                "product_ids": [(6, 0, products[3:].ids)],
            }
        )
        self.assertEqual(brake_service.sequence, 10)
        self.assertEqual(oil_service.sequence, 20)
        self.assertEqual(brake_service.product_ids, products[:3])
        self.assertEqual(oil_service.product_ids, products[3:])

        card = self._create_card()
        brake_line = self.env["workshop.job.card.service"].create(
            {"job_card_id": card.id, "repair_service_id": brake_service.id}
        )
        oil_line = self.env["workshop.job.card.service"].create(
            {"job_card_id": card.id, "repair_service_id": oil_service.id}
        )
        self.assertEqual(brake_line.option_line_ids.product_id, products[:3])
        self.assertEqual(oil_line.option_line_ids.product_id, products[3:])
        self.assertEqual(len(brake_line.option_line_ids), 3)
        self.assertEqual(len(oil_line.option_line_ids), 3)

        brake_line._generate_option_lines()
        oil_line._generate_option_lines()
        self.assertEqual(len(brake_line.option_line_ids), 3)
        self.assertEqual(len(oil_line.option_line_ids), 3)

        brake_korea = brake_line.option_line_ids.filtered(
            lambda option: option.product_id == products[0]
        )
        brake_oem = brake_line.option_line_ids.filtered(
            lambda option: option.product_id == products[1]
        )
        oil_shell = oil_line.option_line_ids.filtered(
            lambda option: option.product_id == products[4]
        )
        brake_korea.selected = True
        brake_oem.selected = True
        self.assertFalse(brake_korea.selected)
        self.assertTrue(brake_oem.selected)

        oil_shell.selected = True
        self.assertTrue(brake_oem.selected)
        self.assertTrue(oil_shell.selected)
        self.assertEqual(card.total_amount, 630000)

        with self.assertRaises(IntegrityError):
            with self.env.cr.savepoint():
                self.env["workshop.job.card.service"].create(
                    {"job_card_id": card.id, "repair_service_id": brake_service.id}
                )

        self._complete_pre_customer_inspections(card)
        card.action_send_to_customer()
        card.action_approve()
        card.action_create_repair_order()

        repair = card.repair_order_id
        self.assertEqual(repair.move_ids.product_id, products[1] | products[4])
        self.assertEqual(len(repair.move_ids), 2)
        self.assertEqual(card.state, "repair_created")

        form = etree.fromstring(
            self.env.ref("workshop_job_card.view_job_card_form").arch_db
        )
        self.assertFalse(form.xpath("//field[@name='selected_line_count']"))
        self.assertFalse(form.xpath("//field[@name='selected_total']"))
        self.assertTrue(form.xpath("//field[@name='total_amount']"))
        self.assertEqual(
            self.env["workshop.job.card"]._fields["total_amount"].string,
            "Total",
        )

