odoo.define('quemen.models', function (require) {
"use strict";
    const { Context } = owl;
    var rpc = require('web.rpc');
    var models = require('point_of_sale.models');
    // var gui = require('point_of_sale.gui');
    var time, time1 = require('web.time');
    var field_utils = require('web.field_utils');
    // var gui = require('point_of_sale.gui');

    // var { Gui } = require('point_of_sale.Gui');

    var core = require('web.core');
    var rpc = require('web.rpc');
    var _t = core._t;

    models.load_fields('res.company', 'street_name')
    models.load_fields('res.company', 'street2')
    models.load_fields('res.company', 'l10n_mx_edi_colony' )
    models.load_fields('res.company', 'country_id')
    models.load_fields('res.company', 'l10n_mx_edi_colony_code')
    models.load_fields('res.company', 'l10n_mx_edi_locality')
    models.load_fields('res.company', 'city')
    models.load_fields('res.company', 'state_id')
    models.load_fields('res.company', 'zip')
    models.load_fields('res.company', 'country_id')
    models.load_fields('account.journal', 'direccion')

models.load_fields("product.product", ["invoice_policy", "type"]);

var super_order_line_model = models.Orderline.prototype;
models.Orderline = models.Orderline.extend({
  initialize: function (attributes, options) {
      super_order_line_model.initialize.apply(this, arguments);

      this.producto_especial = this.producto_especial || false;

  },
  init_from_JSON: function (json) {
      super_order_line_model.init_from_JSON.apply(this, arguments);
      this.producto_especial = json.producto_especial;
  },
  export_as_JSON: function () {
      const json = super_order_line_model.export_as_JSON.apply(this, arguments);
      json.producto_especial = this.producto_especial;
      return json;
  },
  set_producto_especial: function(producto_especial){
    this.set({
      producto_especial: producto_especial
    });
  },

  get_producto_especial: function(){
    return this.get('producto_especial');
  },

});

    var _super_posmodel = models.PosModel.prototype;
    models.PosModel = models.PosModel.extend({

        initialize: function(attributes) {
            _super_posmodel.initialize.apply(this,attributes);

            console.log('INICIALIZAR POS MODEL')
	    var self = this;
            self.rpc({
                model: 'stock.lot',
                method: 'get_available_lots_for_pos',
                args: [],
            }).then(function(result) {
                self.lot_dict = result || {};
                console.log('✅ Lotes cargados:', self.lot_dict);
            }).catch(function(err) {
                console.error('❌ Error cargando lotes:', err);
            });

            self.regimenes_fiscales = [{
                'id': 601,
                'name': 'General de Ley Personas Morales',
            }, {
                'id': 603,
                'name': 'Personas Morales con Fines no Lucrativos',
            }, {
                'id': 603,
                'name': 'Personas Morales con Fines no Lucrativos',
            }, {
                'id': 605,
                'name': 'Sueldos y Salarios e Ingresos Asimilados a Salarios',
            }, {
                'id': 606,
                'name': 'Arrendamiento',
            }, {
                'id': 607,
                'name': 'Régimen de Enajenación o Adquisición de Bienes',
            } , {
                'id': 608,
                'name': 'Demás ingresos',
            } , {
                'id': 609,
                'name': 'Consolidación',
            } , {
                'id': 610,
                'name': 'Residentes en el Extranjero sin Establecimiento Permanente en México',
            } , {
                'id': 611,
                'name': 'Ingresos por Dividendos (socios y accionistas)',
            }, {
                'id': 612,
                'name': 'Personas Físicas con Actividades Empresariales y Profesionales',
            }, {
                'id': 614,
                'name': 'Ingresos por intereses',
            }, {
                'id': 615,
                'name': 'Régimen de los ingresos por obtención de premios',
            }, {
                'id': 616,
                'name': 'Sin obligaciones fiscales',
            }, {
                'id': 620,
                'name': 'Sociedades Cooperativas de Producción que optan por diferir sus ingresos',
            }, {
                'id': 621,
                'name': 'Incorporación Fiscal',
            }, {
                'id': 622,
                'name': 'Actividades Agrícolas, Ganaderas, Silvícolas y Pesqueras',
            }, {
                'id': 623,
                'name': 'Opcional para Grupos de Sociedades',
            }, {
                'id': 624,
                'name': 'Coordinados',
            }, {
                'id': 625,
                'name': 'Régimen de las Actividades Empresariales con ingresos a través de Plataformas Tecnológicas',
            },{
                'id': 626,
                'name': 'Régimen Simplificado de Confianza - RESICO',
            },{
                'id': 628,
                'name': 'Hidrocarburos',
            },{
                'id': 629,
                'name': 'De los Regímenes Fiscales Preferentes y de las Empresas Multinacionales',
            },{
                'id': 630,
                'name': 'Enajenación de acciones en bolsa de valores',
            }]
            console.log(self)
        },
        add_new_order: function(){
            var new_order = _super_posmodel.add_new_order.apply(this);
            console.log("Que es esto?")
            if (this.config.cliente_id) {
                new_order.set_client(this.db.get_partner_by_id(this.config.cliente_id[0]))
            }
        }
    })


var _super_order = models.Order.prototype;

models.Order = models.Order.extend({

  set_fecha: function(fecha_hora){
    this.set({
      fecha: fecha_hora
    });
  },

  get_fecha: function(){
    return this.get('fecha');
  },

  set_hora: function(hora_id){
    this.set({
      hora: hora_id
    });
  },

  get_hora: function(){
    return this.get('hora')
  },

  set_observaciones: function(observaciones){
    this.set({
      observaciones: observaciones
    });
  },

  get_observaciones: function(){
    return this.get('observaciones')
  },

  set_autorizo: function(autorizo){
    this.set({
      autorizo: autorizo
    });
  },

  get_autorizo: function(){
    return this.get('autorizo')
  },

  set_terminosCondiciones: function(terminos_condiciones){
    this.set({
      terminos_condiciones: terminos_condiciones
    });
  },

  get_terminos_condiciones: function(){
    return this.get('terminos_condiciones')
  },

  set_entrega: function(sucursal_entrega){
    this.set({
      entrega: sucursal_entrega
    });
  },

  get_entrega: function(){
    return this.get('entrega')
  },

  set_fecha_formato: function(formato_correcto){
    this.set({
      formato_correcto: formato_correcto
    });
  },

  get_fecha_formato: function(){
    return this.get('formato_correcto')
  },

  set_fecha_hora_actual: function (fecha_hora_actual){
    this.set({
      fecha_hora_actual: fecha_hora_actual
    });
  },

  get_fecha_hora_actual: function(){
    return this.get('fecha_hora_actual')
  },

  set_dicc_prod_especiales: function(dicc_productos_especiales){
    console.log('set productos especiales')
    console.log(dicc_productos_especiales)
    this.set({
      dicc_productos_especiales: dicc_productos_especiales
    });
  },

  get_dicc_prod_especiales: function(){
    console.log('get dicc_productos_especiales')
    console.log(this.get('dicc_productos_especiales'))
    return this.get('dicc_productos_especiales')
  },

  set_dicc_total: function(dicc_total){
    this.set({
      dicc_total: dicc_total
    });
  },

  get_dicc_total: function(){
    return this.get('dicc_total')
  },

  export_as_JSON : function(){

    var new_json = _super_order.export_as_JSON.apply(this);
    new_json['fecha'] = this.get_fecha() ? this.get_fecha() : false;
    new_json['hora'] = this.get_hora() ? this.get_hora(): false;
    new_json['observaciones'] = this.get_observaciones() ? this.get_observaciones() : false;
    new_json['sucursal_entrega'] = this.get_entrega() ? this.get_entrega() : false;
    new_json['autorizo'] = this.get_autorizo() ? this.get_autorizo() : false;
    return new_json;
  },

  initialize: function() {
    _super_order.initialize.apply(this,arguments);
    console.log('initialize productos especiales')
    this.set_fecha();
    this.set_hora();
    this.set_observaciones();
    this.set_autorizo();
    this.set_fecha_formato();
    this.set_entrega();
    this.set_fecha_hora_actual();
    this.set_dicc_prod_especiales();
    this.set_dicc_total();
    this.set_terminosCondiciones();
	},

});
});
