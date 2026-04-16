# -*- coding: utf-8 -*-
import base64
import io
from datetime import datetime, time

from odoo import api, fields, models, _
from odoo.exceptions import UserError
import logging

class InventoryXlsxWizard(models.TransientModel):
    _name = "quemen.inventory.xlsx.wizard"
    _description = "Wizard Reporte Inventario XLSX"

    warehouse_id = fields.Many2one(
        "stock.warehouse",
        string="Almacén",
        required=True,
    )
    date_start = fields.Date(
        string="Fecha inicio",
        required=True,
    )
    date_end = fields.Date(
        string="Fecha fin",
        required=True,
    )
    file_data = fields.Binary(string="Archivo", readonly=True)
    file_name = fields.Char(string="Nombre archivo", readonly=True)

    def action_generate_xlsx(self):
        self.ensure_one()

        if self.date_start > self.date_end:
            raise UserError(_("La fecha inicio no puede ser mayor a la fecha fin."))

        data_lines = self._get_report_lines()

        output = io.BytesIO()
        workbook = self._build_workbook(output, data_lines)
        workbook.close()
        output.seek(0)

        filename = "inventario_%s_%s_%s.xlsx" % (
            self.warehouse_id.code or self.warehouse_id.name.replace(" ", "_"),
            self.date_start.strftime("%Y%m%d"),
            self.date_end.strftime("%Y%m%d"),
        )

        self.write({
            "file_data": base64.b64encode(output.read()),
            "file_name": filename,
        })

        return {
            "type": "ir.actions.act_url",
            "url": "/web/content/?model=%s&id=%s&field=file_data&filename_field=file_name&download=true" % (
                self._name, self.id
            ),
            "target": "self",
        }

    def _get_locations_domain(self):
        self.ensure_one()
        warehouse = self.warehouse_id
        return self.env["stock.location"].search([
            ("id", "child_of", warehouse.view_location_id.id),
        ]).ids

    def _get_report_lines(self):
        self.ensure_one()

        Product = self.env["product.product"]
        Move = self.env["stock.move"]

        location_ids = self._get_locations_domain()

        dt_start = datetime.combine(self.date_start, time.min)
        dt_end = datetime.combine(self.date_end, time.max)

        internal_locations = self.env["stock.location"].search([
            ("id", "in", location_ids),
            ("usage", "=", "internal"),
        ])
        internal_location_ids = internal_locations.ids

        Product = self.env["product.product"]

        # Detectar campo según versión
        if "is_storable" in Product._fields:
            domain = [("is_storable", "=", True)]
        else:
            domain = [("type", "=", "product")]

        products = Product.search(
            domain,
            order="default_code, name"
        )
        lines = []
        logging.warning("Productos")
        logging.warning(products)
        for product in products:
            # Movimientos antes del periodo para calcular saldo inicial
            moves_before_in = Move.search([
                ("product_id", "=", product.id),
                ("state", "=", "done"),
                ("date", "<", fields.Datetime.to_string(dt_start)),
                ("location_dest_id", "in", internal_location_ids),
                ("location_id", "not in", internal_location_ids),
            ])
            logging.warning("moves_before_in")
            logging.warning(moves_before_in)
            moves_before_out = Move.search([
                ("product_id", "=", product.id),
                ("state", "=", "done"),
                ("date", "<", fields.Datetime.to_string(dt_start)),
                ("location_id", "in", internal_location_ids),
                ("location_dest_id", "not in", internal_location_ids),
            ])
            logging.warning("moves_before_out")
            logging.warning(moves_before_out)
            opening_qty = sum(moves_before_in.mapped("product_uom_qty")) - sum(moves_before_out.mapped("product_uom_qty"))

            # Entradas del periodo
            moves_in = Move.search([
                ("product_id", "=", product.id),
                ("state", "=", "done"),
                ("date", ">=", fields.Datetime.to_string(dt_start)),
                ("date", "<=", fields.Datetime.to_string(dt_end)),
                ("location_dest_id", "in", internal_location_ids),
                ("location_id", "not in", internal_location_ids),
            ])
            logging.warning("moves_in")
            logging.warning(moves_in)
            # Salidas del periodo
            moves_out = Move.search([
                ("product_id", "=", product.id),
                ("state", "=", "done"),
                ("date", ">=", fields.Datetime.to_string(dt_start)),
                ("date", "<=", fields.Datetime.to_string(dt_end)),
                ("location_id", "in", internal_location_ids),
                ("location_dest_id", "not in", internal_location_ids),
            ])
            logging.warning("moves_out")
            logging.warning(moves_out)

            in_qty = sum(moves_in.mapped("product_uom_qty"))
            out_qty = sum(moves_out.mapped("product_uom_qty"))
            balance_qty = opening_qty + in_qty - out_qty

            # Costo estándar como fallback compatible entre versiones
            cost = product.standard_price or 0.0

            opening_amount = opening_qty * cost
            in_amount = in_qty * cost
            out_amount = out_qty * cost
            total_cost = balance_qty * cost

            if not opening_qty and not in_qty and not out_qty and not balance_qty:
                continue

            lines.append({
                "default_code": product.default_code or "",
                "name": product.display_name or "",
                "uom": product.uom_id.name or "",
                "cost_method": dict(product.product_tmpl_id._fields["cost_method"].selection).get(
                    product.product_tmpl_id.cost_method, product.product_tmpl_id.cost_method
                ),
                "opening_qty": opening_qty,
                "in_qty": in_qty,
                "out_qty": out_qty,
                "balance_qty": balance_qty,
                "opening_amount": opening_amount,
                "in_amount": in_amount,
                "out_amount": out_amount,
                "cost": cost,
                "total_cost": total_cost,
            })

        return lines

    def _build_workbook(self, output, lines):
        import xlsxwriter

        workbook = xlsxwriter.Workbook(output, {"in_memory": True})
        sheet = workbook.add_worksheet("Inventario")

        title_fmt = workbook.add_format({
            "bold": True,
            "align": "center",
            "valign": "vcenter",
            "font_size": 14,
            "border": 1,
        })
        header_fmt = workbook.add_format({
            "bold": True,
            "bg_color": "#D9E1F2",
            "border": 1,
            "align": "center",
            "valign": "vcenter",
        })
        text_fmt = workbook.add_format({
            "border": 1,
            "align": "left",
        })
        number_fmt = workbook.add_format({
            "border": 1,
            "align": "right",
            "num_format": "#,##0.00",
        })
        integer_fmt = workbook.add_format({
            "border": 1,
            "align": "right",
            "num_format": "#,##0.00",
        })

        row = 0
        sheet.merge_range(row, 0, row, 12, "REPORTE DE INVENTARIO POR ALMACÉN", title_fmt)
        row += 2

        sheet.write(row, 0, "Almacén:", header_fmt)
        sheet.write(row, 1, self.warehouse_id.display_name, text_fmt)
        sheet.write(row, 3, "Fecha inicio:", header_fmt)
        sheet.write(row, 4, str(self.date_start), text_fmt)
        sheet.write(row, 6, "Fecha fin:", header_fmt)
        sheet.write(row, 7, str(self.date_end), text_fmt)
        row += 2

        headers = [
            "Código Producto",
            "Nombre Producto",
            "UM",
            "Método Costeo",
            "Inventario Inicial",
            "Entradas",
            "Salidas",
            "Existencia",
            "Importe Inicial",
            "Importe Entradas",
            "Importe Salidas",
            "Costo Promedio",
            "Costo Total",
        ]

        for col, header in enumerate(headers):
            sheet.write(row, col, header, header_fmt)

        row += 1

        for line in lines:
            sheet.write(row, 0, line["default_code"], text_fmt)
            sheet.write(row, 1, line["name"], text_fmt)
            sheet.write(row, 2, line["uom"], text_fmt)
            sheet.write(row, 3, line["cost_method"], text_fmt)
            sheet.write_number(row, 4, line["opening_qty"], integer_fmt)
            sheet.write_number(row, 5, line["in_qty"], integer_fmt)
            sheet.write_number(row, 6, line["out_qty"], integer_fmt)
            sheet.write_number(row, 7, line["balance_qty"], integer_fmt)
            sheet.write_number(row, 8, line["opening_amount"], number_fmt)
            sheet.write_number(row, 9, line["in_amount"], number_fmt)
            sheet.write_number(row, 10, line["out_amount"], number_fmt)
            sheet.write_number(row, 11, line["cost"], number_fmt)
            sheet.write_number(row, 12, line["total_cost"], number_fmt)
            row += 1

        sheet.set_column("A:A", 18)
        sheet.set_column("B:B", 40)
        sheet.set_column("C:C", 10)
        sheet.set_column("D:D", 22)
        sheet.set_column("E:M", 15)

        return workbook
