# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import json
import datetime
import math
import re
import warnings

from collections import defaultdict
from dateutil.relativedelta import relativedelta

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
from odoo.tools import float_compare, float_round, float_is_zero, format_datetime
from odoo.tools.misc import OrderedSet, format_date, groupby as tools_groupby

from odoo.addons.stock.models.stock_move import PROCUREMENT_PRIORITIES
import logging
SIZE_BACK_ORDER_NUMERING = 3

class MrpProduction(models.Model):
    """ Manufacturing Orders """
    _inherit = 'mrp.production'

    x_studio_etapa = fields.Integer(
        string='Etapa',
        index=True,
        group_expand='_read_group_x_studio_etapa',
    )

    # lot_id = fields.Many2one('quemen.op_lote','Lote')

    @api.model
    def _read_group_x_studio_etapa(self, stages, domain, order):
        """Keep the usual stages visible even when a column has no orders."""
        return sorted(set(stages or []) | set(range(5)))

    def action_update_product_qty(self, product_qty):
        """Safely change an MO quantity from the Quemen kanban view."""
        self.ensure_one()
        if self.state in ('done', 'cancel'):
            raise UserError(_('No puede cambiar la cantidad de una orden cerrada o cancelada.'))

        try:
            product_qty = float(product_qty)
        except (TypeError, ValueError):
            raise UserError(_('Ingrese una cantidad válida.'))

        rounding = self.product_uom_id.rounding
        if not math.isfinite(product_qty) or float_compare(
                product_qty, 0.0, precision_rounding=rounding) <= 0:
            raise UserError(_('La cantidad a producir debe ser mayor que cero.'))
        if float_compare(
                product_qty, self.qty_produced, precision_rounding=rounding) < 0:
            raise UserError(_(
                'La cantidad a producir no puede ser menor que la cantidad ya producida.'
            ))

        if float_compare(
                product_qty, self.product_qty, precision_rounding=rounding) == 0:
            return True
        if float_compare(
                self.product_qty, self.qty_produced, precision_rounding=rounding) <= 0:
            raise UserError(_(
                'No puede cambiar la cantidad desde esta vista porque la orden ya fue '
                'producida completamente.'
            ))

        self.env['change.production.qty'].create({
            'mo_id': self.id,
            'product_qty': product_qty,
        }).change_prod_qty()
        return True

    def action_confirm_and_close(self, product_qty=None):
        """Apply the card quantity, confirm the MO and close it in one step."""
        self.ensure_one()
        if self.state == 'cancel':
            raise UserError(_('No puede confirmar una orden de producción cancelada.'))
        if self.state == 'done':
            return True

        if product_qty is not None:
            self.action_update_product_qty(product_qty)

        if self.state == 'draft':
            self.action_confirm()

        remaining_qty = self.product_qty - self.qty_produced
        if self.product_tracking == 'serial' and float_compare(
                remaining_qty, 1.0,
                precision_rounding=self.product_uom_id.rounding) > 0:
            raise UserError(_(
                'Las órdenes con seguimiento por número de serie y cantidad mayor que uno '
                'deben cerrarse desde el formulario estándar.'
            ))
        if self.product_tracking in ('lot', 'serial') and not self.lot_producing_id:
            raise UserError(_(
                'Debe asignar un lote o número de serie al producto terminado antes de cerrar la orden.'
            ))

        self.qty_producing = self.product_qty
        self._set_qty_producing()
        return self.with_context(
            skip_immediate=True,
            skip_consumption=True,
            skip_backorder=True,
        ).button_mark_done()

    @api.onchange('bom_id', 'product_id', 'product_qty', 'product_uom_id', 'move_raw_ids')
    def _onchange_move_raw(self):
        res = super(MrpProduction, self)._onchange_move_raw()
        for line in self.move_raw_ids:
            if len(line.product_id.bom_ids) > 0:
                if line.product_id.bom_ids[0].picking_type_id:
                    line.location_id = line.product_id.bom_ids[0].picking_type_id.default_location_dest_id.id

    def _get_move_raw_values(self, product_id, product_uom_qty, product_uom, operation_id=False, bom_line=False):
        res = super(MrpProduction, self)._get_move_raw_values(product_id, product_uom_qty, product_uom, operation_id, bom_line)
        if res:
            if ('location_id' and 'product_id') in res and (bom_line and bom_line.location_src_id):
                res['location_id'] = bom_line.location_src_id.id if (bom_line and bom_line.location_src_id) else False,
        return res

    def elminar_lineas_duplicadas(self):
        listas = self.env['mrp.bom'].search([('active','=',True)])
        listas_guardadas = []
        listas_eliminadas = []
        for l in listas:
            listas_guardadas.append(l)
        lineas_eliminar = []
        if listas_guardadas:
            for lista in listas_guardadas:
                if len(lista.bom_line_ids) > 0:
                    bom_line = lista.bom_line_ids
                    for linea in bom_line:
                        if linea.id not in listas_eliminadas:
                            producto = linea.product_id.id
                            linea_id = linea.id
                            linea_eliminar = self.env['mrp.bom.line'].search([('id','!=', linea.id),('product_id','=', linea.product_id.id),('bom_id','=', linea.bom_id.id)])
                            if len(linea_eliminar) > 0:
                                for l in linea_eliminar:
                                    listas_eliminadas.append(l.id)
                                    l.unlink()
