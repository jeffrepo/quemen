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

class ReportPlaneacion(models.AbstractModel):
    _name = 'report.quemen.reporte_planeacion'
    _description = " "

    def get_info(self, o):
        #info contiene todo la informacion de productos por componente o materia prima
        info = {}
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
                                info[bom_line.stage]['component'][bom_line.product_id.id] = {'product': bom_line.product_id, 'quantity': 0.00000}
                            info[bom_line.stage]['component'][bom_line.product_id.id]['quantity'] += (bom_line.product_qty * pt_line.quantity)
                            logging.warning('componente antes')
                            logging.warning(bom_line.product_id.name)
                            stage = bom_line.stage
                            info = self.search_components(bom_line.product_id, info, stage, pt_line.quantity)
                            
                        else:
                            if bom_line.product_id.id not in info[bom_line.stage]['mp']:
                                info[bom_line.stage]['mp'][bom_line.product_id.id] = {'product': bom_line.product_id, 'quantity': 0.00000}
                            info[bom_line.stage]['mp'][bom_line.product_id.id]['quantity'] += (bom_line.product_qty * pt_line.quantity)

                            

        
        logging.warning(products_pt)
        logging.warning(info)
        return [products_pt, info]

    def search_components(self, component, info, stage, pt_line_quantity):
        list_components = []
        list_mp = []
        new_info = info
        while component:
            logging.warning('WHILE COMPONENT')
            logging.warning(component)
            new_component = component
            if len(new_component.bom_ids) > 0:
                for bom_line in new_component.bom_ids[0].bom_line_ids:
                    if bom_line.product_id.name[0:4] == "COMP":
                        if len(bom_line.product_id.bom_ids) == 0:
                            raise ValidationError("Producto no contiene lista de materiales" + str(bom_line.product_id.name))
                        new_component = bom_line.product_id
                        new_component_stage = bom_line.stage
                        if new_component.id not in info[new_component_stage]['component']:
                            info[new_component_stage]['component'][new_component.id] = {'product': new_component, 'quantity': 0.00000}
                        info[new_component_stage]['component'][new_component.id]['quantity'] += (bom_line.product_qty * pt_line_quantity)
                        
                        list_components.append(new_component.name)
                    else:
                        new_component_stage = bom_line.stage
                        if new_component_stage in info:
                            if bom_line.product_id.id not in info[new_component_stage]['mp']:
                                info[new_component_stage]['mp'][bom_line.product_id.id] = {'product': bom_line.product_id, 'quantity': 0.00000}
                            info[new_component_stage]['mp'][bom_line.product_id.id]['quantity'] += (bom_line.product_qty * pt_line_quantity)
                        
                component = False
        logging.warning('components search')
        logging.warning(list_components)
                 
        return new_info
    
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
            # 'obtener_tienda': self.obtener_tienda,
            # 'salida_productos_vencidos': self.salida_productos_vencidos,

        }
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
