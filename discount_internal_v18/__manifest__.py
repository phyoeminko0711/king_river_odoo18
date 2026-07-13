# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Discount Internal',
    'version': '1.0',
    'description': """
This module contains the modification about Sale,PO and Account.
    """,
    'depends':  ['sale', 'account', 'purchase', 'wm_purchase_global_discount'],
    'data': [
        'views/sale.xml',
        'views/account_move.xml',
        'views/purchase.xml',
        'wizards/sale_order_discount.xml',
        'wizards/purchase_order_discount.xml',
    ],
    'installable': True,
    'auto_install': False
}
