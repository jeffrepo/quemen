# -*- coding: utf-8 -*-
import base64
import io
from datetime import datetime, time

from odoo import fields, models, _
from odoo.exceptions import UserError


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
    file_data = fields.Binary(
        string="Archivo",
        readonly=True,
    )
    file_name = fields.Char(
        string="Nombre archivo",
        readonly=True,
    )

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
            (self.warehouse_id.code or self.warehouse_id.name or "ALMACEN").replace(" ", "_"),
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
                self._name,
                self.id,
            ),
            "target": "self",
        }

    def _get_internal_location_ids(self):
        self.ensure_one()

        warehouse = self.warehouse_id
        root_location = warehouse.view_location_id

        locations = self.env["stock.location"].search([
            ("id", "child_of", root_location.id),
            ("usage", "=", "internal"),
        ])
        return locations.ids

    def _get_product_domain(self):
        Product = self.env["product.product"]

        # Compatible Odoo 15 / 19
        if "is_storable" in Product._fields:
            return [("is_storable", "=", True)]
        return [("type", "=", "product")]

    def _get_cost_method_label(self, product):
        tmpl = product.product_tmpl_id
        cost_method = tmpl.cost_method or ""

        field_obj = tmpl._fields.get("cost_method")
        if not field_obj:
            return cost_method

        selection = field_obj.selection

        # En algunas versiones selection puede ser función
        if callable(selection):
            try:
                selection = selection(tmpl)
            except TypeError:
                try:
                    selection = selection(self.env)
                except TypeError:
                    selection = []

        selection_dict = dict(selection or [])
        return selection_dict.get(cost_method, cost_method)

    def _get_qty_from_moves(self, moves, product):
        qty = 0.0
        for move in moves:
            if hasattr(move, "quantity_done"):
                qty += move.quantity_done or 0.0
            else:
                qty += move.product_uom_qty or 0.0
        return qty

    def _get_report_lines(self):
        self.ensure_one()

        Product = self.env["product.product"]
        Move = self.env["stock.move"]

        internal_location_ids = self._get_internal_location_ids()

        dt_start = datetime.combine(self.date_start, time.min)
        dt_end = datetime.combine(self.date_end, time.max)

        dt_start_str = fields.Datetime.to_string(dt_start)
        dt_end_str = fields.Datetime.to_string(dt_end)

        products = Product.search(
            self._get_product_domain(),
            order="default_code, name"
        )

        lines = []

        for product in products:
            # Entradas antes del periodo
            moves_before_in = Move.search([
                ("product_id", "=", product.id),
                ("state", "=", "done"),
                ("date", "<", dt_start_str),
                ("location_dest_id", "in", internal_location_ids),
                ("location_id", "not in", internal_location_ids),
            ])

            # Salidas antes del periodo
            moves_before_out = Move.search([
                ("product_id", "=", product.id),
                ("state", "=", "done"),
                ("date", "<", dt_start_str),
                ("location_id", "in", internal_location_ids),
                ("location_dest_id", "not in", internal_location_ids),
            ])

            opening_in_qty = self._get_qty_from_moves(moves_before_in, product)
            opening_out_qty = self._get_qty_from_moves(moves_before_out, product)
            opening_qty = opening_in_qty - opening_out_qty

            # Entradas del periodo
            moves_in = Move.search([
                ("product_id", "=", product.id),
                ("state", "=", "done"),
                ("date", ">=", dt_start_str),
                ("date", "<=", dt_end_str),
                ("location_dest_id", "in", internal_location_ids),
                ("location_id", "not in", internal_location_ids),
            ])

            # Salidas del periodo
            moves_out = Move.search([
                ("product_id", "=", product.id),
                ("state", "=", "done"),
                ("date", ">=", dt_start_str),
                ("date", "<=", dt_end_str),
                ("location_id", "in", internal_location_ids),
                ("location_dest_id", "not in", internal_location_ids),
            ])

            in_qty = self._get_qty_from_moves(moves_in, product)
            out_qty = self._get_qty_from_moves(moves_out, product)
            balance_qty = opening_qty + in_qty - out_qty

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
                "cost_method": self._get_cost_method_label(product),
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

        row = 0
        sheet.merge_range(row, 0, row, 12, "REPORTE DE INVENTARIO POR ALMACÉN", title_fmt)
        row += 2

        sheet.write(row, 0, "Almacén:", header_fmt)
        sheet.write(row, 1, self.warehouse_id.display_name or "", text_fmt)
        sheet.write(row, 3, "Fecha inicio:", header_fmt)
        sheet.write(row, 4, str(self.date_start or ""), text_fmt)
        sheet.write(row, 6, "Fecha fin:", header_fmt)
        sheet.write(row, 7, str(self.date_end or ""), text_fmt)
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
            sheet.write_number(row, 4, line["opening_qty"], number_fmt)
            sheet.write_number(row, 5, line["in_qty"], number_fmt)
            sheet.write_number(row, 6, line["out_qty"], number_fmt)
            sheet.write_number(row, 7, line["balance_qty"], number_fmt)
            sheet.write_number(row, 8, line["opening_amount"], number_fmt)
            sheet.write_number(row, 9, line["in_amount"], number_fmt)
            sheet.write_number(row, 10, line["out_amount"], number_fmt)
            sheet.write_number(row, 11, line["cost"], number_fmt)
            sheet.write_number(row, 12, line["total_cost"], number_fmt)
            row += 1

        sheet.set_column("A:A", 18)
        sheet.set_column("B:B", 40)
        sheet.set_column("C:C", 12)
        sheet.set_column("D:D", 20)
        sheet.set_column("E:M", 16)

        return workbook
