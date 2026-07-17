from lxml import etree

from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install")
class TestWorkshopProductBrand(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.brand = cls.env["workshop.product.brand"].create(
            {"name": "  Korea  ", "code": " KR "}
        )

    def test_brand_master_is_simple(self):
        self.assertEqual(self.brand.name, "Korea")
        self.assertEqual(self.brand.code, "KR")
        self.assertTrue(self.brand.active)
        fields = self.brand._fields
        for field_name in ("country_id", "sequence"):
            self.assertNotIn(field_name, fields)

    def test_brand_is_shared_by_all_template_variants(self):
        template = self.env["product.template"].create(
            {"name": "Workshop Part", "brand_id": self.brand.id}
        )
        variant = template.product_variant_id
        self.assertEqual(variant.brand_id, self.brand)

        replacement = self.env["workshop.product.brand"].create(
            {"name": "Replacement"}
        )
        variant.brand_id = replacement
        self.assertEqual(template.brand_id, replacement)
        self.assertEqual(variant.brand_id, replacement)

    def test_brand_is_optional(self):
        template = self.env["product.template"].create({"name": "Unbranded Part"})
        self.assertFalse(template.brand_id)
        self.assertFalse(template.product_variant_id.brand_id)

    def test_brand_views_and_menu(self):
        list_view = etree.fromstring(
            self.env.ref(
                "workshop_product_brand.view_workshop_product_brand_list"
            ).arch_db
        )
        self.assertEqual(list_view.xpath("//list/field/@name"), ["name", "code", "active"])

        form = etree.fromstring(
            self.env.ref(
                "workshop_product_brand.view_workshop_product_brand_form"
            ).arch_db
        )
        self.assertEqual(form.xpath("//form//field/@name"), ["name", "code", "active"])

        template_form = etree.fromstring(
            self.env.ref(
                "workshop_product_brand.product_template_form_view_inherit_workshop_brand"
            ).arch_db
        )
        self.assertTrue(template_form.xpath("//field[@name='brand_id']"))

        template_list = etree.fromstring(
            self.env.ref(
                "workshop_product_brand.product_template_tree_view_inherit_workshop_brand"
            ).arch_db
        )
        self.assertTrue(template_list.xpath("//field[@name='brand_id']"))

        search = etree.fromstring(
            self.env.ref(
                "workshop_product_brand.product_search_form_view_inherit_workshop_brand"
            ).arch_db
        )
        self.assertTrue(search.xpath("//field[@name='brand_id']"))
        self.assertTrue(search.xpath("//filter[@name='group_by_brand']"))

        menu = self.env.ref("workshop_product_brand.menu_workshop_product_brand")
        self.assertEqual(menu.parent_id, self.env.ref("repair.repair_menu_config"))
