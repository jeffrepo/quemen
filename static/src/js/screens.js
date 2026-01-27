odoo.define('quemen.screens', function (require) {
"use strict";

var screens = require('point_of_sale.screens');
var models = require('point_of_sale.models');
// var pos_db = require('point_of_sale.DB');
var rpc = require('web.rpc');
var PosBaseWidget = require('point_of_sale.BaseWidget');
var core = require('web.core');
var _t = core._t;

// var gui = require('point_of_sale.gui');
// var core = require('web.core');
// var PopupWidget = require('point_of_sale.popups');
// var field_utils = require('web.field_utils');
// var QWeb = core.qweb;
// var _t = core._t;

models.load_fields('pos.config', 'efectivo_maximo');
models.load_fields('product.product', 'type');
screens.NumpadWidget.include({
  start: function(event) {
      this._super(event);
  },
  clickDeleteLastChar: function(event) {

      this.orderline_remove;
      console.log('hola')
      console.log(event)
      var linea = this.pos.get_order().get_selected_orderline();
      this.pos.get_order().remove_orderline(linea);
      // this.pos.get_order().get_last_orderline().remove_orderline()
      // this.orderline_remove(this.pos.get_order().get_last_orderline())
      this._super(event);
      // return this.state.deleteLastChar();
  },
});

screens.ActionpadWidget.include({
  renderElement: function(){
      console.log('Am here');
      PosBaseWidget.prototype.renderElement.call(this);
      var self = this;
      this._super();

      this.$('.pay').click(function(){
          var order = self.pos.get_order();
          var has_valid_product_lot = _.every(order.orderlines.models, function(line){
              return line.has_valid_product_lot();
          });
          // Crear mi for each
          //Llave id producto-lote
          //No
          var dicc_prod_lotes = {}
          order.get_orderlines().forEach(function(prod){
            console.log("prod");
            console.log(prod);
            if (prod.has_product_lot == true && prod.pack_lot_lines.length > 0 ) {
              var id_lote = prod.product.id +"-"+ prod.pack_lot_lines.models[0]['changed']['lot_name'];
              console.log("prod.pack_lot_lines.models[0]['changed']['lot_name']");
              console.log(prod.pack_lot_lines.models[0]['changed']['lot_name']);
              if (!(id_lote in dicc_prod_lotes)) {
                dicc_prod_lotes[id_lote]=0
              }

              if ( id_lote in dicc_prod_lotes) {
                dicc_prod_lotes[id_lote]+=prod.get_quantity();
              }


            }

          });
          console.log("Diccionario lote_id");
          console.log(dicc_prod_lotes);

          order.get_orderlines().forEach(function(l) {
            //Tiene chequesito y no tiene fecha
            //o no tiene chequesito
            console.log("Que es to_make_mrp");
            console.log(l.product)
            if ( (l.product.to_make_mrp == true && order.get_fecha() == undefined) || l.product.to_make_mrp == false ){

              if (l.has_product_lot && l.pack_lot_lines.length > 0 ) {
                  // var lote = l.pack_lot_lines.models[0].get_lot_name();
                  // console.log(lote)
                  // var product = l.product;
                  // console.log(l)
                  // var tipo_ubicacion = l.pos.config.picking_type_id[0];

                  rpc.query({
                                  model: 'stock.lot',
                                  method: 'search_read',
                                  args: [[['name', '=', l.pack_lot_lines.models[0].get_lot_name()]], ['id']],
                              })
                              .then(function (lote){
                                  console.log('rpc')
                                  console.log(lote)
                                  if (lote.length == 0){
                                    console.log('es cero')
                                    self.gui.show_screen('products');
                                    self.gui.show_popup('confirm',{
                                        'title': _t('Lote invalido'),
                                        'body':  l.pack_lot_lines.models[0].get_lot_name(),
                                        confirm: function(){
                                            self.gui.show_screen('products');
                                        },
                                    });
                                  }else{
                                      rpc.query({
                                              model: 'pos.order',
                                              method: 'obtener_inventario_producto',
                                              args: [[],l.product.id,l.pos.config.picking_type_id[0],l.pack_lot_lines.models[0].get_lot_name()],
                                          })
                                          .then(function (existencia){

                                              var lot_prod_id = l.product.id+"-"+l.pack_lot_lines.models[0]['changed']['lot_name'];
                                              if (lot_prod_id in dicc_prod_lotes) { //Verificación si el producto-lote esta en el diccionario_productos_lotes (dicc_prod_lotes)
                                                console.log("Existencia de lotes :");
                                                console.log(dicc_prod_lotes);
                                                if (dicc_prod_lotes[lot_prod_id] > existencia){ //La cantidad del producto-lote es mayor que la existencia
                                                    self.gui.show_screen('products');
                                                    self.gui.show_popup('confirm',{
                                                        'title': _t('No hay existencia producto'),
                                                        'body':  l.product.display_name,
                                                        confirm: function(){
                                                            self.gui.show_screen('products');
                                                        },
                                                    });
                                                    // self.gui.show_popup("error",{
                                                    //     "title": "No hay existencia producto",
                                                    //     "body":  l.product.display_name,
                                                    // });

                                                }
                                              }

                                          });

                                  }
                          });

              }else{

                  console.log("Las lineas");
                  console.log(l.product.type);
                  if (l.product.type == 'product' ) {
                    rpc.query({
                            model: 'pos.order',
                            method: 'obtener_inventario_producto',
                            args: [[],l.product.id,l.pos.config.picking_type_id[0],false],
                        })
                        .then(function (existencia){
                            console.log(l.product.display_name)
                            console.log(existencia)
                            console.log(l.quantity)
                            if (l.quantity > existencia){
                                self.gui.show_screen('products');

                                self.gui.show_popup('confirm',{
                                    'title': _t('No hay existencia producto'),
                                    'body':  l.product.display_name,
                                    confirm: function(){
                                        self.gui.show_screen('products');
                                    },
                                });
                                // self.gui.show_popup("error",{
                                //     "title": "No hay existencia producto",
                                //     "body":  l.product.display_name,
                                // });
                            }
                        });
                  }

              }

            }

          });




          if(!has_valid_product_lot){
              self.gui.show_popup('confirm',{
                  'title': _t('Empty Serial/Lot Number'),
                  'body':  _t('One or more product(s) required serial/lot number.'),
                  confirm: function(){
                      self.gui.show_screen('payment');
                  },
              });
          }else{
              self.gui.show_screen('payment');
          }
      });
      this.$('.set-customer').click(function(){
          self.gui.show_screen('clientlist');
      });

  },
  // renderElement: function() {
  //     var self = this;
  //     this._super();
  //
  //     this.$('.pay').click(function(){
  //         console.log('zz')
  //         var order = self.pos.get_order();
  //         var has_valid_product_lot = _.every(order.orderlines.models, function(line){
  //             return line.has_valid_product_lot();
  //         });
  //         if(!has_valid_product_lot){
  //             self.gui.show_popup('confirm',{
  //                 'title': _t('Empty Serial/Lot Number'),
  //                 'body':  _t('One or more product(s) required serial/lot number.'),
  //                 confirm: function(){
  //                     self.gui.show_screen('payment');
  //                 },
  //             });
  //         }else{
  //             self.gui.show_screen('payment');
  //         }
  //     });
  //     this.$('.set-customer').click(function(){
  //         self.gui.show_screen('clientlist');
  //     });
  // }
    //
    // set_value: function(val) {
    //     var self = this;
    //     var gui = this.pos.gui;
    //     var mode = this.numpad_state.get('mode');
    //     var empleado = this.pos.get_empleado();
    //     var orderline = this.pos.get_order().get_selected_orderline();
    //
    //     var _super_sin_this = this._super;
    //     var _super_con_this = _super_sin_this.bind(this);
    //
    //     if (!(orderline.mp_dirty)) {
    //         if (mode == 'quantity') {
    //             if (empleado.responsable) {
    //
    //                 self.gui.show_popup('passinput',{
    //                     'title': 'Ingrese clave',
    //                     'confirm': function(clave_empleado) {
    //                         if (clave_empleado == this.pos.user.pos_security_pin) {
    //                             _super_con_this(val);
    //                         }
    //                         else {
    //                             gui.show_popup('confirm',{
    //                                 'title': 'Error',
    //                                 'body': 'Pin de seguridad incorrecto',
    //                                 'confirm': function(data) {
    //                                 },
    //                             });
    //                         }
    //                     },
    //                 });
    //             }
    //             else {
    //                 gui.show_popup('confirm',{
    //                     'title': 'Error',
    //                     'body': 'No tiene permisos para modificar pedidos que ya se enviaron',
    //                     'confirm': function(data) {
    //                     },
    //                 });
    //
    //             }
    //         }
    //         else if (mode == 'discount') {
    //             if (empleado.descuentos) {
    //                 self.gui.show_popup('passinput',{
    //                     'title': 'Ingrese clave',
    //                     'confirm': function(clave_empleado) {
    //                         if (clave_empleado == this.pos.user.pos_security_pin) {
    //                             _super_con_this(val);
    //                         }
    //                         else {
    //                             gui.show_popup('confirm',{
    //                                 'title': 'Error',
    //                                 'body': 'Pin de seguridad incorrecto',
    //                                 'confirm': function(data) {
    //                                 },
    //                             });
    //                         }
    //                     },
    //                 });
    //             }
    //             else {
    //                 gui.show_popup('confirm',{
    //                     'title': 'Error',
    //                     'body': 'No tiene permisos para hacer descuentos',
    //                     'confirm': function(data) {
    //                     },
    //                 });
    //             }
    //         }
    //         else {
    //             this._super(val);
    //         }
    //     }
    //     else {
    //         this._super(val);
    //     }
    // },
});

screens.ReceiptScreenWidget.include({
  render_receipt: function() {
    this.$('.pos-receipt-container-ticket').html(QWeb.render('TicketPedidoEspecial', this.get_receipt_render_env()));
    this._super();
  },
});

screens.PaymentScreenWidget.include({
    validate_order: function(force_validation) {
        var self = this;
        var order = this.pos.get_order();
        var order_pagos = order.get_paymentlines();
        var _super = this._super.bind(this)
        var total_efectivo = 0;
        if (this.pos.config.efectivo_maximo > 0){
            var metodos_pago_efectivo = [];
            for (var i = 0; i < order_pagos.length; i++) {
                if (order_pagos[i].payment_method.is_cash_count){
                    metodos_pago_efectivo.push(order_pagos[i].payment_method.id)
                    total_efectivo += order_pagos[i].amount
                }

            }

            rpc.query({
                    model: 'pos.session',
                    method: 'search_read',
                    args: [[['id', '=', this.pos.pos_session.id ]], []],
                })
                .then(function (sesion){
                    rpc.query({
                            model: 'pos.payment',
                            method: 'search_read',
                            args: [[['session_id', '=', self.pos.pos_session.id ],['payment_method_id', 'in', metodos_pago_efectivo ]], []],
                        })
                        .then(function (pagos){
                            var efectivo = 0;
                            if (pagos.length > 0 ){

                                for (var i = 0; i < pagos.length; i++) {
                                    efectivo += pagos[i].amount
                                }

                            }
                            if ((sesion[0].cash_register_total_entry_encoding) > self.pos.config.efectivo_maximo){
                                self.pos.gui.show_popup("error",{
                                    "title": "Límite de efectivo",
                                    "body":  "Límite de efectivo máximo",
                                });
                            // }else if ((sesion[0].cash_register_total_entry_encoding+sesion[0].cash_register_balance_start+total_efectivo) > self.pos.config.efectivo_maximo) {
                            }else if ((sesion[0].cash_register_total_entry_encoding+total_efectivo) > self.pos.config.efectivo_maximo) {

                                window.alert('Límite de efectivo, por favor retire efectivo antes de la siguiente venta');
                                _super();
                            }else{
                                _super();
                            }
                            // console.log(efectivo+sesion[0].cash_register_balance_start);
                            self.renderElement();
                        });


                });
        }else{

            this._super();
        }

        // search rpc buscar el pedido
        // verificar que me retorne el objeto del pedido
        // rpc.query({
        //   model: 'pos.order',
        //   method: 'search_read',
        //   args: [[['pos_reference', '=', order.name.toString()]], []],
        //

            rpc.query({
              model: 'pos.order',
              method: 'texto_total',
              args: [[],order.get_total_with_tax()],
            },{
              timeout: 5000,
            }).then(function(total){
              order.set_totalString(total);
              // console.log("order.get_totalString()");
              // console.log(order.get_totalString());
              // self.$('.pos-receipt-container').html(QWeb.render('OrderReceipt', receipt_env));
              // console.log("El total en letras funcion correcta");
              // console.log(total);
              // console.log("que es receipt_env");
              // console.log(receipt_env);
            });
    },
});

// var CuponesButton = screens.ActionButtonWidget.extend({
//     template: 'CuponesButton',
//     init: function(parent, options) {
//         this._super(parent, options);
//         this.pos.bind('change:selectedOrder',this.renderElement,this);
//     },
//     button_click: function(){
//         var self = this;
//         var order = this.pos.get_order();
//         var gui = this.pos.gui;
//
//         this.gui.show_popup('textinput',{
//             'title': 'Ingrese cupon',
//             'confirm': function(cupon) {
//                 // var error_status = self.apply_coupon(order, codigo_cupon)
//                 rpc.query({
//                         model: 'sale.coupon',
//                         method: 'search_read',
//                         args: [[['code', '=', cupon],['state','=','new']], []],
//                     })
//                     .then(function (busqueda){
//                         if(busqueda.length > 0){
//                             self.obtener_programa(busqueda);
//                         }else{
//                             self.gui.show_popup('confirm',{
//                                 'title': _t('Codigo invalido'),
//                                 'body':  cupon,
//                                 confirm: function(){
//                                     console.log('')
//                                 },
//                             });
//                             // console.log('codigo invalido')
//                         }
//                     });
//             },
//         });
//
//     },
//     obtener_programa: function(busqueda){
//         var self = this;
//         var order = this.pos.get_order();
//         var gui = this.pos.gui;
//         rpc.query({
//                 model: 'sale.coupon.program',
//                 method: 'search_read',
//                 args: [[['id', '=', busqueda[0].program_id[0]]], []],
//             })
//             .then(function (programa){
//                 if(programa.length > 0){
//                     var tipo_descuento = programa[0].discount_type;
//
//                     if (tipo_descuento == 'fixed_amount'){
//                         var product_id = self.pos.db.get_product_by_id(programa[0]['discount_line_product_id'][0]);
//                         var descuento = programa[0].discount_fixed_amount;
//                         order.add_product(product_id, { price: descuento*-1, quantity: 1, extras: { price_manually_set: true } });
//                         rpc.query({
//                                 model: 'pos.order',
//                                 method: 'deshabilitar_cupon',
//                                 args: [[],busqueda[0].id],
//                             })
//                             .then(function (res){
//
//                             });
//                         order.get_last_orderline().set_cupon(busqueda[0].code);
//                         // console.log(order.get_last_orderline().get_cupon())
//
//                     }
//                     // console.log(programa)
//                 }else{
//                     self.gui.show_popup('confirm',{
//                         'title': _t('Codigo invalido'),
//                         'body':  cupon,
//                         confirm: function(){
//                             console.log('')
//                         },
//                     });
//                     // console.log('codigo invalido')
//                 }
//             });
//     },
// });

// screens.define_action_button({
//     'name': 'cupones',
//     'widget': CuponesButton,
//     'condition': function(){
//         return this.pos.config.cupones;
//     },
// });


var TipoVentaButton = screens.ActionButtonWidget.extend({
    template: 'TipoVentaButton',
    init: function(parent, options) {
        this._super(parent, options);
        this.pos.bind('change:selectedOrder',this.renderElement,this);
    },
    button_click: function(){
        var self = this;
        var order = this.pos.get_order();
        var lista_ventas = [
            {
                'label': 'Mesas',
                'item':  'mesas',
            },
            {
                'label': 'Mostrador',
                'item':  'mostrador',
            },
            {
                'label': 'A domicilio',
                'item':  'domicilio',
            },
            {
                'label': 'Pedidos especiales',
                'item':  'especial',
            }
        ];
        this.gui.show_popup('selection',{
            'title': 'Seleccione tipo de venta',
            'list': lista_ventas,
            'confirm': function(tipo) {
                console.log(tipo);
                self.pos.set_tipo_venta(tipo);
                self.renderElement();


            },
        });


        this.renderElement();
    },
    get_name: function(){
        var tipo_venta = this.pos.get_tipo_venta();
        if(tipo_venta){
            return tipo_venta;
        }else{
            // return "Escoja tipo venta---";
            return "mostrador";
        }
    },

});

    

screens.define_action_button({
    'name': 'tipo_venta',
    'widget': TipoVentaButton,
    'condition': function(){
        return this.pos.config.tipo_venta;
    },
});

screens.ProductScreenWidget.include({
  /**
   * Processes the buffer of keys filled by _onKeypadKeyDown and
   * distinguishes between the actual keystrokes and scanner inputs.
   *
   * @private
  */
  _handleBufferedKeys: function () {
      // If more than 2 keys are recorded in the buffer, chances are high that the input comes
      // from a barcode scanner. In this case, we don't do anything.
      if (this.buffered_key_events.length > 2) {
          this.buffered_key_events = [];
          return;
      }

      for (var i = 0; i < this.buffered_key_events.length; ++i) {
          var ev = this.buffered_key_events[i];
          if ((ev.key >= "0" && ev.key <= "9") || ev.key === ".") {
              if( ev.key === "."){
                  break;
              }else{
                this.numpad.state.appendNewChar(ev.key);
              }

          }
          else {
              switch (ev.key){
                  case "Backspace":
                      var linea = this.pos.get_order().get_selected_orderline();
                      this.pos.get_order().remove_orderline(linea);
                      break;
                  case "Delete":
                      this.numpad.state.resetValue();
                      break;
                  case ",":
                      // this.numpad.state.appendNewChar(".");
                      break;
                  case "+":
                      this.numpad.state.positiveSign();
                      break;
                  case "-":
                      this.numpad.state.negativeSign();
                      break;
              }
          }
      }
      this.buffered_key_events = [];
  },

})
// screens.ScreenWidget.include({
//     barcode_product_action: function(code){
//         var self = this;
//         // self._super();
//         // console.log('BARCODE_PRODUCT_ACTION')
//         // console.log(code.code)
//         // // console.log(code.code.length)
//         // console.log(code.code.substring(0, 11))
//         console.log('quemen barcode')
//         code.code = String(code.code).substring(0, 11);
//         code.base_code = String(code.base_code).substring(0, 11);
//         // code = "10900219001"
//         console.log('SELF SCAN PRODUCT')
//         // console.log(self.pos.scan_product(code));
//         console.log('---------------------')
//         if (self.pos.scan_product(code)) {
//             if (self.barcode_product_screen) {
//                 self.gui.show_screen(self.barcode_product_screen, null, null, true);
//             }
//         } else {
//             this.barcode_error_action(code);
//         }
//     },
//
// });


});
