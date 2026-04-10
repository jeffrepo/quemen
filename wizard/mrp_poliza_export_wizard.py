import base64
import io

from odoo import fields, models, _
from odoo.exceptions import UserError

import xlsxwriter


class MrpPolizaExportWizard(models.TransientModel):
    _name = 'mrp.poliza.export.wizard'
    _description = 'Exportar póliza de fabricación'

    location_ids = fields.Many2many('stock.location', string='Ubicaciones')
    date_start = fields.Date(string='Fecha inicio', required=True)
    date_end = fields.Date(string='Fecha fin', required=True)
    file_data = fields.Binary(string='Archivo', readonly=True)
    file_name = fields.Char(string='Nombre archivo', readonly=True)

    def action_export_xlsx(self):
        self.ensure_one()
    
        if self.date_start > self.date_end:
            raise UserError(_('La fecha inicio no puede ser mayor que la fecha fin.'))
    
        start_dt = fields.Datetime.to_datetime(str(self.date_start) + ' 00:00:00')
        end_dt = fields.Datetime.to_datetime(str(self.date_end) + ' 23:59:59')
    
        productions = self.env['mrp.production'].search([
            ('state', '=', 'done'),
            ('date_finished', '>=', start_dt),
            ('date_finished', '<=', end_dt),
        ], order='date_finished, name')
    
        if not productions:
            raise UserError(_('No se encontraron órdenes de fabricación terminadas en el rango seleccionado.'))
    
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        sheet = workbook.add_worksheet('Poliza')
    
        fmt_header = workbook.add_format({'bold': True, 'bg_color': '#D9E1F2', 'border': 1})
        fmt_amount = workbook.add_format({'num_format': '#,##0.00'})
    
        headers = [
            'Cuenta', 'Nombre', 'Cargo M.E.', 'Abono M.E.',
            'Cargo', 'Abono', 'Referencia', 'Concepto', 'Diario', 'Seg. Neg.'
        ]
    
        for col, header in enumerate(headers):
            sheet.write(0, col, header, fmt_header)
    
        row = 1
        found_lines = 0
    
        for production in productions:
            concepto = production.picking_type_id.name or 'Fabricación'
    
            for move in production.move_raw_ids.filtered(lambda m: m.state == 'done'):
                qty = self._get_qty(move)
                cost = move.product_id.standard_price or 0.0
                amount = qty * cost
    
                source_location = move.location_id
                account = source_location.account_id
    
                sheet.write(row, 0, account.code if account else '')
                sheet.write(row, 1, move.product_id.display_name or '')
                sheet.write(row, 2, '')
                sheet.write(row, 3, '')
                sheet.write_number(row, 4, amount, fmt_amount)
                sheet.write_number(row, 5, 0.0, fmt_amount)
                sheet.write(row, 6, production.name or '')
                sheet.write(row, 7, concepto)
                sheet.write(row, 8, '')
                sheet.write(row, 9, '')
    
                row += 1
                found_lines += 1
    
            for move in production.move_finished_ids.filtered(lambda m: m.state == 'done'):
                qty = self._get_qty(move)
                cost = move.product_id.standard_price or 0.0
                amount = qty * cost
    
                dest_location = move.location_dest_id
                account = dest_location.account_id
    
                sheet.write(row, 0, account.code if account else '')
                sheet.write(row, 1, move.product_id.display_name or '')
                sheet.write(row, 2, '')
                sheet.write(row, 3, '')
                sheet.write_number(row, 4, 0.0, fmt_amount)
                sheet.write_number(row, 5, amount, fmt_amount)
                sheet.write(row, 6, production.name or '')
                sheet.write(row, 7, concepto)
                sheet.write(row, 8, '')
                sheet.write(row, 9, '')
    
                row += 1
                found_lines += 1
    
        if not found_lines:
            raise UserError(_('Se encontraron OF terminadas, pero no se generó ninguna línea.'))
    
        workbook.close()
        output.seek(0)
    
        self.write({
            'file_data': base64.b64encode(output.read()),
            'file_name': 'poliza_fabricacion_prueba.xlsx',
        })
    
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'mrp.poliza.export.wizard',
            'view_mode': 'form',
            'res_id': self.id,
            'target': 'new',
        }

    def _get_qty(self, move):
        qty = 0.0

        if hasattr(move, 'quantity'):
            qty = move.quantity or 0.0
        if not qty and hasattr(move, 'quantity_done'):
            qty = move.quantity_done or 0.0
        if not qty and hasattr(move, 'product_uom_qty'):
            qty = move.product_uom_qty or 0.0

        # fallback por líneas de movimiento
        if not qty and hasattr(move, 'move_line_ids'):
            qty = sum(move.move_line_ids.mapped('quantity')) if 'quantity' in move.move_line_ids._fields else 0.0
            if not qty and 'qty_done' in move.move_line_ids._fields:
                qty = sum(move.move_line_ids.mapped('qty_done'))

        return abs(qty)