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
        pedidos_facturar =[]
        pagos = {}
        ids_pedidos = []
        lineas_facturar = []
        factura_id = False
        logging.warning('generar_factura_global')
        logging.warning(self)
        lineas_facturar_dic = {}
        pendiente_facturar = 0
        for sesion in sesiones:
            if sesion.factura_global_id:
                raise ValidationError(_('La sesión ' + sesion.name + ' actualmente ya contiene una factura global.'))
            if len(sesion.order_ids) > 0:
                for pedido in sesion.order_ids:
                    if pedido.state in ['done', 'paid'] and pedido.amount_total > 0 and (pedido.is_refunded==False):
                        pedidos_facturar.append(pedido)
                        logging.warn("pedidos_facturar")
                        logging.warn(pedidos_facturar)
                        ids_pedidos.append(pedido.id)
                        for linea in pedido.payment_ids:
                            if linea.payment_method_id.id not in pagos:

                                pagos[linea.payment_method_id.id] = {'diario': linea.payment_method_id.journal_id, 'cantidad': 0}
                            pagos[linea.payment_method_id.id]['cantidad'] += linea.amount
        producto_linea_factura = self.env['product.product'].search([('default_code','=','001')])
        if pedidos_facturar:
            for pedido in pedidos_facturar:
                pendiente_facturar += pedido.amount_total
                # descuento = 0
                # precio_unitario = 0
                impuesto_programa = False
                producto_0_ids = False
                producto_16_ids = False
                total_descuento_0 = 0
                impuesto_programa_0 = False
                impuesto_programa_16 = False
                total_descuento_16 = 0
                pedido_impuesto = pedido.amount_tax
                impuesto_programa_ieps8 = False
                for linea in pedido.lines:
                    if linea.price_subtotal_incl < 0 and linea.program_id:
                        dominio = linea.program_id.rule_products_domain
                        dominio = ast.literal_eval(dominio)
                        #producto_ids = self.env['product.product'].search(dominio)
                        producto_ids = []
                        if linea.program_id.discount_specific_product_ids.ids:
                            producto_ids = self.env['product.product'].search([('id','in', linea.program_id.discount_specific_product_ids.ids)])
                        else:
                            producto_ids = linea.program_id.discount_line_product_id

                        logging.warning("****************************")
                        logging.warning(producto_ids[0].name)
                        logging.warning(producto_ids[0].taxes_id)
                        if producto_ids[0].taxes_id[0].name == "IVA(16%) VENTAS":
                            impuesto_programa_16 =  "IVA(16%) VENTAS"
                            total_descuento_16 += (linea.price_subtotal_incl*-1)
                            producto_16_ids = self.env['product.product'].search(dominio)
                            producto_16_ids += linea.program_id.discount_specific_product_ids
                        else:
                            impuesto_programa_0 = "IVA(0%) VENTAS"
                            total_descuento_0 += (linea.price_subtotal_incl*-1)
                            producto_0_ids = self.env['product.product'].search(dominio)
                            producto_0_ids += linea.program_id.discount_specific_product_ids

                        if len(producto_ids[0].taxes_id) > 1:
                            if producto_ids[0].taxes_id[1].name == "IEPS(8%) VENTAS":
                                impuesto_programa_ieps8 = True

                for linea in pedido.lines:
                    llave = str(linea.order_id.name)+str(linea.tax_ids_after_fiscal_position[0].name)
                    if linea.price_subtotal_incl > 0:

                        if llave not in lineas_facturar_dic:
                            # linea_0 = True if linea.tax_ids_after_fiscal_position[0].name == "IVA(0%) VENTAS" else False
                            # linea_16 = True if linea.tax_ids_after_fiscal_position[0].name == "IVA(16%) VENTAS" else False
                            linea_0 = linea.tax_ids_after_fiscal_position.filtered(lambda t: t.name == "IVA(0%) VENTAS")
                            linea_16 = linea.tax_ids_after_fiscal_position.filtered(lambda t: t.name == "IVA(16%) VENTAS")

                            # Si la promoción tiene IEPS y este producto aplica IEPS, añadirlo.
                            if impuesto_programa_ieps8 and any('IEPS' in t.name for t in linea.product_id.taxes_id):
                                tax_ids = [(6, 0, linea.product_id.taxes_id.ids)]
                            else:
                                # Usar los impuestos reales de la línea
                                tax_ids = [(6, 0, linea.tax_ids_after_fiscal_position.ids)]
                            logging.warning("lineas factura _----------------")
                            logging.warning(tax_ids)
                            linea_factura = {
                                'product_id': producto_linea_factura.id,
                                'quantity': 1,
                                'discount': 0,
                                'price_unit': 0,
                                'name': pedido.name,
                                'tax_ids': tax_ids,
                                'product_uom_id': producto_linea_factura.uom_id.id,
                                'total_descuento_0': total_descuento_0,
                                'total_descuento_16': total_descuento_16,
                                'linea_0': linea_0,
                                'linea_16': linea_16,
                            }
                            lineas_facturar_dic[llave] = linea_factura
                        if (impuesto_programa_0 and producto_0_ids) and (linea.product_id.id in producto_0_ids.ids) and (linea.tax_ids_after_fiscal_position[0].name == impuesto_programa_0):
                            lineas_facturar_dic[llave]['price_unit'] += linea.price_subtotal_incl
                            if lineas_facturar_dic[llave]['tax_ids'] == False:
                                lineas_facturar_dic[llave]['tax_ids'] = [(6, 0, linea.product_id.taxes_id.ids)]
                        elif (impuesto_programa_16 and producto_16_ids) and (linea.product_id.id in producto_16_ids.ids) and (linea.tax_ids_after_fiscal_position[0].name == impuesto_programa_16):
                            lineas_facturar_dic[llave]['price_unit'] += linea.price_subtotal_incl
                            if lineas_facturar_dic[llave]['tax_ids'] == False:
                                lineas_facturar_dic[llave]['tax_ids'] = [(6, 0, linea.tax_ids_after_fiscal_position.ids)]
                        else:
                            lineas_facturar_dic[llave]['price_unit'] += linea.price_subtotal_incl
                            if lineas_facturar_dic[llave]['tax_ids'] == False:
                                lineas_facturar_dic[llave]['tax_ids'] = [(6, 0, linea.product_id.taxes_id.ids)]
                            if total_descuento_0 == 0:
                                if 'total_descuento_0' in lineas_facturar_dic[llave]:
                                    del lineas_facturar_dic[llave]['total_descuento_0']
                            else:
                                if linea.tax_ids_after_fiscal_position[0].name != impuesto_programa_0:
                                    if 'total_descuento_0' in lineas_facturar_dic[llave]:
                                        del lineas_facturar_dic[llave]['total_descuento_0']
                                    if total_descuento_16 == 0:
                                        if 'total_descuento_16' in lineas_facturar_dic[llave]:
                                            del lineas_facturar_dic[llave]['total_descuento_16']

                            if total_descuento_16 == 0:
                                    if 'total_descuento_16' in lineas_facturar_dic[llave]:
                                        del lineas_facturar_dic[llave]['total_descuento_16']

            for ticket in lineas_facturar_dic:
                logging.warning('lineas')
                logging.warning(ticket)
                logging.warning(lineas_facturar_dic[ticket])
                # if 'total_descuento_0' in lineas_facturar_dic[ticket] and lineas_facturar_dic[ticket]['total_descuento_0'] > 0 and lineas_facturar_dic[ticket]['linea_0']:
                #     precio_unitario = lineas_facturar_dic[ticket]['price_unit']
                #     precio_con_descuento = 0
                #     precio_con_descuento = lineas_facturar_dic[ticket]['price_unit'] - lineas_facturar_dic[ticket]['total_descuento_0']
                #     descuento = ((precio_unitario - precio_con_descuento) / precio_unitario)*100
                #     lineas_facturar_dic[ticket]['discount'] = descuento
                #     del lineas_facturar_dic[ticket]['total_descuento_0']
                # if 'total_descuento_16' in lineas_facturar_dic[ticket] and lineas_facturar_dic[ticket]['total_descuento_16'] > 0 and lineas_facturar_dic[ticket]['linea_16']:
                #     precio_unitario = lineas_facturar_dic[ticket]['price_unit']
                #     precio_con_descuento = 0
                #     precio_con_descuento = lineas_facturar_dic[ticket]['price_unit'] - lineas_facturar_dic[ticket]['total_descuento_16']
                #     descuento = ((precio_unitario - precio_con_descuento) / precio_unitario)*100
                #     lineas_facturar_dic[ticket]['discount'] = descuento
                #     del lineas_facturar_dic[ticket]['total_descuento_16']
                # logging.warning('linea facturar')
                # if 'total_descuento_16' in lineas_facturar_dic[ticket]:
                #     logging.warning(ticket)
                #     logging.warning(lineas_facturar_dic[ticket])
                #     del lineas_facturar_dic[ticket]['total_descuento_16']
                # if 'total_descuento_0' in lineas_facturar_dic[ticket]:
                #     logging.warning(ticket)
                #     logging.warning(lineas_facturar_dic[ticket])
                #     del lineas_facturar_dic[ticket]['total_descuento_0']

                # del lineas_facturar_dic[ticket]['linea_0']
                # del lineas_facturar_dic[ticket]['linea_16']
                if 'total_descuento_0' in lineas_facturar_dic[ticket] and lineas_facturar_dic[ticket]['total_descuento_0'] > 0 and lineas_facturar_dic[ticket]['linea_0']:
                    precio_unitario = lineas_facturar_dic[ticket]['price_unit']
                    precio_con_descuento = 0
                    precio_con_descuento = lineas_facturar_dic[ticket]['price_unit'] - lineas_facturar_dic[ticket]['total_descuento_0']
                    descuento = ((precio_unitario - precio_con_descuento) / precio_unitario)*100
                    lineas_facturar_dic[ticket]['discount'] = descuento
                    del lineas_facturar_dic[ticket]['total_descuento_0']
                if 'total_descuento_16' in lineas_facturar_dic[ticket] and lineas_facturar_dic[ticket]['total_descuento_16'] > 0 and lineas_facturar_dic[ticket]['linea_16']:
                    precio_unitario = lineas_facturar_dic[ticket]['price_unit']
                    precio_con_descuento = 0
                    precio_con_descuento = lineas_facturar_dic[ticket]['price_unit'] - lineas_facturar_dic[ticket]['total_descuento_16']
                    descuento = ((precio_unitario - precio_con_descuento) / precio_unitario)*100
                    lineas_facturar_dic[ticket]['discount'] = descuento
                    del lineas_facturar_dic[ticket]['total_descuento_16']

                if 'total_descuento_16' in lineas_facturar_dic[ticket]:
                    del lineas_facturar_dic[ticket]['total_descuento_16']
                if 'total_descuento_0' in lineas_facturar_dic[ticket]:
                    del lineas_facturar_dic[ticket]['total_descuento_0']

                del lineas_facturar_dic[ticket]['linea_0']
                del lineas_facturar_dic[ticket]['linea_16']
                lineas_facturar.append((0,0,lineas_facturar_dic[ticket]))

            factura = {
                'partner_id': sesion.config_id.cliente_id.id or 1,
                'ref': sesion.name,
                'invoice_date': fields.Date.context_today(self),
                'invoice_origin': sesion.name,
                'factura_global': True,
                'journal_id': sesion.config_id.invoice_journal_id.id,
                'l10n_mx_edi_payment_method_id': self.env['l10n_mx_edi.payment.method'].search([('code','=','01')]).id,
                'l10n_mx_edi_usage': 'S01',
                'move_type': 'out_invoice',
                'pos_order_ids': [(6, 0, ids_pedidos)],
                'invoice_line_ids': lineas_facturar,
            }
            factura_id = self.env['account.move'].create(factura)
            logging.warning("Si llega?")
            logging.warning(factura_id)

            if factura_id:

                factura_id.action_post()
                # self.factura_global_id = factura_id.id
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

        for sesion in sesiones:
            sesion.write({'pendiente_facturar': pendiente_facturar})
            sesion.write({'factura_global_id': factura_id.id})
        return True

    # def action_pos_session_validate(self, balancing_account=False, amount_to_balance=0, bank_payment_method_diffs=None):
    #     logging.warn('test')
    #     pedidos_facturar =[]
    #     pagos = {}
    #     ids_pedidos = []
    #     logging.warn(self.order_ids)
    #     if self.order_ids:
    #         for pedido in self.order_ids:
    #             logging.warn(pedido.state)
    #             if pedido.state in ['done', 'paid']:
    #                 pedidos_facturar.append(pedido)
    #                 logging.warn("pedidos_facturar")
    #                 logging.warn(pedidos_facturar)
    #                 ids_pedidos.append(pedido.id)
    #                 for linea in pedido.payment_ids:
    #                     if linea.payment_method_id.id not in pagos:

    #                         pagos[linea.payment_method_id.id] = {'diario': linea.payment_method_id.journal_id, 'cantidad': 0}
    #                     pagos[linea.payment_method_id.id]['cantidad'] += linea.amount

    #     logging.warn(pedidos_facturar)
    #     lineas_facturar = []
    #     logging.warn(pagos)
    #     logging.warning("Que onda?")
    #     logging.warning(self.config_id.invoice_journal_id.name)
    #     logging.warning(self.config_id.invoice_journal_id.id)
    #     if pedidos_facturar:
    #         for pedido in pedidos_facturar:
    #             for linea in pedido.lines:
    #                 lineas_facturar.append(linea)
    #         factura = {
    #             'partner_id': self.config_id.cliente_id.id or 1,
    #             'ref': self.name,
    #             'invoice_date': fields.Date.context_today(self),
    #             'invoice_origin': self.name,
    #             'journal_id': self.config_id.invoice_journal_id.id,
    #             'move_type': 'out_invoice',
    #             'pos_order_ids': [(6, 0, ids_pedidos)],
    #             'invoice_line_ids': [(0, None, self.env['pos.order']._prepare_invoice_line(line)) for line in lineas_facturar],
    #         }
    #         factura_id = self.env['account.move'].create(factura)
    #         logging.warning("Si llega?")
    #         logging.warning(factura_id)
    #         logging.warning(factura)
    #         if factura_id:
    #             factura_id.action_post()
    #             self.factura_global_id = factura_id.id
    #             for pago in pagos:
    #                 logging.warning("PAgos")
    #                 logging.warning(pagos[pago])

    #                 # 'communication':factura_id.name, linea 68

    #                 pago_dic = {'payment_type': 'inbound','date': fields.Date.today(),
    #                 'partner_type': 'customer','partner_id':factura_id.partner_id.id,'payment_method_id':1,
    #                 'journal_id':pagos[pago]['diario'].id,'amount': pagos[pago]['cantidad'],'reconciled_invoice_ids':  [(6, 0, [factura_id.id])],}
    #                 pago_id = self.env['account.payment'].create(pago_dic)
    #                 pago_id.action_post()

    #                 for linea_gasto in pago_id.move_id.line_ids.filtered(lambda r: r.account_id.user_type_id.type == 'receivable' and not r.reconciled):
    #                         for linea_factura in factura_id.line_ids.filtered(lambda r: r.account_id.user_type_id.type == 'receivable' and not r.reconciled):
    #                             if (linea_gasto.debit == linea_factura.credit or linea_gasto.credit - linea_factura.debit ):
    #                                 (linea_gasto | linea_factura).reconcile()
    #                                 break



    #     res = super(PosSession, self).action_pos_session_validate(balancing_account, amount_to_balance, bank_payment_method_diffs)
    #     return res
