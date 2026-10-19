{
    "name": "Product Internal",
    "version": "18.0.1.2.0",
    "summary": "Additional internal product naming fields",
    "category": "Inventory/Product",
    "author": "dev_pmk",
    "license": "LGPL-3",
    "depends": ["product", "stock", "workshop_product_brand"],
    "data": [
        "security/ir.model.access.csv",
        "views/product_rate_scheme_views.xml",
        "views/product_template_views.xml",
    ],
    "installable": True,
    "application": False,
}
