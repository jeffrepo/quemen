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

            # -------------------------------
            # ABONOS: producto terminado
            # -------------------------------
            abono_lines = []
            total_abono = 0.0

            finished_moves = production.move_finished_ids.filtered(lambda m: m.state == 'done')

            for move in finished_moves:
                qty = self._get_qty(move)
                if not qty:
                    continue

                cost = move.product_id.standard_price or 0.0
                amount = qty * cost
                if not amount:
                    continue

                dest_location = move.location_dest_id

                if self.location_ids and dest_location not in self.location_ids:
                    continue

                account = dest_location.account_id

                abono_lines.append({
                    'cuenta': account.code if account else '',
                    'nombre': move.product_id.display_name or '',
                    'cargo': 0.0,
                    'abono': amount,
                    'referencia': production.name or '',
                    'concepto': concepto,
                })
                total_abono += amount

            if not abono_lines:
                continue

            # -------------------------------
            # CARGO: una sola línea = suma de abonos
            # toma cuenta/nombre del primer componente
            # -------------------------------
            cargo_account = ''
            cargo_name = production.product_id.display_name or ''

            raw_moves = production.move_raw_ids.filtered(lambda m: m.state == 'done')
            first_raw_move = False

            for move in raw_moves:
                qty = self._get_qty(move)
                if not qty:
                    continue

                source_location = move.location_id
                dest_location = move.location_dest_id

                if self.location_ids and source_location not in self.location_ids and dest_location not in self.location_ids:
                    continue

                first_raw_move = move
                break

            if first_raw_move:
                source_location = first_raw_move.location_id
                account = source_location.account_id
                cargo_account = account.code if account else ''
                cargo_name = first_raw_move.product_id.display_name or cargo_name

            # Línea de cargo primero
            sheet.write(row, 0, cargo_account)
            sheet.write(row, 1, cargo_name)
            sheet.write(row, 2, '')
            sheet.write(row, 3, '')
            sheet.write_number(row, 4, total_abono, fmt_amount)
            sheet.write_number(row, 5, 0.0, fmt_amount)
            sheet.write(row, 6, production.name or '')
            sheet.write(row, 7, concepto)
            sheet.write(row, 8, '')
            sheet.write(row, 9, '')

            row += 1
            found_lines += 1

            # Luego los abonos
            for line in abono_lines:
                sheet.write(row, 0, line['cuenta'])
                sheet.write(row, 1, line['nombre'])
                sheet.write(row, 2, '')
                sheet.write(row, 3, '')
                sheet.write_number(row, 4, line['cargo'], fmt_amount)
                sheet.write_number(row, 5, line['abono'], fmt_amount)
                sheet.write(row, 6, line['referencia'])
                sheet.write(row, 7, line['concepto'])
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

        if not qty and hasattr(move, 'move_line_ids'):
            qty = sum(move.move_line_ids.mapped('quantity')) if 'quantity' in move.move_line_ids._fields else 0.0
            if not qty and 'qty_done' in move.move_line_ids._fields:
                qty = sum(move.move_line_ids.mapped('qty_done'))

        return abs(qty)
