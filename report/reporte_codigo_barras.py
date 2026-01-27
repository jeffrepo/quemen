# -*- coding: utf-8 -*-

from odoo import api, models
import datetime
import logging

class CaodigoBarras(models.AbstractModel):
    _name = 'report.quemen.reporte_codigo_barras'
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
        dia_elab = datetime.datetime.strptime(str(o.create_date),'%Y-%m-%d %H:%M:%S.%f').strftime("%d")
        mes_elab = datetime.datetime.strptime(str(o.create_date),'%Y-%m-%d %H:%M:%S.%f').strftime("%m")
        anio_elab = datetime.datetime.strptime(str(o.create_date),'%Y-%m-%d %H:%M:%S.%f').strftime("%Y")

        elab = str(dia_elab) +'-'+self.mes_abreviado(int(mes_elab))+'-'+str(anio_elab)

        # conversion a fecha formato especial fecha caducidad

        dia_cad = datetime.datetime.strptime(str(o.expiration_date),'%Y-%m-%d %H:%M:%S').strftime("%d")
        mes_cad = datetime.datetime.strptime(str(o.expiration_date),'%Y-%m-%d %H:%M:%S').strftime("%m")
        anio_cad = datetime.datetime.strptime(str(o.expiration_date),'%Y-%m-%d %H:%M:%S').strftime("%Y")

        cad = str(dia_cad) +'-'+self.mes_abreviado(int(mes_cad))+'-'+str(anio_cad)


        return {'elab': elab,'cad':cad}

    @api.model
    def _get_report_values(self, docids, data=None):
        # self.model = 'stock.lot'
        docs = self.env['stock.lot'].browse(docids)

        return {
            'doc_ids': docids,
            'doc_model': 'stock.lot',
            'docs': docs,
            'fecha_barras': self.fecha_barras,
        }
