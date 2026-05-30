odoo.define('quemen.pos', function(require) {
    'use strict';

    const Pos = require('pos_coupon.pos');
    const Registries = require('point_of_sale.Registries');
    const models = require('point_of_sale.models');
    const rpc = require('web.rpc');

    
    var _order_super = models.Order.prototype;
    models.Order = models.Order.extend({
        
        _llenarCero: function(valor){
            const nuevoValor = "0"
            console.log('valor')
            valor = valor.toString()
            if (valor < 10){
                nuevoValor = "0"+valor
            }
            return nuevoValor
        },
        _checkProgramRules: async function (program) {
            const check = _order_super._checkProgramRules.apply(this, arguments);
            console.log('new _checkProgramRules inherit')
            const ruleFrom = program.rule_date_from ? this._convertToDate(program.rule_date_from) : new Date(-8640000000000000);
            const ruleTo = program.rule_date_to ? this._convertToDate(program.rule_date_to) : new Date(8640000000000000);
            const orderDate = new Date();
            
            const orderTime = orderDate.getHours().toString().padStart(2, '0')+ ':' + orderDate.getMinutes().toString().padStart(2, '0')
            const ruleFromTime = ruleFrom.getHours().toString().padStart(2, '0') + ':' + ruleFrom.getMinutes().toString().padStart(2, '0')
            const ruleToTime = ruleTo.getHours().toString().padStart(2, '0') + ':' + ruleTo.getMinutes().toString().padStart(2, '0')
            console.log(orderTime)
            console.log(ruleFromTime)
            console.log(ruleToTime)
            if ( orderTime < ruleFromTime ||  orderTime > ruleToTime){
                return {
                    successful: false,
                };
                
            }else{
                return check
            }
            
            // Check minimum amount
            // const amountToCheck =
            //     program.rule_minimum_amount_tax_inclusion === 'tax_included'
            //         ? this.get_total_with_tax()
            //         : this.get_total_without_tax();
            // // TODO jcb rule_minimum_amount has to be converted.
            // if (
            //     !(
            //         amountToCheck > program.rule_minimum_amount ||
            //         float_is_zero(amountToCheck - program.rule_minimum_amount, this.pos.currency.decimals)
            //     )
            // ) {
            //     return {
            //         successful: false,
            //         reason: 'Minimum amount for this program is not satisfied.',
            //     };
            // }

            // // Check minimum quantity
            // const validQuantity = this._getRegularOrderlines()
            //     .filter((line) => {
            //         return program.valid_product_ids.has(line.product.id);
            //     })
            //     .reduce((total, line) => total + line.quantity, 0);
            // if (!(validQuantity >= program.rule_min_quantity)) {
            //     return {
            //         successful: false,
            //         reason: "Program's minimum quantity is not satisfied.",
            //     };
            // }

            // // Bypass other rules if program is coupon_program
            // if (program.program_type === 'coupon_program') {
            //     return {
            //         successful: true,
            //     };
            // }

            // // Check if valid customer
            // const customer = this.get_client();
            // const partnersDomain = program.rule_partners_domain || '[]';
            // if (partnersDomain !== '[]' && !program.valid_partner_ids.has(customer ? customer.id : 0)) {
            //     return {
            //         successful: false,
            //         reason: "Current customer can't avail this program.",
            //     };
            // }

            // // Check rule date
            // const ruleFrom = program.rule_date_from ? this._convertToDate(program.rule_date_from) : new Date(-8640000000000000);
            // const ruleTo = program.rule_date_to ? this._convertToDate(program.rule_date_to) : new Date(8640000000000000);
            // const orderDate = new Date();
            // console.log('orderDate')
            // console.log(orderDate)
            // console.log(orderDate.getHours())
            // console.log(ruleFrom)
            // console.log(ruleFrom.getHours())
            // console.log(ruleTo)
            // console.log(ruleTo.getHours())

            // console.log(orderDate.getTime())
            // console.log(ruleFrom.getTime())
            // var orderTime = self._llenarCero(orderDate.getHours()) + ':' + self._llenarCero(orderDate.getMinutes())
            // var ruleFromTime = self._llenarCero(ruleFrom.getHours()) + ':' + self._llenarCero(ruleFrom.getMinutes())
            // var ruleToTime = self._llenarCero(ruleTo.getHours()) + ':' + self._llenarCero(ruleTo.getMinutes())


            // console.log(orderTime)
            // console.log(ruleFromTime)
            // console.log(ruleToTime)

            // // if(orderTime < ruleFromTime){
            // //     console.log('cumple1')
            // // }

            // // if(orderTime > ruleToTime){
            // //     console.log('cumple2')
            // // }
            
            // // if ( orderTime >= ruleFromTime &&  orderTime <= ruleToTime){
            // //     console.log('cumplTodo')
            // //     return {
            // //         successful: true,
            // //     };
                
            // // }
    
            
            // if (!(orderDate >= ruleFrom && orderDate <= ruleTo)) {
            //     return {
            //         successful: false,
            //         reason: 'Program already expired.',
            //     };
            // }

            // // Check max number usage
            // if (program.maximum_use_number !== 0) {
            //     const [result] = await rpc
            //         .query({
            //             model: 'coupon.program',
            //             method: 'read',
            //             args: [program.id, ['total_order_count']],
            //             kwargs: { context: session.user_context },
            //         })
            //         .catch(() => Promise.resolve([false])); // may happen because offline
            //     if (!result) {
            //         return {
            //             successful: false,
            //             reason: 'Unable to get the number of usage of the program.',
            //         };
            //     } else if (!(result.total_order_count < program.maximum_use_number)) {
            //         return {
            //             successful: false,
            //             reason: "Program's maximum number of usage has been reached.",
            //         };
            //     }
            // }

            // return {
            //     successful: true,
            // };
        },        
        
    });
    
    // const QuemenPos = Pos =>
    //     class extends Pos {
    
    // Registries.Component.extend(Pos, QuemenPos);
Pos

});