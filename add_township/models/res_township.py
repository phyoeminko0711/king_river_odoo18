

from odoo import models, fields

class Township(models.Model):
    _description = "Township"
    _name = 'res.township'
    _order = 'code'

    state_id = fields.Many2one('res.country.state', string='State', required=True)    
    name = fields.Char(string='Township Name', required=True)
    name_mm = fields.Char(string='Township Name (MM)')
    code = fields.Char(string='Township Code', help='The township code.', required=True)
    district = fields.Many2one('res.country.district', string="District")
    country_id = fields.Many2one('res.country', string='Country', related='state_id.country_id', store=True)

    _sql_constraints = [
        ('name_code_uniq', 'unique(state_id, code)', 'The code of the township must be unique by state !')
    ]    

    
