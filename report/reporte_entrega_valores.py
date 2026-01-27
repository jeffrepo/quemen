# -*- encoding: utf-8 -*-

from odoo import api, models, fields
from datetime import date
import datetime
import time
import dateutil.parser
from dateutil.relativedelta import relativedelta
from dateutil import relativedelta as rdelta
from odoo.fields import Date, Datetime
import logging
from operator import itemgetter
import pytz
# import odoo.addons.hr_gt.a_letras

class ReportEntregaValores(models.AbstractModel):
    _name = 'report.quemen.reporte_entrega_valores'
    _description = " "


    def _get_entrega_valores(self, fecha_inicio,fecha_fin, tienda_id):
        logging.warning(tienda_id)
        retiro_ids = False
        if fecha_inicio and fecha_fin:
            retiro_ids = self.env['quemen.retiros_efectivo'].search([('tienda_id','=',tienda_id[0]),('fecha_hora','>=',fecha_inicio),('fecha_hora','<=',fecha_fin)],order='fecha_hora asc')
        else:
            retiro_ids = self.env['quemen.retiros_efectivo'].search([('tienda_id','=',tienda_id[0]),('entregado','=', False),('state','=', 'confirmado')], order='fecha_hora asc')
        fondo_caja = {}
        retiro_efectivo = {}
        logging.warn(retiro_ids)
        if len(retiro_ids) > 0:
            for retiro in retiro_ids:
                fecha_sesion = dateutil.parser.parse(str(retiro.sesion_id.start_at)).date()
                logging.warn("Sesion")
                logging.warn(retiro.sesion_id.name)
                retiro.write({'entregado': True})
                if fecha_sesion not in retiro_efectivo:
                    retiro_efectivo[fecha_sesion] = {'fecha': fecha_sesion, 'retiros': [],'total_retiros': 0}

                retiro_efectivo[fecha_sesion]['retiros'].append(retiro)
                retiro_efectivo[fecha_sesion]['total_retiros'] += retiro.total
        logging.warning(retiro_ids)
        return {'retiro_efectivo': retiro_efectivo.values()}



    @api.model
    def _get_report_values(self, docids, data=None):
        model = self.env.context.get('active_model')
        docs = self.env[model].browse(self.env.context.get('active_ids', []))
        fecha_inicio = data['form']['fecha_inicio']
        fecha_fin = data['form']['fecha_fin']
        tienda_id = data['form']['tienda_id']
        fecha_generacion = data['form']['fecha_generacion']

        return {
            'doc_ids': self.ids,
            'doc_model': model,
            'data': data['form'],
            'docs': docs,
            'fecha_inicio': fecha_inicio,
            'fecha_fin': fecha_fin,
            'tienda_id': tienda_id,
            'fecha_generacion': fecha_generacion,
            '_get_entrega_valores': self._get_entrega_valores,
        }
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
