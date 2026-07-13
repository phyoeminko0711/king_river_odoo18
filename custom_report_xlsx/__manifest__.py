# -*- coding:utf-8 -*-

{
    'name': 'Custom Detail Report',

    'category': 'Reporting',

    'sequence': 39,

    'summary': 'Custom report',

    'description': "",

    'depends': ['base', 'stock', 'web', 'sale', 'purchase', 'report_controller','stock',],

    'data': [
        'security/ir.model.access.csv',
        'wizards/sale_detail_report.xml',
        'wizards/purchase_detail_report.xml',
        'wizards/sale_analysis_detail_report_wizard.xml',
    ],

    'installable': True,

    'application': False,

}
