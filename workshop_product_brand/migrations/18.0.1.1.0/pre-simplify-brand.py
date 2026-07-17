"""Relax database constraints from the former advanced Brand model."""


def migrate(cr, version):
    cr.execute(
        """
        ALTER TABLE workshop_product_brand
            ALTER COLUMN code DROP NOT NULL,
            ALTER COLUMN brand_type_id DROP NOT NULL,
            ALTER COLUMN state DROP NOT NULL
        """
    )
    cr.execute(
        "ALTER TABLE workshop_product_brand_type ALTER COLUMN code DROP NOT NULL"
    )
    for constraint_name in (
        "brand_code_not_empty",
        "brand_code_unique",
        "workshop_product_brand_brand_code_not_empty",
        "workshop_product_brand_brand_code_unique",
        "brand_type_code_not_empty",
        "brand_type_code_unique",
        "workshop_product_brand_type_brand_type_code_not_empty",
        "workshop_product_brand_type_brand_type_code_unique",
    ):
        cr.execute(
            f"ALTER TABLE workshop_product_brand DROP CONSTRAINT IF EXISTS {constraint_name}"
            if "brand_type" not in constraint_name
            else f"ALTER TABLE workshop_product_brand_type DROP CONSTRAINT IF EXISTS {constraint_name}"
        )

