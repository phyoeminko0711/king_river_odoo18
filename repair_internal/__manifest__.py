{
    "name": "Repair Internal Invoice",
    "version": "18.0.1.0.0",
    "summary": "Create customer invoices directly from completed repair orders",
    "category": "Services/Repair",
    "author": "dev_pmk",
    "license": "LGPL-3",
    "depends": [
        "repair",
        "account",
        "workshop_job_card",
    ],
    "data": [
        "security/ir.model.access.csv",
        "views/repair_order_views.xml",
        "views/account_move_views.xml",
    ],
    "installable": True,
    "application": False,
}
