from odoo import models,fields,api


class District(models.Model):
    _name = 'res.country.district'
    _description = 'District'


    name = fields.Char('Name')
    code = fields.Char('District Code')
    state_id = fields.Many2one('res.country.state',
                               string="State"
                               )


