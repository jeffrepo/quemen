from odoo import api, models, _
from odoo.exceptions import UserError, ValidationError
from datetime import datetime
import pytz
import ast
import logging

class ReporteCorteCajaCarta(models.AbstractModel):
    _name = 'report.quemen.reporte_corte_caja_carta'

    nombre_reporte=''

    def datos_factura(self, docs):
        pedidos_facturar =[]
        pagos = {}
        ids_pedidos = []
        lineas_facturar = []
        factura_id = False
        lineas_facturar_dic = {}
        pendiente_facturar = 0
        for sesion in docs:
            if len(sesion.order_ids) > 0:
                for pedido in sesion.order_ids:
                    if pedido.state in ['done', 'paid','invoiced'] and pedido.amount_total > 0 and (pedido.is_refunded==False):
                        pedidos_facturar.append(pedido)
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
                impuesto_programa_ieps8 = False
                total_descuento_16 = 0
                pedido_impuesto = pedido.amount_tax
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
                            linea_0 = linea.tax_ids_after_fiscal_position.filtered(lambda t: t.name == "IVA(0%) VENTAS")
                            linea_16 = linea.tax_ids_after_fiscal_position.filtered(lambda t: t.name == "IVA(16%) VENTAS")

                            # Si la promoción tiene IEPS y este producto aplica IEPS, añadirlo.
                            if impuesto_programa_ieps8 and any('IEPS' in t.name for t in linea.product_id.taxes_id):
                                tax_ids = [(6, 0, linea.product_id.taxes_id.ids)]
                            else:
                                # Usar los impuestos reales de la línea
                                tax_ids = [(6, 0, linea.tax_ids_after_fiscal_position.ids)]
                            # linea_0 = True if linea.tax_ids_after_fiscal_position[0].name == "IVA(0%) VENTAS" else False
                            # linea_16 = True if linea.tax_ids_after_fiscal_position[0].name == "IVA(16%) VENTAS" else False
                            # tax_ids = [1,12] if linea_0 and impuesto_programa_ieps8 else False
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
        logging.warning("lineas_facturar_dic")
        logging.warning(lineas_facturar_dic)
        return lineas_facturar_dic

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

        #SOLO OBTENEMOS INFORMACION DE PEDIDOS FACTURADOS
                    # ventas_sesion[venta_nombre] = {'venta': venta_nombre,'ventas_sin_iva': 0, 'descuento_sin_iva': 0, 'ventas_iva': 0, 'descuento_iva': 0, 'ieps8': 0, 'descuento_ieps8':0 ,'descuento': 0, 'iva': 0, 'total': 0, 'fp': fp, 'e':0}
        lineas_facturar_dic = self.datos_factura(docs)

        ventas_sesion = {}
        totales_ventas_sesion = {
            'ventas_sin_iva': 0, 'descuento_sin_iva': 0,
            'ventas_iva': 0, 'descuento_iva': 0,
            'ieps8': 0, 'descuento_ieps8': 0,
            'descuento': 0, 'iva': 0, 'total': 0
        }
        currency = docs.currency_id or self.env.company.currency_id

        for llave, linea in lineas_facturar_dic.items():
            ticket_ref = linea['name']   # referencia al pedido/ticket

            # --- normalizar tax_ids ---
            tax_ids = []
            logging.warning('Linea taxids')
            logging.warning(linea['tax_ids'])
            if linea['tax_ids']:
                if isinstance(linea['tax_ids'], (list, tuple)):
                    if isinstance(linea['tax_ids'][0], (list, tuple)):
                        tax_ids = linea['tax_ids'][0][2]  # [(6, 0, [ids])]
                    else:
                        tax_ids = linea['tax_ids']        # lista simple de ints
                else:
                    tax_ids = [linea['tax_ids']]          # int único

            taxes = self.env['account.tax'].browse(tax_ids) if tax_ids else False

            # --- precio unitario con descuento aplicado ---
            discount = linea.get('discount', 0.0) or 0.0
            price_unit_desc = linea['price_unit'] * (1 - (linea.get('discount', 0.0) or 0.0) / 100.0)


            # --- compute_all con precio con descuento ---
            taxes_res = taxes.compute_all(
                price_unit_desc,
                currency,
                linea['quantity'],
                product=self.env['product.product'].browse(linea['product_id']),
                partner=False,
            ) if taxes else {'total_excluded': 0, 'total_included': 0, 'taxes': []}

            ventas_sin_iva = sum(t['base'] for t in taxes_res['taxes'] if '0%' in t['name'])
            ventas_iva = sum(t['base'] for t in taxes_res['taxes'] if '16%' in t['name'])
            ieps8 = sum(t['amount'] for t in taxes_res['taxes'] if 'IEPS' in t['name'])
            iva = sum(t['amount'] for t in taxes_res['taxes'] if 'IVA' in t['name'])
            total = taxes_res['total_included']

            # --- crear la estructura del ticket si no existe ---


            # --- calcular descuentos manuales ---
            descuento_total = (linea['price_unit'] * linea['quantity']) - (price_unit_desc * linea['quantity'])

            # Inicializamos columnas
            ventas_sin_iva = 0.0
            ventas_iva = 0.0
            ieps8 = 0.0
            iva = 0.0
            descuento_sin_iva = 0.0
            descuento_iva = 0.0
            descuento_ieps8 = 0.0
            subtotal_neto = taxes_res['total_excluded']
            total = taxes_res['total_included']
            # Detectar si hay IEPS en la línea
            tiene_ieps = any('IEPS' in t['name'] for t in taxes_res['taxes'])

            # --- normalizar tax_ids de la línea (diccionario proveniente de datos_factura) ---
            tax_ids = []
            if linea.get('tax_ids'):
                if isinstance(linea['tax_ids'], (list, tuple)):
                    if linea['tax_ids'] and isinstance(linea['tax_ids'][0], (list, tuple)):
                        # formato Odoo M2M: [(6, 0, [ids])]
                        tax_ids = linea['tax_ids'][0][2]
                    else:
                        # lista simple de ids
                        tax_ids = list(linea['tax_ids'])
                else:
                    # id único
                    tax_ids = [linea['tax_ids']]

            taxes = self.env['account.tax'].browse(tax_ids) if tax_ids else False

            # --- precio con descuento aplicado ---
            discount = linea.get('discount', 0.0) or 0.0
            price_unit = linea['price_unit']
            qty = linea['quantity']
            price_unit_desc = price_unit * (1 - discount / 100.0)

            product = self.env['product.product'].browse(linea['product_id'])
            logging.warning("producto")
            logging.warning(product)
            logging.warning(product.name)
            def _compute(price_unit_):
                if not taxes:
                    return {
                        'total_excluded': price_unit_ * qty,
                        'total_included': price_unit_ * qty,
                        'taxes': []
                    }
                return taxes.compute_all(
                    price_unit_,
                    currency,
                    qty,
                    product=product,
                    partner=False,
                )

            # --- calcular ANTES y DESPUÉS del descuento ---
            res_before = _compute(price_unit)        # antes de descuento
            logging.warning('res_before: ' + str(res_before) )
            res_after  = _compute(price_unit_desc)   # después de descuento
            logging.warning('res_after: ' + str(res_after) )


            # --- extraer componentes por impuesto ---
            def _split(res):
                base0 = sum(t['base']   for t in res['taxes'] if '0%'   in t['name'])
                base16= sum(t['base']   for t in res['taxes'] if '16%'  in t['name'])
                iva   = sum(t['amount'] for t in res['taxes'] if 'IVA'  in t['name'])
                ieps  = sum(t['amount'] for t in res['taxes'] if 'IEPS' in t['name'])
                return base0, base16, iva, ieps, res['total_excluded'], res['total_included']

            b0_before, b16_before, iva_before, ieps_before, _, tot_inc_before = _split(res_before)
            b0_after,  b16_after,  iva_after,  ieps_after,  _, tot_inc_after  = _split(res_after)


            # --- VENTAS (valores netos después del descuento) ---
            ventas_sin_iva = b0_after
            ventas_iva     = b16_after
            ieps8          = ieps_after
            iva            = iva_after
            total          = tot_inc_after


            # --- Descuentos manuales (según Excel) ---
            descuento_base0  = b0_before - b0_after
            descuento_base16 = b16_before - b16_after

            descuento_sin_iva = 0.0
            descuento_iva     = 0.0
            descuento_ieps8   = 0.0

            tiene_ieps = any('IEPS' in t['name'] for t in res_before['taxes'])
            logging.warning("tiene IEPS")
            logging.warning(ticket_ref)
            logging.warning(res_before)
            logging.warning(tiene_ieps)
            if ticket_ref not in ventas_sesion:
                ventas_sesion[ticket_ref] = {
                    'venta': ticket_ref,
                    'ventas_sin_iva': 0, 'descuento_sin_iva': 0,
                    'ventas_iva': 0, 'descuento_iva': 0,
                    'ieps8': 0, 'descuento_ieps8': 0,
                    'descuento': 0, 'iva': 0, 'total': 0,
                    'fp': 'M', 'e': 0
                }


            # Caso: 0% + IEPS
            # if descuento_base0 > 0 and tiene_ieps:
            #     descuento_sin_iva = descuento_base0
            #     descuento_ieps8   = descuento_base0 * 0.08
            #
            # # Caso: 16% + IEPS
            # elif descuento_base16 > 0 and tiene_ieps:
            #     descuento_sin_iva = 0.0
            #     descuento_base = descuento_base16
            #     descuento_ieps8 = descuento_base * 0.08
            #     descuento_iva   = (descuento_base + descuento_ieps8) * 0.16
            #
            # # Caso: solo 16%
            # elif descuento_base16 > 0 and not tiene_ieps:
            #     descuento_iva = descuento_base16 * 0.16
            #
            # # Caso: solo 0%
            # elif descuento_base0 > 0 and not tiene_ieps:
            #     descuento_sin_iva = descuento_base0
            #
            # # Total descuento
            # descuento_total = descuento_sin_iva + descuento_iva + descuento_ieps8

            # Descuentos reales calculados con compute_all()
            # res_before = impuestos antes del descuento
            # res_after  = impuestos después del descuento

            descuento_sin_iva = max(b0_before - b0_after, 0.0)

            # Esta variable representa la BASE gravada 16% descontada.
            # Se usa para la columna "Desct 16%".
            descuento_base16 = max(b16_before - b16_after, 0.0)

            # Estos son impuestos descontados reales.
            # Se usan para cuadrar contra factura.
            descuento_ieps8 = max(ieps_before - ieps_after, 0.0)
            descuento_iva_impuesto = max(iva_before - iva_after, 0.0)

            # Total descuento fiscal completo:
            # base 0% + base 16% + IEPS descontado + IVA descontado
            descuento_total = (
                descuento_sin_iva +
                descuento_base16 +
                descuento_ieps8 +
                descuento_iva_impuesto
            )

            # Guardar descuentos en el diccionario del ticket
            # ventas_sesion[ticket_ref]['descuento_sin_iva'] += descuento_sin_iva
            # ventas_sesion[ticket_ref]['descuento_iva'] += descuento_iva
            # ventas_sesion[ticket_ref]['descuento_ieps8'] += descuento_ieps8
            # ventas_sesion[ticket_ref]['descuento'] += (descuento_sin_iva + descuento_iva + descuento_ieps8)
            ventas_sesion[ticket_ref]['descuento_sin_iva'] += descuento_sin_iva
            ventas_sesion[ticket_ref]['descuento_iva'] += descuento_base16
            ventas_sesion[ticket_ref]['descuento_ieps8'] += descuento_ieps8
            ventas_sesion[ticket_ref]['descuento'] += descuento_total
            # --- acumular en el ticket ---
            ventas_sesion[ticket_ref]['ventas_sin_iva'] += ventas_sin_iva
            ventas_sesion[ticket_ref]['ventas_iva'] += ventas_iva
            ventas_sesion[ticket_ref]['ieps8'] += ieps8
            ventas_sesion[ticket_ref]['iva'] += iva
            ventas_sesion[ticket_ref]['total'] += total

            # También acumular en los totales generales
            # totales_ventas_sesion['descuento_sin_iva'] += descuento_sin_iva
            # totales_ventas_sesion['descuento_iva'] += descuento_iva
            # totales_ventas_sesion['descuento_ieps8'] += descuento_ieps8
            # totales_ventas_sesion['descuento'] += (descuento_sin_iva + descuento_iva + descuento_ieps8)
            totales_ventas_sesion['descuento_sin_iva'] += descuento_sin_iva
            totales_ventas_sesion['descuento_iva'] += descuento_base16
            totales_ventas_sesion['descuento_ieps8'] += descuento_ieps8
            totales_ventas_sesion['descuento'] += descuento_total
            
            # --- acumular en los totales generales ---
            totales_ventas_sesion['ventas_sin_iva'] += ventas_sin_iva
            totales_ventas_sesion['ventas_iva'] += ventas_iva
            totales_ventas_sesion['ieps8'] += ieps8
            totales_ventas_sesion['iva'] += iva
            totales_ventas_sesion['total'] += total


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
                'total_cancelado': total_cancelado
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
