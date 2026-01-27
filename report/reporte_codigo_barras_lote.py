# -*- coding: utf-8 -*-

from odoo import api, models, _
from odoo.exceptions import UserError, ValidationError
import datetime
import logging

class CaodigoBarrasLote(models.AbstractModel):
    _name = 'report.quemen.reporte_codigo_barras_lote'
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
        logging.warning('EL O')
        logging.warning(product_ids)
        op_lote_line_ids = self.env['quemen.op_lote_line'].search([('id','in',product_ids )])
        barcode_lot = []
        barcode_lot_list = []
        for line in op_lote_line_ids:
            logging.warning(line)
            logging.warning(line.lot_barcode_id)
            if len(line.lot_barcode_id) == 0:
                raise ValidationError(_('No puede generar códigos de barra con productos sin Lote.'))
            if line.elaboration_date:
                logging.warning(line.elaboration_date)
                if line.lot_barcode_id:
                    if line.elaboration_date != line.lot_barcode_id.elaboration_date:
                        elaboration_date = datetime.datetime.fromisoformat(line.elaboration_date.isoformat() + ' 06:00:00')
                        expiration_date = elaboration_date + datetime.timedelta(days=line.product_id.expiration_time)
                        removal_date = elaboration_date + datetime.timedelta(days=line.product_id.removal_time)
                        use_date = elaboration_date + datetime.timedelta(days=line.product_id.use_time)
                        alert_date = elaboration_date + datetime.timedelta(days=line.product_id.alert_time)
                        line.lot_barcode_id.write({
                                          'elaboration_date': elaboration_date,
                                          'expiration_date': expiration_date,
                                          'removal_date': removal_date,
                                          'use_date': use_date,
                                          'alert_date': alert_date})
                else:
                    elaboration_date = datetime.datetime.fromisoformat(line.elaboration_date.isoformat() + ' 06:00:00')
                    expiration_date = elaboration_date + datetime.timedelta(days=line.product_id.expiration_time)
                    removal_date = elaboration_date + datetime.timedelta(days=line.product_id.removal_time)
                    use_date = elaboration_date + datetime.timedelta(days=line.product_id.use_time)
                    alert_date = elaboration_date + datetime.timedelta(days=line.product_id.alert_time)
                    # lot_id = self.env['stock.lot'].create({'product_id': line.product_id.id,
                    #                                                   'elaboration_date': elaboration_date,
                    #                                                   'expiration_date': expiration_date,
                    #                                                   'removal_date': removal_date,
                    #                                                   'use_date': use_date,
                    #                                                   'alert_date': alert_date,
                    #                                                   'company_id': 1})
                    # logging.warning('lote')
                    # logging.warning(lot_id)
                    # if lot_id:
                    #     line.write({'lot_barcode_id': lot_id})

                dates = self.fecha_barras(line.lot_barcode_id)
                # date_numbers = self.fecha_barras_numero(line.lot_barcode_id)
                # logging.warning(date_numbers)
                # barcode_number = line.product_id.barcode + str(date_numbers['elab']) +  str(date_numbers['cad'])
                barcode_lot.append({
                    'product': line.product_id,
                    'elab':  dates['elab'],
                    'cad': dates['cad'],
                    # 'barcode_number': barcode_number,
                    'lot': line.lot_barcode_id,
                    'quantity': line.qty_label,
                })

        logging.warning(barcode_lot)
        for bc in barcode_lot:
            count = 0
            while count < bc['quantity']:
                barcode_info = {
                    'product': bc['product'],
                    'elab':  bc['elab'],
                    'cad': bc['cad'],
                    # 'barcode_number': bc['barcode_number'],
                    'lot': bc['lot'],
                    'quantity': bc['quantity'],
                }
                barcode_lot_list.append(barcode_info)
                count += 1
        return barcode_lot_list

    @api.model
    def _get_report_values(self, docids, data=None):
        logging.warning('_get_report_values')

        product_ids = data['form']['product_ids']
        create_lot_f = self.create_lot(product_ids)


        return {
            'doc_ids': docids,
            'doc_model': 'quemen.reporte_codigo_barras_lote',
            # 'docs': docs,
            'fecha_barras': self.fecha_barras,
            'create_lot': create_lot_f,
        }
