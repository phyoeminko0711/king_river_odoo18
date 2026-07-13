import json, werkzeug
from odoo import http
import datetime
from odoo.http import request

def default(o):
    if isinstance(o, (datetime.date, datetime.datetime)):
        return o.isoformat()
        
class LocationAPIController(http.Controller):
    
    # Get Countries
    @http.route("/api/countries", methods=["GET"], type="http", auth="none", csrf=False)
    def get_country(self,codes=None):
        domain = []
        fields = ['id', 'name', 'code']
        if codes:
            domain.append(('code','in', list(map(lambda x:x.upper(),codes.split(",")))))
        countries = request.env['res.country'].sudo().search_read(domain,fields=fields)
        return werkzeug.wrappers.Response(status=200, content_type="application/json; charset=utf-8", response=json.dumps(countries, default=default))

    # Get States
    @http.route("/api/states", methods=["GET"], type="http", auth="none", csrf=False)
    def get_states(self,countries=None):
        final_list = []
        domain = []
        fields = ['id', 'name']
        townships = request.env['res.township'].sudo()
        if countries:
            try:
                domain.append(('country_id','in', list(map(lambda x:int(x),countries.split(",")))))
            except Exception as e:
                return werkzeug.wrappers.Response(status=200, content_type="application/json; charset=utf-8", response=json.dumps({"ERROR":e.args[0]}, default=default))
        states = request.env['res.country.state'].sudo().search(domain, order="name")
        for i in states:
            final_list.append({
                'id': i.id,
                'name': i.name,
                'country_id': {'id': i.country_id.id, 'name': i.country_id.name},
                'township_ids': townships.search_read([('state_id','=',i.id)], fields=fields, order="name")
            })
        return werkzeug.wrappers.Response(status=200, content_type="application/json; charset=utf-8", response=json.dumps(final_list, default=default))

    # Get Townships
    @http.route("/api/townships", methods=["GET"], type="http", auth="none", csrf=False)
    def get_townships(self,countries=None,states=None):
        domain = []
        fields = ['id', 'name']
        if countries:
            domain.append(('country_id','in', list(map(lambda x:int(x),countries.split(",")))))
        if states:
            domain.append(('state_id','in', list(map(lambda x:int(x),states.split(",")))))
        townships = request.env['res.township'].sudo().search_read(domain,fields=fields,order="name")
        return werkzeug.wrappers.Response(status=200, content_type="application/json; charset=utf-8", response=json.dumps(townships, default=default))
        