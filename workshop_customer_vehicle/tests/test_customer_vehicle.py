from lxml import etree
from psycopg2 import IntegrityError

from odoo.exceptions import ValidationError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install")
class TestCustomerVehicle(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.customer = cls.env["res.partner"].create(
            {"name": "ABC Trading", "customer_rank": 1}
        )
        cls.other_customer = cls.env["res.partner"].create(
            {"name": "Other Customer", "customer_rank": 1}
        )
        cls.hyundai = cls.env["workshop.vehicle.brand"].create(
            {"name": "CV Test Hyundai 18"}
        )
        cls.toyota = cls.env["workshop.vehicle.brand"].create(
            {"name": "CV Test Toyota 18"}
        )
        cls.starex = cls.env["workshop.vehicle.model"].create(
            {"name": "Grand Starex", "brand_id": cls.hyundai.id}
        )
        cls.hiace = cls.env["workshop.vehicle.model"].create(
            {"name": "Hiace", "brand_id": cls.toyota.id}
        )

    def _vehicle_values(self, **overrides):
        values = {
            "customer_id": self.customer.id,
            "vehicle_brand_id": self.hyundai.id,
            "vehicle_model_id": self.starex.id,
            "plate_no": "YGN-9K-1234",
            "chassis_no": "CHASSIS-001",
            "engine_no": "ENGINE-001",
            "mileage": 120000,
        }
        values.update(overrides)
        return values

    def test_create_normalization_and_display_name(self):
        vehicle = self.env["workshop.customer.vehicle"].create(
            self._vehicle_values(
                plate_no=" ygn-9k-1234 ",
                chassis_no=" chassis-001 ",
            )
        )
        self.assertRegex(vehicle.name, r"^VEH/\d{5}$")
        self.assertEqual(vehicle.plate_no, "YGN-9K-1234")
        self.assertEqual(vehicle.chassis_no, "CHASSIS-001")
        self.assertEqual(
            vehicle.display_name,
            "[YGN-9K-1234] CV Test Hyundai 18 Grand Starex",
        )

    def test_duplicate_customer_plate_is_rejected(self):
        self.env["workshop.customer.vehicle"].create(self._vehicle_values())
        with self.assertRaises(IntegrityError):
            with self.env.cr.savepoint():
                self.env["workshop.customer.vehicle"].create(
                    self._vehicle_values(chassis_no="CHASSIS-002")
                )

    def test_customer_can_have_multiple_vehicles(self):
        first = self.env["workshop.customer.vehicle"].create(self._vehicle_values())
        second = self.env["workshop.customer.vehicle"].create(
            self._vehicle_values(
                plate_no="YGN-1A-2222",
                chassis_no="CHASSIS-002",
            )
        )
        self.assertEqual(self.customer.vehicle_count, 2)
        self.assertEqual(self.customer.vehicle_ids, first | second)

    def test_same_plate_for_different_customer_is_allowed(self):
        self.env["workshop.customer.vehicle"].create(self._vehicle_values())
        second = self.env["workshop.customer.vehicle"].create(
            self._vehicle_values(
                customer_id=self.other_customer.id,
                chassis_no="CHASSIS-002",
            )
        )
        self.assertTrue(second)

    def test_model_must_match_brand(self):
        with self.assertRaisesRegex(ValidationError, "does not belong"):
            self.env["workshop.customer.vehicle"].create(
                self._vehicle_values(vehicle_model_id=self.hiace.id)
            )

    def test_mileage_cannot_be_negative(self):
        with self.assertRaises(IntegrityError):
            with self.env.cr.savepoint():
                self.env["workshop.customer.vehicle"].create(
                    self._vehicle_values(mileage=-1)
                )

    def test_vehicle_is_not_a_product(self):
        fields = self.env["workshop.customer.vehicle"]._fields
        self.assertNotIn("product_id", fields)
        self.assertNotIn("product_tmpl_id", fields)

    def test_partner_smart_button_action(self):
        vehicle = self.env["workshop.customer.vehicle"].create(self._vehicle_values())
        action = self.customer.action_view_vehicles()
        self.assertEqual(action["domain"], [("customer_id", "=", self.customer.id)])
        self.assertEqual(action["context"]["default_customer_id"], self.customer.id)
        self.assertEqual(vehicle.customer_id, self.customer)

    def test_advanced_fields_are_hidden_from_vehicle_form(self):
        form_arch = str(
            self.env.ref("workshop_customer_vehicle.view_customer_vehicle_form").arch_db
        )
        for field_name in (
            "model_year",
            "mileage_uom",
            "transmission",
            "fuel_type",
            "image_1920",
            "note",
        ):
            self.assertNotIn(f'name="{field_name}"', form_arch)

        partner_arch = str(
            self.env.ref(
                "workshop_customer_vehicle.view_partner_form_customer_vehicles"
            ).arch_db
        )
        self.assertNotIn('name="customer_vehicles"', partner_arch)

    def test_vehicle_view_domain_and_menu_order(self):
        form = etree.fromstring(
            self.env.ref(
                "workshop_customer_vehicle.view_customer_vehicle_form"
            ).arch_db
        )
        self.assertFalse(form.xpath("//field[@name='company_id']"))
        self.assertFalse(form.xpath("//field[@name='product_id']"))
        model_field = form.xpath("//field[@name='vehicle_model_id']")[0]
        self.assertEqual(
            model_field.get("domain"), "[('brand_id', '=', vehicle_brand_id)]"
        )

        model_list = etree.fromstring(
            self.env.ref(
                "workshop_customer_vehicle.view_vehicle_model_list"
            ).arch_db
        )
        self.assertEqual(
            model_list.xpath("//list/field/@name"), ["name", "brand_id", "active"]
        )
        self.assertFalse(model_list.xpath("//list/@editable"))
        self.assertEqual(
            model_list.xpath("//field[@name='active']/@column_invisible"),
            ["True"],
        )

        for view_xmlid in (
            "workshop_customer_vehicle.view_customer_vehicle_form",
            "workshop_customer_vehicle.view_vehicle_brand_form",
            "workshop_customer_vehicle.view_vehicle_model_form",
        ):
            form_view = etree.fromstring(self.env.ref(view_xmlid).arch_db)
            self.assertEqual(
                form_view.xpath("//field[@name='active']/@invisible"), ["1"]
            )

        vehicle_menu = self.env.ref(
            "workshop_customer_vehicle.menu_customer_vehicle"
        )
        brand_menu = self.env.ref("workshop_customer_vehicle.menu_vehicle_brand")
        model_menu = self.env.ref("workshop_customer_vehicle.menu_vehicle_model")
        self.assertEqual(vehicle_menu.parent_id, self.env.ref("repair.menu_repair_order"))
        self.assertLess(vehicle_menu.sequence, self.env.ref("repair.repair_order_menu").sequence)
        self.assertEqual(brand_menu.parent_id, self.env.ref("repair.repair_menu_config"))
        self.assertEqual(model_menu.parent_id, brand_menu.parent_id)
        self.assertLess(brand_menu.sequence, model_menu.sequence)
