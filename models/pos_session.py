# -*- encoding: utf-8 -*-

from odoo import models, fields, api, _
import logging
from odoo.exceptions import UserError, ValidationError
import ast
from odoo.tools.float_utils import float_compare, float_is_zero

class PosSession(models.Model):
    _inherit = 'pos.session'


    factura_global_id = fields.Many2one("account.move", string="Factura global")
    saldo_apartura = fields.Float('Saldo apertura', compute='_calcular_apertura_retiro_efectivo', store=True)
    total_efectivo_caja = fields.Float('Total efectivo caja', store=True)
    pagos_efectivo = fields.Float('Pagos efectivo',  compute='_calcular_pagos_efectivo', store=True)
    retiros_efectivo = fields.Float('Retiros efectivo', compute='_calcular_apertura_retiro_efectivo')
    pendiente_facturar = fields.Float('Pendiente facturar')

    @api.depends('cash_register_total_entry_encoding', 'cash_register_id.line_ids')
    def _calcular_apertura_retiro_efectivo(self):
        for sesion in self:
            total_saldo_apertura = 0
            efectivo_caja = 0
            retiros = 0
            # cash_register_total_entry_encoding = sesion.​cash_register_total_entry_encoding
            if len(sesion.cash_register_id.line_ids):
                for linea in sesion.cash_register_id.line_ids:
                    if linea.amount < 0:
                        retiros += (linea.amount*-1)
                    if "Opening" in linea.payment_ref:
                        total_saldo_apertura += linea.amount
            sesion.saldo_apartura = total_saldo_apertura
            # efectivo_caja = ​cash_register_total_entry_encoding - total_saldo_apertura + retiros
            sesion.total_efectivo_caja = efectivo_caja
            sesion.retiros_efectivo = retiros

    @api.depends('order_ids','cash_register_total_entry_encoding')
    def _calcular_pagos_efectivo(self):
        for sesion in self:
            # result = self.env['pos.payment'].read_group([('session_id', 'in', self.ids)],['payment_method_id','amount'] ,['payment_method_id'])
            pago_ids = self.env['pos.payment'].search([('session_id','=',sesion.id)])
            efectivo = 0
            if pago_ids:
                for pago in pago_ids:
                    if pago.payment_method_id.name == "Efectivo":
                        efectivo += pago.amount

            # logging.warning('result')
            # logging.warning(result)
            sesion.pagos_efectivo = efectivo


    def generar_factura_global_sesion(self):
        pedidos_facturar =[]
        pagos = {}
        ids_pedidos = []
        lineas_facturar = []
        factura_id = False
        logging.warning('generar_factura_global')
        logging.warning(self)
        for sesion in self:
            if sesion.factura_global_id:
                raise ValidationError(_('La sesión ' + sesion.name + ' actualmente ya contiene una factura global.'))
            if len(sesion.order_ids) > 0:
                for pedido in sesion.order_ids:
                    if pedido.state in ['done', 'paid'] and pedido.amount_total > 0:
                        pedidos_facturar.append(pedido)
                        logging.warn("pedidos_facturar")
                        logging.warn(pedidos_facturar)
                        ids_pedidos.append(pedido.id)
                        for linea in pedido.payment_ids:
                            if linea.payment_method_id.id not in pagos:

                                pagos[linea.payment_method_id.id] = {'diario': linea.payment_method_id.journal_id, 'cantidad': 0}
                            pagos[linea.payment_method_id.id]['cantidad'] += linea.amount
        if pedidos_facturar:
            for pedido in pedidos_facturar:
                for linea in pedido.lines:

                    lineas_facturar.append(linea)
            factura = {
                'partner_id': sesion.config_id.cliente_id.id or 1,
                'ref': sesion.name,
                'invoice_date': fields.Date.context_today(self),
                'invoice_origin': sesion.name,
                'journal_id': sesion.config_id.invoice_journal_id.id,
                'l10n_mx_edi_payment_method_id': self.env['l10n_mx_edi.payment.method'].search([('code','=','01')]).id,
                'l10n_mx_edi_usage': 'S01',
                'move_type': 'out_invoice',
                'pos_order_ids': [(6, 0, ids_pedidos)],
                'invoice_line_ids': [(0, None, self.env['pos.order']._prepare_invoice_line(line)) for line in lineas_facturar],
            }
            factura_id = self.env['account.move'].create(factura)
            logging.warning("Si llega?")
            logging.warning(factura_id)
            if factura_id:
                factura_id.action_post()
                # # self.factura_global_id = factura_id.id
                # for pago in pagos:
                #     logging.warning("PAgos")
                #     logging.warning(pagos[pago])
                #
                #     # 'communication':factura_id.name, linea 68
                #
                #     pago_dic = {'payment_type': 'inbound','date': fields.Date.today(),
                #     'partner_type': 'customer','partner_id':factura_id.partner_id.id,'payment_method_id':1,
                #     'journal_id':pagos[pago]['diario'].id,'amount': pagos[pago]['cantidad'],'reconciled_invoice_ids':  [(6, 0, [factura_id.id])],}
                #     pago_id = self.env['account.payment'].create(pago_dic)
                #     pago_id.action_post()
                #
                #     for linea_gasto in pago_id.move_id.line_ids.filtered(lambda r: r.account_id.user_type_id.type == 'receivable' and not r.reconciled):
                #             for linea_factura in factura_id.line_ids.filtered(lambda r: r.account_id.user_type_id.type == 'receivable' and not r.reconciled):
                #                 if (linea_gasto.debit == linea_factura.credit or linea_gasto.credit - linea_factura.debit ):
                #                     (linea_gasto | linea_factura).reconcile()
                #                     break

        for sesion in self:
            sesion.write({'factura_global_id': factura_id.id})
        return True

    def generar_factura_global(self, sesiones):
        pedidos_facturar = []
        pagos = {}
        ids_pedidos = []
        lineas_facturar = []
        factura_id = False
        pendiente_facturar = 0.0

        logging.warning('generar_factura_global')
        logging.warning(self)

        if not sesiones:
            return True

        sesion_base = sesiones[0]
        currency = sesion_base.company_id.currency_id

        # Seguridad: una factura global debe salir con una sola configuración POS,
        # porque usa un solo cliente, diario y configuración fiscal.
        configs = sesiones.mapped('config_id')
        if len(configs) > 1:
            raise ValidationError(_(
                'No se puede generar una sola factura global con sesiones de diferentes configuraciones POS.'
            ))

        for sesion in sesiones:
            if sesion.factura_global_id:
                raise ValidationError(_('La sesión ' + sesion.name + ' actualmente ya contiene una factura global.'))

            for pedido in sesion.order_ids:
                if pedido.state in ['done', 'paid'] and pedido.amount_total > 0 and not pedido.is_refunded:
                    pedidos_facturar.append(pedido)
                    ids_pedidos.append(pedido.id)
                    pendiente_facturar += pedido.amount_total

                    for pago in pedido.payment_ids:
                        metodo_id = pago.payment_method_id.id
                        if metodo_id not in pagos:
                            pagos[metodo_id] = {
                                'diario': pago.payment_method_id.journal_id,
                                'cantidad': 0.0,
                            }
                        pagos[metodo_id]['cantidad'] += pago.amount

        producto_linea_factura = self.env['product.product'].search([
            ('default_code', '=', '001')
        ], limit=1)

        if not producto_linea_factura:
            raise ValidationError(_('No se encontró el producto genérico de facturación con código interno 001.'))

        metodo_pago_01 = self.env['l10n_mx_edi.payment.method'].search([
            ('code', '=', '01')
        ], limit=1)

        if not metodo_pago_01:
            raise ValidationError(_('No se encontró el método de pago SAT con código 01.'))

        if not pedidos_facturar:
            return True

        def _tax_key_from_line(linea):
            """
            Agrupa por impuestos reales de la línea.
            Usamos tax_ids_after_fiscal_position si existe.
            Si no existe, usamos impuestos del producto.
            """
            taxes = linea.tax_ids_after_fiscal_position
            if not taxes:
                taxes = linea.product_id.taxes_id

            tax_ids = tuple(sorted(taxes.ids))
            return tax_ids

        for pedido in pedidos_facturar:
            positivos = {}
            descuentos = {}

            # 1) Primero resumimos el ticket por grupo de impuestos.
            #    Las líneas positivas forman la base.
            #    Las líneas negativas se guardan como descuento.
            for linea in pedido.lines:
                monto = currency.round(linea.price_subtotal_incl or 0.0)

                if float_is_zero(monto, precision_rounding=currency.rounding):
                    continue

                tax_key = _tax_key_from_line(linea)

                if monto > 0:
                    if tax_key not in positivos:
                        positivos[tax_key] = 0.0
                    positivos[tax_key] += monto

                elif monto < 0:
                    if tax_key not in descuentos:
                        descuentos[tax_key] = 0.0
                    descuentos[tax_key] += abs(monto)

            if not positivos:
                raise ValidationError(_(
                    'El pedido %s tiene total positivo, pero no tiene líneas positivas para facturar.'
                ) % pedido.name)

            grupos = {}

            for tax_key, monto_positivo in positivos.items():
                grupos[tax_key] = {
                    'pedido': pedido.name,
                    'tax_ids': list(tax_key),
                    'positivo': currency.round(monto_positivo),
                    'descuento': 0.0,
                }

            descuento_sin_grupo = 0.0

            # 2) Aplicamos descuentos al mismo grupo de impuestos.
            #    Si el descuento no trae impuestos compatibles, lo dejamos pendiente.
            for tax_key, monto_descuento in descuentos.items():
                monto_descuento = currency.round(monto_descuento)

                if tax_key in grupos:
                    grupos[tax_key]['descuento'] += monto_descuento
                else:
                    descuento_sin_grupo += monto_descuento

            # 3) Si hubiera descuentos sin grupo fiscal compatible,
            #    los distribuimos proporcionalmente entre las bases positivas.
            if not float_is_zero(descuento_sin_grupo, precision_rounding=currency.rounding):
                total_positivo = sum(g['positivo'] for g in grupos.values())

                if float_is_zero(total_positivo, precision_rounding=currency.rounding):
                    raise ValidationError(_(
                        'El pedido %s tiene descuento sin base positiva para aplicarlo.'
                    ) % pedido.name)

                grupos_items = list(grupos.items())
                descuento_asignado = 0.0

                for index, (tax_key, grupo) in enumerate(grupos_items):
                    if index == len(grupos_items) - 1:
                        monto_asignar = descuento_sin_grupo - descuento_asignado
                    else:
                        monto_asignar = currency.round(
                            descuento_sin_grupo * grupo['positivo'] / total_positivo
                        )
                        descuento_asignado += monto_asignar

                    grupo['descuento'] += monto_asignar

            # 4) Validación crítica:
            #    jamás permitir descuento mayor al importe positivo del grupo,
            #    porque eso genera líneas negativas.
            for tax_key, grupo in grupos.items():
                grupo['positivo'] = currency.round(grupo['positivo'])
                grupo['descuento'] = currency.round(grupo['descuento'])

                if float_compare(
                    grupo['descuento'],
                    grupo['positivo'],
                    precision_rounding=currency.rounding
                ) > 0:
                    raise ValidationError(_(
                        'El pedido %s tiene un descuento mayor que su base positiva '
                        'en un grupo de impuestos. Base: %.2f, descuento: %.2f. '
                        'No se generó factura para evitar líneas negativas.'
                    ) % (
                        pedido.name,
                        grupo['positivo'],
                        grupo['descuento'],
                    ))

            # 5) Creamos líneas de factura.
            #    No metemos líneas negativas.
            #    El descuento se expresa como porcentaje.
            for tax_key, grupo in grupos.items():
                positivo = currency.round(grupo['positivo'])
                descuento_monto = currency.round(grupo['descuento'])
                neto = currency.round(positivo - descuento_monto)

                # Si una base quedó completamente descontada, no hace falta crear línea.
                if float_compare(neto, 0.0, precision_rounding=currency.rounding) <= 0:
                    continue

                descuento_pct = 0.0
                if not float_is_zero(descuento_monto, precision_rounding=currency.rounding):
                    descuento_pct = (descuento_monto / positivo) * 100

                if descuento_pct > 100:
                    raise ValidationError(_(
                        'El pedido %s generaría un descuento mayor al 100%%. '
                        'No se generó factura.'
                    ) % pedido.name)

                lineas_facturar.append((0, 0, {
                    'product_id': producto_linea_factura.id,
                    'quantity': 1,
                    'discount': round(descuento_pct, 6),
                    'price_unit': positivo,
                    'name': grupo['pedido'],
                    'tax_ids': [(6, 0, grupo['tax_ids'])],
                    'product_uom_id': producto_linea_factura.uom_id.id,
                }))

        if not lineas_facturar:
            raise ValidationError(_('No se generaron líneas válidas para la factura global.'))

        factura = {
            'partner_id': sesion_base.config_id.cliente_id.id or 1,
            'ref': ', '.join(sesiones.mapped('name')),
            'invoice_date': fields.Date.context_today(self),
            'invoice_origin': ', '.join(sesiones.mapped('name')),
            'factura_global': True,
            'journal_id': sesion_base.config_id.invoice_journal_id.id,
            'l10n_mx_edi_payment_method_id': metodo_pago_01.id,
            'l10n_mx_edi_usage': 'S01',
            'move_type': 'out_invoice',
            'pos_order_ids': [(6, 0, ids_pedidos)],
            'invoice_line_ids': lineas_facturar,
        }

        factura_id = self.env['account.move'].create(factura)

        # 6) Validación antes de publicar.
        #    La factura debe cuadrar contra el total POS.
        total_pos = currency.round(pendiente_facturar)
        total_factura = currency.round(factura_id.amount_total)

        if float_compare(
            total_factura,
            total_pos,
            precision_rounding=currency.rounding
        ) != 0:
            diferencia = currency.round(total_factura - total_pos)
            factura_nombre = factura_id.name or 'Factura en borrador'

            factura_id.unlink()

            raise ValidationError(_(
                'La factura global no cuadra contra POS.\n'
                'Factura: %s\n'
                'Total POS: %.2f\n'
                'Total factura: %.2f\n'
                'Diferencia: %.2f\n'
                'Se eliminó la factura en borrador para evitar publicar un documento incorrecto.'
            ) % (
                factura_nombre,
                total_pos,
                total_factura,
                diferencia,
            ))

        # 7) Validación extra: ninguna línea de factura puede quedar negativa.
        lineas_negativas = factura_id.invoice_line_ids.filtered(
            lambda l: float_compare(l.price_total, 0.0, precision_rounding=currency.rounding) < 0
        )

        if lineas_negativas:
            nombres = ', '.join(lineas_negativas.mapped('name'))
            factura_id.unlink()

            raise ValidationError(_(
                'La factura global generó líneas negativas: %s. '
                'Se eliminó la factura en borrador.'
            ) % nombres)

        factura_id.action_post()

        for sesion in sesiones:
            sesion.write({
                'pendiente_facturar': total_pos,
                'factura_global_id': factura_id.id,
            })

        return True
