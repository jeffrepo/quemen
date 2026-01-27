# -*- encoding: utf-8 -*-

from odoo import api, models, fields
from datetime import date
import datetime
import time
import dateutil.parser
from dateutil.relativedelta import relativedelta
from dateutil import relativedelta as rdelta
from odoo.fields import Date, Datetime
import logging
from operator import itemgetter
import pytz
import logging
from odoo.exceptions import UserError, ValidationError
# import odoo.addons.hr_gt.a_letras

class ReportExplosionInsumos(models.AbstractModel):
    _name = 'report.quemen.reporte_explosion_insumos'
    _description = " "

    def get_info(self, o):
        #info contiene todo la informacion de productos por componente o materia prima
        info = {'mp': {}}
        products_pt = {}
        products_cp = {}
        products_mp = {}
        if o.product_ids:
            for pt_line in o.product_ids:
                if pt_line.product_id.id not in products_pt:
                     products_pt[pt_line.product_id.id] = {'name': pt_line.product_id.name, 'quantity': 0.00000, 'uom': pt_line.product_id.uom_id.name}
                products_pt[pt_line.product_id.id]['quantity'] += pt_line.quantity

                if pt_line.product_id.bom_ids:
                    for bom_line in pt_line.product_id.bom_ids[0].bom_line_ids:
                        if bom_line.stage not in info:
                            info[bom_line.stage] = {'component': {}, 'mp': {}}

                        # verificamos si es componente o materia prima
                        logging.warning(bom_line.product_id.name[0:4])
                        if bom_line.product_id.name[0:4] == "COMP":
                            if len(bom_line.product_id.bom_ids) == 0:
                                raise ValidationError("Producto no contiene lista de materiales" + str(bom_line.product_id.name))
                            if bom_line.product_id.id not in info[bom_line.stage]['component']:
                                info[bom_line.stage]['component'][bom_line.product_id.id] = {'product': bom_line.product_id, 'quantity': 0.00000, 'quantity_exp': 0.00000}
                            info[bom_line.stage]['component'][bom_line.product_id.id]['quantity'] += (bom_line.product_qty * pt_line.quantity)
                            info[bom_line.stage]['component'][bom_line.product_id.id]['quantity_exp'] += (bom_line.product_qty * pt_line.quantity)
                            logging.warning('componente antes')
                            logging.warning(bom_line.product_id.name)
                            stage = bom_line.stage
                            info = self.search_components(bom_line.product_id, info, stage, pt_line.quantity, bom_line.product_qty)

                        else:
                            if bom_line.product_id.id not in info['mp']:
                                info['mp'][bom_line.product_id.id] = {'product': bom_line.product_id, 'quantity': 0.00000, 'quantity_exp':  0.00000}
                            cantidad_planeada = sum(line.quantity for line in o.product_ids if bom_line.product_id.id == line.product_id.id)
                            info['mp'][bom_line.product_id.id]['quantity'] += (bom_line.product_qty * pt_line.quantity)
                            info['mp'][bom_line.product_id.id]['quantity_exp'] += (bom_line.product_qty * pt_line.quantity) + cantidad_planeada




        logging.warning(products_pt)
        logging.warning(info)
        return [products_pt, info]

    def search_components(self, component, info, stage, pt_line_quantity, bom_line_product_qty):
        list_components = []
        list_mp = []
        new_info = info
        while component:
            logging.warning('WHILE COMPONENT')
            logging.warning(component.name)
            new_component = component
            if len(new_component.bom_ids) > 0:
                for bom_line in new_component.bom_ids[0].bom_line_ids:
                    if bom_line.product_id.name == "COMP - Gelatina de yogurt de durazno KG":
                        logging.warning('COMP; COMP - Gelatina de yogurt de durazno KG**********************')
                    if bom_line.product_id.name[0:4] == "COMP":
                        if len(bom_line.product_id.bom_ids) == 0:
                            raise ValidationError("Producto no contiene lista de materiales" + str(bom_line.product_id.name))
                        new_component = bom_line.product_id
                        new_bom_line_product_qty = (bom_line.product_qty)
                        if len(new_component.bom_ids) > 0:
                            info = self.search_mp(new_component, info ,pt_line_quantity, new_bom_line_product_qty)
                        logging.warning('new_component: ' + bom_line.product_id.name)
                        new_component_stage = bom_line.stage

                        list_components.append(new_component.name)
                    else:
                        logging.warning('# REVIEW: product')
                        logging.warning(bom_line.product_id.name)
                        if bom_line.product_id.id not in info['mp']:
                            info['mp'][bom_line.product_id.id] = {'product': bom_line.product_id, 'quantity': 0.00000, 'quantity_exp': 0.00000}
                        info['mp'][bom_line.product_id.id]['quantity'] += (bom_line.product_qty * pt_line_quantity)
                        info['mp'][bom_line.product_id.id]['quantity_exp'] += ((bom_line.product_qty / bom_line.bom_id.product_qty) * pt_line_quantity * bom_line_product_qty)

                component = False
        logging.warning('components search')
        logging.warning(list_components)

        return new_info

    def search_mp(self, new_component, info, pt_line_quantity, bom_line_product_qty):
        for bom_line in new_component.bom_ids[0].bom_line_ids:
            if bom_line.product_id.name[0:4] != "COMP":
                if bom_line.product_id.id not in info['mp']:
                    info['mp'][bom_line.product_id.id] = {'product': bom_line.product_id, 'quantity': 0.00000, 'quantity_exp': 0.00000}
                info['mp'][bom_line.product_id.id]['quantity'] +=  (bom_line.product_qty * pt_line_quantity)
                info['mp'][bom_line.product_id.id]['quantity_exp'] += ((bom_line.product_qty/bom_line.bom_id.product_qty) * pt_line_quantity * bom_line_product_qty)
        return info

    @api.model
    def _get_report_values(self, docids, data=None):
        model = 'quemen.op_lote'
        docs = self.env[model].browse(docids)


        return {
            'doc_ids': docids,
            'doc_model': model,
            'data': data,
            'docs': docs,
            'get_info': self.get_info,
        }
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
