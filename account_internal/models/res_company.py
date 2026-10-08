from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    invoice_header_line_1 = fields.Text(
        string="Invoice Header Line 1",
        help="First address and contact line printed below the invoice company name.",
    )
    invoice_header_line_2 = fields.Text(
        string="Invoice Header Line 2",
        help="Second address and contact line printed below the invoice company name.",
    )
    invoice_shop_1_address = fields.Text(
        string="Shop 1 Address",
        default="အမှတ် (၆၁၉၊ ၆၃၁၊ ၆၃၂)၊ အမှတ် (၃) လမ်းမကြီး၊ ဖူးပွင့်စုံအနီး၊ စုပေါင်း (၃) ရပ်ကွက်၊ မင်္ဂလာဒုံမြို့နယ်၊ ရန်ကုန်မြို့။",
    )
    invoice_shop_1_spare_phone = fields.Char(
        string="Shop 1 Spare Part Phone",
        default="09-441931001, 09-441931002",
    )
    invoice_shop_1_service_phone = fields.Char(
        string="Shop 1 Service Phone",
        default="09-402882005, 09-402882008",
    )
    invoice_shop_2_address = fields.Text(
        string="Shop 2 Address",
        default="အမှတ် (၁)၊ မဟာဗန္ဓုလလမ်း၊ အထကစက်ဆန်းအနီး၊ (၄၅) ရပ်ကွက်၊ မြောက်ဒဂုံမြို့နယ်၊ ရန်ကုန်မြို့။",
    )
    invoice_shop_2_phone = fields.Char(
        string="Shop 2 Phone",
        default="09-732060555, 09-420600554",
    )
    invoice_shop_2_spare_phone = fields.Char(string="Shop 2 Spare Part Phone")
    invoice_shop_2_service_phone = fields.Char(string="Shop 2 Service Phone")
    invoice_service_notes = fields.Text(
        string="Invoice Thank-you / Service Notes",
        default=(
            "ဝယ်ယူပြီးပစ္စည်းများကို ( ) ရက်အတွင်း လဲလှယ်ဝယ်ယူနိုင်ပါသည်။\n"
            "ဝယ်ယူပြီးပစ္စည်းများကို ငွေပြန်မအမ်းပါ။\n"
            "ဝယ်ယူပြီးပစ္စည်းများကို အထူးကျေးဇူးတင်ရှိပါသည်။"
        ),
        help="Myanmar service reminder text printed above the service kilo boxes.",
    )
