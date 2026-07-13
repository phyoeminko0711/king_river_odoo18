# -*- coding: utf-8 -*-
###############################################################################

###############################################################################
{
    'name': 'Hide Cost Price',
    'version': '18.0.1.0.0',
    'category': 'Purchase',
    'summary': """Hide cost price of product for specified users""",
    'description': """Product cost price will be visible only for specified 
                group""",
    'author': 'Innovix Solutions',
    'company': 'Innovix Solutions',
    'maintainer': 'Innovix Solutions',
    'website': 'https://www.innovix-solutions.com',
    'depends': ['purchase'],
    'license': 'AGPL-3',
    'data': [
        'security/hide_cost_price_groups.xml',
        'views/purchase_views.xml'
    ],
    'images': ['static/description/banner.jpg'],
    'installable': True,
    'auto_install': False,
    "application": False,
}
