{
    "name": "Workshop Product Brand",
    "version": "18.0.1.3.0",
    "summary": "Reusable product brand master for workshop spare parts",
    "category": "Repair/Configuration",
    "author": "dev_pmk",
    "license": "LGPL-3",
    "depends": ["base", "product", "repair"],
    "data": [
        "security/ir.model.access.csv",
        "views/product_brand_views.xml",
        "views/product_template_views.xml",
        "views/product_brand_menu.xml",
    ],
    "installable": True,
    "application": False,
}
