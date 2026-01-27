# -*- encoding: utf-8 -*-

from odoo import api, models, fields
import logging

class ReportValeRetiro(models.AbstractModel):
    _name = 'report.quemen.vale_retiro'
    _description = " "

    @api.model
    def _get_report_values(self, docids, data=None):
        return self.get_report_values(docids, data)

    @api.model
    def get_report_values(self, docids, data=None):
        docs = self.env['quemen.retiros_efectivo'].browse(docids)

        return {
            'doc_ids': docids,
            'docs': docs,
        }
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
