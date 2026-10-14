{
    "name": "Purchase Rate Adjustment",
    "version": "18.0.1.0.0",
    "summary": "Adjust product sales prices by product rate scheme and weight",
    "category": "Purchases/Configuration",
    "author": "dev_pmk",
    "license": "LGPL-3",
    "depends": ["purchase", "product_internal", "web"],
    "data": [
        "security/ir.model.access.csv",
        "views/rate_adjustment_views.xml",
        "wizard/rate_adjustment_wizard_views.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "purchase_rate_adjustment/static/src/js/rate_adjustment_list.js",
            "purchase_rate_adjustment/static/src/xml/rate_adjustment_list.xml",
        ],
    },
    "installable": True,
    "application": False,
}
