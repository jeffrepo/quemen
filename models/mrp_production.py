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
        default=0,
        index=True,
    )
    quemen_etapa_kanban = fields.Char(
        string='Etapa',
        compute='_compute_quemen_etapa_kanban',
        inverse='_inverse_quemen_etapa_kanban',
        store=True,
        index=True,
        group_expand='_read_group_quemen_etapa_kanban',
    )

    # lot_id = fields.Many2one('quemen.op_lote','Lote')

    @api.depends('x_studio_etapa')
    def _compute_quemen_etapa_kanban(self):
        for production in self:
            production.quemen_etapa_kanban = str(production.x_studio_etapa or 0)

    def _inverse_quemen_etapa_kanban(self):
        for production in self:
            try:
                production.x_studio_etapa = int(production.quemen_etapa_kanban or 0)
            except (TypeError, ValueError):
                raise UserError(_('La etapa debe ser un número entero.'))

    @api.model
    def _read_group_quemen_etapa_kanban(self, stages, domain, order):
        """Expose numeric stages as text so that zero is not rendered as false."""
        stage_values = {str(stage) for stage in stages if stage not in (False, None, '')}
        stage_values.update(str(stage) for stage in range(5))

        def stage_sort_key(value):
            try:
                return 0, int(value)
            except (TypeError, ValueError):
                return 1, value

        return sorted(stage_values, key=stage_sort_key)

    def action_update_product_qty(self, product_qty):
        """Change the MO quantity without changing its existing components."""
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

        quantity_wizard = self.env['change.production.qty'].create({
            'mo_id': self.id,
            'product_qty': product_qty,
        })

        old_product_qty = self.product_qty
        done_moves = self.move_finished_ids.filtered(
            lambda move: move.state == 'done' and move.product_id == self.product_id
        )
        qty_produced = self.product_id.uom_id._compute_quantity(
            sum(done_moves.mapped('product_qty')),
            self.product_uom_id,
        )

        # Update finished products and by-products as Odoo's standard quantity
        # wizard does, but deliberately leave raw moves untouched. Their
        # ``unit_factor`` is recomputed from the new remaining production
        # quantity, so closing the MO consumes the component demand that was
        # already planned instead of scaling it with ``product_qty``.
        finished_moves_modification = quantity_wizard._update_finished_moves(
            self,
            product_qty - qty_produced,
            old_product_qty - qty_produced,
        )
        if finished_moves_modification:
            self._log_downside_manufactured_quantity(finished_moves_modification)

        self.write({'product_qty': product_qty})
        for workorder in self.workorder_ids:
            workorder.duration_expected = workorder._get_duration_expected(
                ratio=product_qty / old_product_qty
            )
            quantity = workorder.qty_production - workorder.qty_produced
            if self.product_tracking == 'serial':
                quantity = 1.0 if not float_is_zero(
                    quantity, precision_rounding=rounding) else 0.0
            else:
                quantity = quantity if quantity > 0 and not float_is_zero(
                    quantity, precision_rounding=rounding) else 0.0
            workorder._update_qty_producing(quantity)
            if workorder.qty_produced < workorder.qty_production and workorder.state == 'done':
                workorder.state = 'progress'
            if workorder.qty_produced == workorder.qty_production and workorder.state == 'progress':
                workorder.state = 'done'
                if workorder.next_work_order_id.state == 'pending':
                    workorder.next_work_order_id.state = 'ready'
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
