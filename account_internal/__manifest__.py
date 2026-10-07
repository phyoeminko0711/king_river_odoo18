{
    "name": "Account Internal",
    "version": "18.0.1.0.0",
    "summary": "King River sale invoice direct print report",
    "category": "Accounting/Accounting",
    "author": "dev_pmk",
    "license": "LGPL-3",
    "depends": ["account", "report_qweb_direct_print"],
    "data": [
        "views/res_company_views.xml",
        "report/sale_invoice_report.xml",
    ],
    "installable": True,
    "application": False,
}
