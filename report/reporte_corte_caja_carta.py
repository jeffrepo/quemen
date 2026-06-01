from odoo import api, models, _
from odoo.exceptions import UserError, ValidationError
from datetime import datetime
import pytz
import ast
import logging

class ReporteCorteCajaCarta(models.AbstractModel):
    _name = 'report.quemen.reporte_corte_caja_carta'

    nombre_reporte=''

    def _pedidos_validos_corte(self, docs):
        """Pedidos válidos de la sesión para corte/facturación."""
        pedidos = self.env['pos.order']
        for sesion in docs:
            pedidos |= sesion.order_ids.filtered(
                lambda p: (
                    p.invalido is False
                    and p.state in ['done', 'paid', 'invoiced']
                    and p.amount_total > 0
                    and not p.is_refunded
                )
            )
        return pedidos

    def _tax_key_from_pos_line(self, linea):
        """Misma llave fiscal usada por la factura global: impuestos reales de la línea."""
        taxes = linea.tax_ids_after_fiscal_position
        if not taxes:
            taxes = linea.product_id.taxes_id
        return tuple(sorted(taxes.ids))

    def _preparar_lineas_global_simulada(self, docs, pedidos=None):
        """
        Prepara líneas fiscales simuladas con la misma lógica conceptual de
        pos_session.generar_factura_global:
        - líneas positivas forman la base;
        - líneas negativas se convierten en descuento;
        - se agrupa por pedido + grupo de impuestos;
        - no se generan líneas negativas.
        """
        lineas_facturar_dic = {}

        if pedidos is None:
            pedidos = self._pedidos_validos_corte(docs)

        if not pedidos:
            return lineas_facturar_dic

        sesion_base = docs[0] if len(docs) else False
        currency = (
            sesion_base.company_id.currency_id
            if sesion_base
            else self.env.company.currency_id
        )

        producto_linea_factura = self.env['product.product'].search([
            ('default_code', '=', '001')
        ], limit=1)

        if not producto_linea_factura:
            raise ValidationError(_('No se encontró el producto genérico de facturación con código interno 001.'))

        for pedido in pedidos:
            positivos = {}
            descuentos = {}

            for linea in pedido.lines:
                monto = currency.round(linea.price_subtotal_incl or 0.0)
                if abs(monto) < currency.rounding:
                    continue

                tax_key = self._tax_key_from_pos_line(linea)

                if monto > 0:
                    positivos[tax_key] = positivos.get(tax_key, 0.0) + monto
                elif monto < 0:
                    descuentos[tax_key] = descuentos.get(tax_key, 0.0) + abs(monto)

            if not positivos:
                continue

            grupos = {}
            for tax_key, monto_positivo in positivos.items():
                grupos[tax_key] = {
                    'pedido': pedido.name,
                    'tax_ids': list(tax_key),
                    'positivo': currency.round(monto_positivo),
                    'descuento': 0.0,
                }

            descuento_sin_grupo = 0.0
            for tax_key, monto_descuento in descuentos.items():
                monto_descuento = currency.round(monto_descuento)
                if tax_key in grupos:
                    grupos[tax_key]['descuento'] += monto_descuento
                else:
                    descuento_sin_grupo += monto_descuento

            if abs(descuento_sin_grupo) >= currency.rounding:
                total_positivo = sum(g['positivo'] for g in grupos.values())
                if abs(total_positivo) < currency.rounding:
                    continue

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

            for tax_key, grupo in grupos.items():
                positivo = currency.round(grupo['positivo'])
                descuento_monto = currency.round(grupo['descuento'])

                # Evitar descuentos mayores al 100% para no generar líneas negativas.
                if descuento_monto > positivo:
                    raise ValidationError(_(
                        'El pedido %s tiene un descuento mayor que su base positiva '
                        'en un grupo de impuestos. Base: %.2f, descuento: %.2f.'
                    ) % (pedido.name, positivo, descuento_monto))

                neto = currency.round(positivo - descuento_monto)
                if neto <= 0:
                    continue

                descuento_pct = 0.0
                if descuento_monto:
                    descuento_pct = (descuento_monto / positivo) * 100.0

                llave = '%s-%s' % (pedido.name, '-'.join(map(str, tax_key)))
                lineas_facturar_dic[llave] = {
                    'product_id': producto_linea_factura.id,
                    'quantity': 1,
                    'discount': round(descuento_pct, 6),
                    'price_unit': positivo,
                    'name': pedido.name,
                    'tax_ids': [(6, 0, grupo['tax_ids'])],
                    'product_uom_id': producto_linea_factura.uom_id.id,
                    'origen': 'global_simulada',
                }

        return lineas_facturar_dic

    def datos_factura(self, docs):
        """
        Compatibilidad con el reporte anterior.
        Ahora devuelve únicamente líneas simuladas con la lógica de factura global.
        """
        return self._preparar_lineas_global_simulada(docs)

    def _normalizar_tax_ids(self, linea):
        tax_ids = []
        if linea.get('tax_ids'):
            if isinstance(linea['tax_ids'], (list, tuple)):
                if linea['tax_ids'] and isinstance(linea['tax_ids'][0], (list, tuple)):
                    tax_ids = linea['tax_ids'][0][2]
                else:
                    tax_ids = list(linea['tax_ids'])
            else:
                tax_ids = [linea['tax_ids']]
        return tax_ids

    def _acumular_linea_en_corte(self, linea, ventas_sesion, totales_ventas_sesion, currency):
        """
        Acumula una línea estilo factura en ventas_sesion/totales_ventas_sesion.
        Las columnas de ventas e impuestos muestran importes antes de descuento.
        Las columnas de descuento muestran el efecto del descuento.
        IEPS neto = IEPS 8% - Desct IEPS 8%.
        """
        ticket_ref = linea['name']

        tax_ids = self._normalizar_tax_ids(linea)
        taxes = self.env['account.tax'].browse(tax_ids) if tax_ids else False

        discount = linea.get('discount', 0.0) or 0.0
        price_unit = linea.get('price_unit', 0.0) or 0.0
        qty = linea.get('quantity', 1.0) or 1.0
        price_unit_desc = price_unit * (1 - discount / 100.0)
        product = self.env['product.product'].browse(linea['product_id'])

        def _compute(price_unit_):
            if not taxes:
                total = price_unit_ * qty
                return {
                    'total_excluded': total,
                    'total_included': total,
                    'taxes': [],
                }
            return taxes.compute_all(
                price_unit_,
                currency,
                qty,
                product=product,
                partner=False,
            )

        res_before = _compute(price_unit)
        res_after = _compute(price_unit_desc)

        def _split(res):
            base0 = sum(t['base'] for t in res['taxes'] if '0%' in t['name'])
            base16 = sum(t['base'] for t in res['taxes'] if '16%' in t['name'])
            iva = sum(t['amount'] for t in res['taxes'] if 'IVA' in t['name'])
            ieps = sum(t['amount'] for t in res['taxes'] if 'IEPS' in t['name'])
            return base0, base16, iva, ieps, res['total_excluded'], res['total_included']

        b0_before, b16_before, iva_before, ieps_before, _, _ = _split(res_before)
        b0_after, b16_after, iva_after, ieps_after, _, total_after = _split(res_after)

        ventas_sin_iva = b0_before
        ventas_iva = b16_before
        ieps8 = ieps_before
        iva = iva_after
        total = total_after

        descuento_sin_iva = max(b0_before - b0_after, 0.0)
        descuento_base16 = max(b16_before - b16_after, 0.0)
        descuento_ieps8 = max(ieps_before - ieps_after, 0.0)
        descuento_iva_impuesto = max(iva_before - iva_after, 0.0)

        descuento_total = (
            descuento_sin_iva +
            descuento_base16 +
            descuento_ieps8 +
            descuento_iva_impuesto
        )

        if ticket_ref not in ventas_sesion:
            ventas_sesion[ticket_ref] = {
                'venta': ticket_ref,
                'ventas_sin_iva': 0.0,
                'descuento_sin_iva': 0.0,
                'ventas_iva': 0.0,
                'descuento_iva': 0.0,
                'ieps8': 0.0,
                'descuento_ieps8': 0.0,
                'descuento': 0.0,
                'iva': 0.0,
                'total': 0.0,
                'fp': 'M',
                'e': 0,
            }

        ventas_sesion[ticket_ref]['ventas_sin_iva'] += ventas_sin_iva
        ventas_sesion[ticket_ref]['descuento_sin_iva'] += descuento_sin_iva
        ventas_sesion[ticket_ref]['ventas_iva'] += ventas_iva
        ventas_sesion[ticket_ref]['descuento_iva'] += descuento_base16
        ventas_sesion[ticket_ref]['ieps8'] += ieps8
        ventas_sesion[ticket_ref]['descuento_ieps8'] += descuento_ieps8
        ventas_sesion[ticket_ref]['descuento'] += descuento_total
        ventas_sesion[ticket_ref]['iva'] += iva
        ventas_sesion[ticket_ref]['total'] += total

        totales_ventas_sesion['ventas_sin_iva'] += ventas_sin_iva
        totales_ventas_sesion['descuento_sin_iva'] += descuento_sin_iva
        totales_ventas_sesion['ventas_iva'] += ventas_iva
        totales_ventas_sesion['descuento_iva'] += descuento_base16
        totales_ventas_sesion['ieps8'] += ieps8
        totales_ventas_sesion['descuento_ieps8'] += descuento_ieps8
        totales_ventas_sesion['descuento'] += descuento_total
        totales_ventas_sesion['iva'] += iva
        totales_ventas_sesion['total'] += total

    def _acumular_facturas_individuales_en_corte(self, pedidos, ventas_sesion, totales_ventas_sesion, currency):
        """
        Para pedidos ya facturados fuera de la global, usa las líneas reales de su factura.
        Así el corte suma: facturas individuales reales + global simulada.
        """
        producto_generico = self.env['product.product'].search([
            ('default_code', '=', '001')
        ], limit=1)

        facturas_procesadas = self.env['account.move']

        for pedido in pedidos:
            factura = pedido.account_move
            if not factura or factura.state != 'posted' or factura.move_type != 'out_invoice':
                continue

            facturas_procesadas |= factura

            lineas_reales = factura.invoice_line_ids.filtered(
                lambda l: not l.display_type and l.product_id
            )

            for linea_factura in lineas_reales:
                linea = {
                    'product_id': linea_factura.product_id.id or producto_generico.id,
                    'quantity': linea_factura.quantity or 1.0,
                    'discount': linea_factura.discount or 0.0,
                    'price_unit': linea_factura.price_unit or 0.0,
                    'name': pedido.name,
                    'tax_ids': [(6, 0, linea_factura.tax_ids.ids)],
                    'product_uom_id': linea_factura.product_uom_id.id if linea_factura.product_uom_id else False,
                    'origen': 'factura_individual',
                }
                self._acumular_linea_en_corte(
                    linea,
                    ventas_sesion,
                    totales_ventas_sesion,
                    currency,
                )

        return facturas_procesadas

    def _calcular_ieps_facturas(self, facturas):
        ieps = 0.0
        for factura in facturas:
            for linea in factura.line_ids.filtered(
                lambda l: l.tax_line_id and 'IEPS' in l.tax_line_id.name
            ):
                ieps += abs(linea.balance)
        return ieps

    def sesiones(self, docs):
        listado_productos = []
        listado_totales = []
        cantidad = 0
        elementos = 0
        elementos1 = 0
        precio_unitario = 0
        descuento = 0
        descuento_lineas =0
        total_suma_descuento = 0
        total_suma_descuento_iva = 0
        total_columnas_descuento_iva = 0
        impuestos = 0
        linea_iva = 0
        porcentaje = 0
        total=0
        lineas = 0
        iva_venta = 0
        calculo_descuento_iva = 0
        calculo_precio_cantidad=0
        calculo_precio_cantidad_iva=0
        ventas_porciento_iva = 0
        ventas_porciento_sin_iva = 0
        total_columnas_ventas_sin_iva = 0
        total_columnas_ventas_iva = 0
        total_columnas_descuento_sin_iva = 0
        total_columna_descuento = 0
        total_columna_iva = 0
        total_columna_total = 0
        total_ventas_mostrador = 0
        suma_iva = 0
        importe = 0
        folios = []
        pedidos_no_facturados = []
        pedidos_facturados = []
        listado_referencia_facturas = []
        metodos_pago = {}
        productos = docs.order_ids.filtered(lambda order: order.invalido is False).lines
        pago_efectivo = 0
        contador_efectivo = 0
        ventas = docs.order_ids.filtered(lambda order: order.invalido is False)
        facturas = ventas.account_move
        numero_recibo = []
        importe_descuento = 0

        # DEV JEFFREPO

        dic_formas_pago = {'Tarjeta credito': 'TC', 'Efectivo': 'E', 'Tarjeta debito': 'TD', '​Transferencia': 'T', 'Tarjeta crédito': 'TC',}
        ventas_mostrador = {'folios': False, 'importe': 0.00, 'descuento': 0.00, 'total': 0}
        total_ventas_mostrador = 0.00
        ventas_sesion = {}
        totales_ventas_sesion = {'ventas_sin_iva': 0, 'descuento_sin_iva': 0, 'ventas_iva': 0, 'descuento_iva': 0, 'ieps8':0, 'descuento_ieps8': 0, 'descuento': 0, 'iva': 0, 'total': 0}
        resumen_facturas_expedidas = {'serie': '', 'folios': '', 'venta_sin_iva': 0.00, 'venta_iva': 0.00, 'iva': 0.00, 'total': 0.00}
        resumen_factura_global = {'serie': '', 'folios': '', 'venta_sin_iva': 0.00, 'venta_iva': 0.00, 'iva': 0.00, 'total': 0.00}
        total_facturas_expedidas = 0.00
        detalle_facturas_expedidas = {}
        total_detalle_facturas_expedidas = 0.00
        diferencia = 0.00
        apertura_efectivo = docs.cash_register_balance_start
        total_retiro_efectivo = 0.00
        total_retiro_efectivo_sesion_previa = 0.00
        venta_efectivo = 0.00
        cierre_efectivo = docs.cash_register_balance_end_real
        retiro_corte_previo = {}

        # ----------------------------------------------------------------------
        # Cálculo fiscal del corte:
        # 1) Pedidos ya facturados individualmente: se usan sus facturas reales.
        # 2) Pedidos sin factura individual: se simula la futura factura global
        #    con la misma lógica de generar_factura_global.
        # ----------------------------------------------------------------------
        ventas_sesion = {}
        totales_ventas_sesion = {
            'ventas_sin_iva': 0.0,
            'descuento_sin_iva': 0.0,
            'ventas_iva': 0.0,
            'descuento_iva': 0.0,
            'ieps8': 0.0,
            'descuento_ieps8': 0.0,
            'descuento': 0.0,
            'iva': 0.0,
            'total': 0.0,
        }

        currency = docs.currency_id or self.env.company.currency_id

        pedidos_corte = self._pedidos_validos_corte(docs)
        pedidos_facturados_individuales = pedidos_corte.filtered(lambda p: p.account_move)
        pedidos_para_global = pedidos_corte.filtered(lambda p: not p.account_move)

        # Facturas individuales existentes.
        facturas_individuales = self._acumular_facturas_individuales_en_corte(
            pedidos_facturados_individuales,
            ventas_sesion,
            totales_ventas_sesion,
            currency,
        )

        # Futura factura global simulada.
        lineas_facturar_dic = self._preparar_lineas_global_simulada(
            docs,
            pedidos=pedidos_para_global,
        )

        for llave, linea in lineas_facturar_dic.items():
            self._acumular_linea_en_corte(
                linea,
                ventas_sesion,
                totales_ventas_sesion,
                currency,
            )

        ieps_facturas_individuales = self._calcular_ieps_facturas(facturas_individuales)
        ieps_global_simulado_neto = (
            totales_ventas_sesion['ieps8'] -
            totales_ventas_sesion['descuento_ieps8'] -
            ieps_facturas_individuales
        )
        ieps_total_fiscal = (
            ieps_facturas_individuales +
            ieps_global_simulado_neto
        )

        totales_ventas_sesion['ieps_facturas_individuales'] = ieps_facturas_individuales
        totales_ventas_sesion['ieps_global_simulado'] = ieps_global_simulado_neto
        totales_ventas_sesion['ieps_total_fiscal'] = ieps_total_fiscal

        for referencia in ventas:
            # folio = referencia.name.split("/", 1)[1]
            # serie = referencia.name.split("/", 1)[0]
            folios.append(referencia.name)
            folios.sort()
            total_suma_subtotal = 0
            calculo_precio_sin_iva = 0
            sumas_descuento = 0
            precio_original_iva = 0
            suma_descuento_iva = 0
            suma_descuento_sin_iva = 0

            if referencia.state != "invoiced":
                pedidos_no_facturados.append(referencia.id)
            else:
                pedidos_facturados.append(referencia.id)

            listado_productos.append({'venta': referencia.name,'ventas_sin_iva': 0, 'descuento_sin_iva': 0, 'ventas_iva': 0, 'descuento_iva': 0, 'descuento': 0, 'iva': 0, 'total': 0, 'fp': 0, 'e':0})

            iva_venta = referencia.amount_tax
            total = referencia.amount_total
            suma_iva = round(iva_venta, 2)

            for linea_pago in referencia.payment_ids:
                if linea_pago.payment_method_id.name == 'Efectivo':
                    venta_efectivo += linea_pago.amount

            for lineas in referencia.lines:
                linea_iva = lineas.tax_ids_after_fiscal_position
                cantidad = lineas.qty
                precio_unitario = lineas.price_unit
                descuento_lineas = lineas.discount
                porcentaje = descuento_lineas/100
                if len(linea_iva) > 0:
                    for impuesto in linea_iva:
                        if 'IEPS' in impuesto.name:
                            calculo_precio_cantidad_iva = (cantidad * precio_unitario) * porcentaje
                            suma_descuento_iva += calculo_precio_cantidad_iva
                            precio_original_iva += cantidad * precio_unitario
                        else:
                            calculo_precio_cantidad_iva = (cantidad * precio_unitario) * porcentaje
                            suma_descuento_iva += calculo_precio_cantidad_iva
                            precio_original_iva += cantidad * precio_unitario
                else:
                    calculo_precio_cantidad = (cantidad * precio_unitario)*porcentaje
                    suma_descuento_sin_iva += calculo_precio_cantidad
                    calculo_precio_sin_iva += cantidad * precio_unitario

            total_suma_descuento_iva = suma_descuento_iva
            total_suma_descuento = suma_descuento_sin_iva
            sumas_descuento = total_suma_descuento_iva + total_suma_descuento
            ventas_porciento_iva = precio_original_iva
            ventas_porciento_sin_iva = calculo_precio_sin_iva
            acceder = listado_productos[elementos]
            total_columnas_ventas_sin_iva += round(ventas_porciento_sin_iva, 2)
            total_columnas_ventas_iva += round(ventas_porciento_iva, 2)
            total_columnas_descuento_iva += round(total_suma_descuento_iva, 2)
            total_columna_descuento += round(sumas_descuento, 2)
            total_columna_iva += self.env.company.currency_id.round(suma_iva)
            total_columnas_descuento_sin_iva += round(total_suma_descuento, 2)
            total_columna_total += total
            if referencia.amount_total <= 0:
                numero_recibo.append(referencia.pos_reference)

            importe = round(total_columnas_ventas_sin_iva + total_columnas_ventas_iva + total_columna_iva, 2)
            total_ventas_mostrador = round(importe - total_columna_descuento, 2)

            importe1 = 0
            total_pagos = 0
            total_importe_pagos = 0

            for lineas_pagos in referencia.payment_ids:

                inicial = lineas_pagos.payment_method_id.name.split(' ', 0)[0]
                # inicial1 = inicial[0]
                inicial1 = lineas_pagos.payment_method_id.journal_id.code

                if lineas_pagos.payment_method_id.id not in metodos_pago:
                    metodos_pago[lineas_pagos.payment_method_id.id]={'tipo': lineas_pagos.payment_method_id.name, 'importe': 0, 'id': lineas_pagos.payment_method_id.id, 'conteo': 0}


                if lineas_pagos.payment_method_id.id == metodos_pago[lineas_pagos.payment_method_id.id]['id']:
                    importe1 = lineas_pagos.amount
                    metodos_pago[lineas_pagos.payment_method_id.id]['conteo'] += 1

                metodos_pago[lineas_pagos.payment_method_id.id]['importe'] += importe1


            for desc in acceder:
                acceder['ventas_sin_iva'] = ventas_porciento_sin_iva
                acceder['ventas_iva'] = ventas_porciento_iva
                acceder['total'] = total
                acceder['descuento_sin_iva'] = total_suma_descuento
                acceder['descuento_iva'] = total_suma_descuento_iva
                acceder['descuento'] = sumas_descuento
                acceder['iva'] = iva_venta
                acceder['fp'] = inicial1
            elementos +=1

        for  metod_pago in metodos_pago:
            total_pagos += metodos_pago[metod_pago]['importe']

        listado_retiros = []
        retiros = self.env['quemen.retiros_efectivo'].search([('sesion_id', '=', docs.id)], order='fecha_hora asc')
        distint = 0
        for retiro in retiros:
            distint += 1
            listado_retiros.append({'n_retiro': retiro.name, 'distintivo': retiro.motivo, 'fecha_hora': retiro.fecha_hora, 'cantidad': retiro.total, 'cajero': retiro.cajero })
            total_retiro_efectivo += retiro.total

        total_retiros = 0
        for list_ret in listado_retiros:
            total_retiros += list_ret['cantidad']

        folios_concatenados = folios[0] + ' - ' + folios[-1]

        retiros_corte_previa = []
        retiros = self.env['quemen.retiros_efectivo'].search([('sesion_id', '!=', docs.id),('entregado','=', False),('tienda_id','=',docs.config_id.id)], order='fecha_hora asc')
        distint = 0
        for retiro in retiros:
            distint += 1
            retiros_corte_previa.append({'n_retiro': retiro.name, 'distintivo': retiro.motivo, 'fecha_hora': retiro.fecha_hora, 'cantidad': retiro.total, 'cajero': retiro.cajero })
            total_retiro_efectivo_sesion_previa += retiro.total

        total_retiros_noentregados = 0
        for list_ret in retiros_corte_previa:
            total_retiros_noentregados += list_ret['cantidad']
        folios_concatenados = folios[0] + ' - ' + folios[-1]


        for referencia1 in facturas:
            listado_referencia_facturas.append(referencia1.ref)

        facturas_rectificativa = self.env['account.move'].search([('move_type' , '=', 'out_refund'), ('invoice_origin', 'in', listado_referencia_facturas)])
        listado_notas_credito = []
        nota_credito = 0
        total_descuento_credito = 0
        descuento_credito = 0
        total_nota_credito = 0
        total_desglose_venta = 0
        suma_impuesto = 0
        suma_precio_sin_descuento = 0
        suma_precios_descuento = 0
        total_importe_credito = 0
        importe_descuento = 0
        for fac_rec in facturas_rectificativa:
            listado_notas_credito.append({'folio_credito': fac_rec.invoice_origin, 'total': fac_rec.amount_total})
            nota_credito += fac_rec.amount_total

            calculo_descuento = 0
            for lineas_credito in fac_rec.invoice_line_ids:
                lineas_descuento = lineas_credito.discount
                suma_impuesto += (lineas_credito.price_total - lineas_credito.price_subtotal)
                if lineas_descuento != False:
                    precio_descuento = lineas_credito.quantity * lineas_credito.price_unit
                    calculo_descuento = precio_descuento * (lineas_credito.discount / 100)
                    suma_precios_descuento += precio_descuento

                else:
                    precio_sin_descuento = lineas_credito.quantity * lineas_credito.price_unit
                    suma_precio_sin_descuento += precio_sin_descuento

            descuento_credito += calculo_descuento
            importe_descuento = (suma_precios_descuento + suma_precio_sin_descuento) + suma_impuesto

        total_nota_credito = round(nota_credito, 2)
        total_importe_credito = importe_descuento
        total_descuento_credito = descuento_credito
        total_desglose_venta = round(total_ventas_mostrador - total_nota_credito, 2)

        facturas_globales = self.env['account.move'].search([('pos_order_ids', 'in', pedidos_no_facturados)])
        factura_expedida = self.env['account.move'].search([('pos_order_ids', 'in', pedidos_facturados)])

        listado_facturas_expedidas=[]
        total_factura_expedida = 0
        iva_factura_expedida = 0
        suma_ventas_sin_iva = 0
        suma_ventas_iva = 0
        suma_columna_ventas_expedidas=0
        suma_columna_ventas_iva_expedidas=0
        suma_iva_expedido = 0
        suma_columna_iva_expedidas = 0
        suma_total_expedido = 0
        suma_columna_total_expedido = 0
        for fex in factura_expedida:
            total_factura_expedida = fex.amount_total
            producto_iva1 = 0
            producto_sin_iva1 = 0
            # folio_expedido = fex.ref
            # serie_expedido = fex.ref

            for lineas in fex.invoice_line_ids:
                if len(lineas.tax_ids) > 0:
                    for impuesto in lineas.tax_ids:
                        if 'IEPS' in impuesto.name:
                            producto_iva1 += lineas.price_subtotal
                        else:
                            producto_iva1 += lineas.price_subtotal
                else:
                    producto_sin_iva1 += lineas.price_subtotal

            #Codigo antes de IEPS
            #--------------------------------------------
            # for lineas in fex.invoice_line_ids:
            #     if lineas.tax_ids.id != False:
            #         producto_iva1 += lineas.price_subtotal
            #     else:
            #         producto_sin_iva1 += lineas.price_subtotal
            #--------------------------------------------

            suma_ventas_sin_iva += producto_sin_iva1
            suma_ventas_iva += producto_iva1
            iva_factura_expedida = round(fex.amount_total - fex.amount_untaxed, 2)
            suma_iva_expedido += round(iva_factura_expedida, 2)
            suma_total_expedido += round(total_factura_expedida, 2)
            listado_facturas_expedidas.append({
                # 'serie_expedido': serie_expedido,
                # 'folio_expedido': folio_expedido,
                'pedido': fex.ref,
                'producto_iva1': producto_iva1,
                'producto_sin_iva1': producto_sin_iva1,
                'iva_factura_expedida': iva_factura_expedida,
                'total_factura_expedida': total_factura_expedida,
            })

        suma_columna_ventas_expedidas = suma_ventas_sin_iva
        suma_columna_ventas_iva_expedidas = suma_ventas_iva
        suma_columna_iva_expedidas = round(suma_iva_expedido, 2)
        suma_columna_total_expedido = round(suma_total_expedido, 2)

        listado_facturas_globales = []
        total_factura_global = 0
        producto_iva = 0
        producto_sin_iva = 0
        iva_factura_global = 0
        for fg in facturas_globales:
            total_factura_global = fg.amount_total
            for lineas in fg.invoice_line_ids:
                if len(lineas.tax_ids) > 0:
                    for impuesto in lineas.tax_ids:
                        if 'IEPS' in impuesto.name:
                            producto_iva += lineas.price_subtotal
                        else:
                            producto_iva += lineas.price_subtotal
                else:
                    producto_sin_iva += lineas.price_subtotal
                #Codigo antes IEPS
                # if lineas.tax_ids.id != False:
                #     producto_iva += lineas.price_subtotal
                # else:
                #     producto_sin_iva += lineas.price_subtotal


            iva_factura_global = round(fg.amount_total - fg.amount_untaxed, 2)

        listado_facturas_globales.append({
        'producto_sin_iva': producto_sin_iva,
        'producto_iva': producto_iva,
        'iva_factura_global': iva_factura_global,
        'total': total_factura_global})

        suma_columna_total_facturas_totales = 0
        suma_columna_total_facturas_totales = suma_columna_total_expedido + total_factura_global

        listado_pedidos = self.env['pos.order'].search([('session_id','=', docs.id),('amount_total', '<', 0 )])

        listado_cancelados = []
        folios1= []
        serie1 = []

        for list_pedidos in listado_pedidos:
            if len(list_pedidos.refunded_order_ids) > 0:
                listado_cancelados.append({'venta': list_pedidos.name,'importe': list_pedidos.refunded_order_ids.amount_total})


        total_cancelado = 0
        for lst_cancelados in listado_cancelados:
            total_cancelado += lst_cancelados['importe']

        listado_totales.append({
            'total_columnas_ventas_sin_iva': totales_ventas_sesion['ventas_sin_iva'],
            'total_columnas_descuento_sin_iva': totales_ventas_sesion['descuento_sin_iva'],
            'total_columnas_ventas_iva': totales_ventas_sesion['ventas_iva'],
            'total_columnas_descuento_iva': totales_ventas_sesion['descuento_iva'],
            'total_columna_descuento': (
                totales_ventas_sesion['descuento_sin_iva'] +
                totales_ventas_sesion['descuento_iva'] +
                totales_ventas_sesion['descuento_ieps8']
            ),
            'total_columna_iva': totales_ventas_sesion['iva'],
            'total_columna_total': totales_ventas_sesion['total'],
            'importe': (
                totales_ventas_sesion['ventas_sin_iva'] +
                totales_ventas_sesion['ventas_iva'] +
                totales_ventas_sesion['ieps8'] +
                totales_ventas_sesion['iva']
            ),
            'total_ventas_mostrador': totales_ventas_sesion['total'],
            'folios_concatenados': folios_concatenados,
            'total_nota_credito': total_nota_credito,
            'total_descuento_credito': total_descuento_credito,
            'total_importe_credito': total_importe_credito,
            'total_desglose_venta': round(totales_ventas_sesion['total'] - total_nota_credito, 2),
            'suma_columna_ventas_expedidas': suma_columna_ventas_expedidas,
            'suma_columna_ventas_iva_expedidas': suma_columna_ventas_iva_expedidas,
            'suma_columna_iva_expedidas': suma_iva_expedido,
            'suma_columna_total_expedido': suma_total_expedido,
            'suma_columna_total_facturas_totales': suma_columna_total_expedido + total_factura_global,
            'contador_efectivo': contador_efectivo,
            'total_pago': total_pagos,
            'total_retiros': total_retiros,
            'total_cancelado': total_cancelado,
            'total_columnas_ieps8': totales_ventas_sesion['ieps8'],
            'total_columnas_descuento_ieps8': totales_ventas_sesion['descuento_ieps8'],
            'total_columnas_ieps8_neto': (
                totales_ventas_sesion['ieps8'] -
                totales_ventas_sesion['descuento_ieps8']
            ),
        })

        total_ventas_mostrador = totales_ventas_sesion['total']
        total_facturas_expedidas = resumen_facturas_expedidas['total'] + resumen_factura_global['total']

        diferencia = apertura_efectivo + total_retiro_efectivo - venta_efectivo - cierre_efectivo
        ventas_mostrador['importe'] = totales_ventas_sesion['total'] - totales_ventas_sesion['descuento']
        ventas_mostrador['descuento'] = totales_ventas_sesion['descuento']
        ventas_mostrador['total'] = totales_ventas_sesion['total']
        return {
        'listado_productos': listado_productos,
        'listado_totales': listado_totales,
        'listado_notas_credito': listado_notas_credito,
        'listado_facturas_expedidas': listado_facturas_expedidas,
        'listado_facturas_globales': listado_facturas_globales,
        'metodos_pago': metodos_pago,
        'listado_retiros': listado_retiros,
        'listado_cancelados': listado_cancelados,
        'ventas_mostrador': ventas_mostrador,
        'total_ventas_mostrador': total_ventas_mostrador,
        'ventas_sesion': ventas_sesion,
        'totales_ventas_sesion': totales_ventas_sesion,
        'folios_concatenados': folios_concatenados,
        'resumen_facturas_expedidas': resumen_facturas_expedidas,
        'resumen_factura_global': resumen_factura_global,
        'total_facturas_expedidas': total_facturas_expedidas,
        'detalle_facturas_expedidas': detalle_facturas_expedidas,
        'total_detalle_facturas_expedidas': total_detalle_facturas_expedidas,
        'diferencia': diferencia,
        'retiros_corte_previa': retiros_corte_previa,
        }


    @api.model
    def _get_report_values(self, docids, data=None):
        docs = self.env['pos.session'].browse(docids)
        timezone = pytz.timezone(self._context.get('tz') or self.env.user.tz or 'UTC')
        fecha_hoy = datetime.now().astimezone(timezone).strftime('%H')
        estado_sesion = False
        for sesion in docs:
            estado_sesion = sesion.state
        if int(fecha_hoy) >= 13 and estado_sesion != "closed":
            raise ValidationError("No tiene permitido generar corte de caja, favor de cerrar sesión")
        return {
            'doc_ids': docids,
            'doc_model': 'pos.session',
            'docs': docs,
            'sesiones': self.sesiones
        }
