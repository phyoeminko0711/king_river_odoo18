# -*- coding:utf-8 -*-

{
    'name': 'Custom Detail Report',

    'category': 'Reporting',

    'sequence': 39,

    'summary': 'Custom report',

    'description': "",

    'depends': [
        'base',
        'stock',
        'web',
        'sale',
        'sale_management',
        'purchase',
        'account',
        'account_payment_channel',
        'report_controller',
    ],

    'data': [
        'security/ir.model.access.csv',
        # 'wizards/sale_detail_report.xml',
        # 'wizards/purchase_detail_report.xml',
        # 'wizards/sale_analysis_detail_report_wizard.xml',
        'wizards/daily_sales_summary_report.xml',
    ],

    'installable': True,

    'application': False,

}
