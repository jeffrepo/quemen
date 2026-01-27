# -*- coding: utf-8 -*-

from odoo import api, models, _
from odoo.exceptions import UserError, ValidationError
import datetime
import logging

class CaodigoBarrasLoteTraslado(models.AbstractModel):
    _name = 'report.quemen.reporte_codigo_barras_lotet'
    _description = " "

    nombre_reporte = ''

    def fecha_hoy(self,o):
        fecha = o.date
        dia = datetime.strptime(str(fecha), '%Y-%m-%d').strftime('%d')
        mes = datetime.strptime(str(fecha), '%Y-%m-%d').strftime('%m')
        mes_letras = odoo.addons.l10n_gt_extra.a_letras.mes_a_letras(int(mes)-1)
        anio = datetime.strptime(str(fecha), '%Y-%m-%d').strftime('%Y')
        fecha = str(dia)+' de '+mes_letras+' de '+str(anio)
        return fecha

    def mes_abreviado(self,mes):
        resultado = False
        if mes == 1:
            resultado = 'ENE'
        elif mes == 2:
            resultado = 'FEB'
        elif mes == 3:
            resultado = 'MAR'
        elif mes == 4:
            resultado = 'ABR'
        elif mes == 5:
            resultado = 'MAY'
        elif mes == 6:
            resultado = 'JUN'
        elif mes == 7:
            resultado = 'JUL'
        elif mes == 8:
            resultado = 'AGO'
        elif mes == 9:
            resultado = 'SEP'
        elif mes == 10:
            resultado = 'OCT'
        elif mes == 11:
            resultado = 'NOV'
        elif mes == 12:
            resultado = 'DIC'
        return resultado

    def fecha_barras(self,o):
        elab = False
        cad = False

        # conversion a fecha formato especial fecha eleboracion
        dia_elab = o.elaboration_date.day
        mes_elab = o.elaboration_date.month
        anio_elab = o.elaboration_date.year

        elab = str(dia_elab) +'-'+self.mes_abreviado(int(mes_elab))+'-'+str(anio_elab)

        # conversion a fecha formato especial fecha caducidad

        dia_cad = datetime.datetime.strptime(str(o.expiration_date),'%Y-%m-%d %H:%M:%S').strftime("%d")
        mes_cad = datetime.datetime.strptime(str(o.expiration_date),'%Y-%m-%d %H:%M:%S').strftime("%m")
        anio_cad = datetime.datetime.strptime(str(o.expiration_date),'%Y-%m-%d %H:%M:%S').strftime("%Y")

        cad = str(dia_cad) +'-'+self.mes_abreviado(int(mes_cad))+'-'+str(anio_cad)


        return {'elab': elab,'cad':cad}

    def fecha_barras_numero(self,o):
        elab = False
        cad = False

        # conversion a fecha formato especial fecha eleboracion
        dia_elab = o.elaboration_date.day
        mes_elab = o.elaboration_date.month
        anio_elab = o.elaboration_date.year

        elab = str(dia_elab)+str(mes_elab)+str(anio_elab)

        # conversion a fecha formato especial fecha caducidad

        dia_cad = datetime.datetime.strptime(str(o.expiration_date),'%Y-%m-%d %H:%M:%S').strftime("%d")
        mes_cad = datetime.datetime.strptime(str(o.expiration_date),'%Y-%m-%d %H:%M:%S').strftime("%m")
        anio_cad = datetime.datetime.strptime(str(o.expiration_date),'%Y-%m-%d %H:%M:%S').strftime("%Y")

        cad = str(dia_cad)+str(mes_cad)+str(anio_cad)


        return {'elab': elab,'cad':cad}

    def create_lot(self, product_ids):
        op_lote_line_ids = self.env['stock.move.line'].search([('id','in',product_ids )])
        barcode_lot = []
        barcode_lot_list = []

        for p in op_lote_line_ids:
            count = 0
            while count < p.cantidad_etiquetas:
                dates = self.fecha_barras(p.lot_id)
                barcode_info = {
                        'product': p.product_id,
                        'elab':  dates["elab"],
                        'cad':   dates["cad"],
                        'lot': p.lot_id,
                        'quantity': p.cantidad_etiquetas,
                }
                barcode_lot_list.append(barcode_info)
                count += 1
        return barcode_lot_list

    @api.model
    def _get_report_values(self, docids, data=None):
        logging.warning('_get_report_values')

        product_ids = data['form']['product_ids']
        logging.warning("los productos ids")
        logging.warning(product_ids)
        create_lot_f = self.create_lot(product_ids)


        return {
            'doc_ids': docids,
            'doc_model': 'quemen.reporte_codigo_barras_lotet',
            # 'docs': docs,
            'fecha_barras': self.fecha_barras,
            'create_lot': create_lot_f,
        }
