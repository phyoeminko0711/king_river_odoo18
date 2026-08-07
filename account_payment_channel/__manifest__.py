{
    "name": "Account Payment Channel",
    "version": "18.0.1.0.0",
    "summary": "Classify cash and bank journals by configurable payment channels",
    "category": "Accounting/Accounting",
    "author": "dev_pmk",
    "license": "LGPL-3",
    "depends": [
        "account",
    ],
    "data": [
        "security/ir.model.access.csv",
        "views/payment_channel_views.xml",
        "views/account_journal_views.xml",
        "views/payment_channel_menu.xml",
    ],
    "demo": [
        "demo/payment_channel_demo.xml",
    ],
    "installable": True,
    "application": False,
}
