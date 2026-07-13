from odoo import models, fields
from datetime import datetime

class ReportHelperMixin(models.AbstractModel):
    _name = 'report.helper.mixin'
    _description = 'Helper Mixin for report names'

    def _get_print_time_str(self):
        """Return current datetime in user's timezone for report filenames"""
        user_tz = self.env.user.tz or 'UTC'
        utc_dt = datetime.utcnow()
        local_dt = fields.Datetime.context_timestamp(self, utc_dt)
        return local_dt.strftime("%d_%m_%Y_%H_%M_%S")
