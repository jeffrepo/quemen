odoo.define('quemen.pos', function(require) {
    'use strict';

    require('pos_coupon.pos');

    const models = require('point_of_sale.models');
    const _order_super = models.Order.prototype;

    models.Order = models.Order.extend({
        _minutes_from_date: function(date) {
            return date.getHours() * 60 + date.getMinutes();
        },

        _is_time_in_range: function(currentMinutes, startMinutes, endMinutes) {
            // Same start/end means "all day".
            if (startMinutes === endMinutes) {
                return true;
            }

            // Normal range, for example 08:00-18:00.
            if (startMinutes < endMinutes) {
                return currentMinutes >= startMinutes && currentMinutes <= endMinutes;
            }

            // Overnight range, for example 22:00-05:00.
            return currentMinutes >= startMinutes || currentMinutes <= endMinutes;
        },

        _checkProgramRules: async function(program) {
            if (!program) {
                return {
                    successful: false,
                    reason: 'Missing program.',
                };
            }

            const check = await Promise.resolve(
                _order_super._checkProgramRules.apply(this, arguments)
            );

            if (!check || !check.successful) {
                return check;
            }

            if (!program.rule_date_from || !program.rule_date_to) {
                return check;
            }

            const ruleFrom = this._convertToDate(program.rule_date_from);
            const ruleTo = this._convertToDate(program.rule_date_to);
            const orderDate = new Date();

            const orderMinutes = this._minutes_from_date(orderDate);
            const ruleFromMinutes = this._minutes_from_date(ruleFrom);
            const ruleToMinutes = this._minutes_from_date(ruleTo);

            const timeAllowed = this._is_time_in_range(
                orderMinutes,
                ruleFromMinutes,
                ruleToMinutes
            );

            if (!timeAllowed) {
                return {
                    successful: false,
                    reason: 'Program outside allowed hours.',
                };
            }

            return check;
        },
    });

    return models.Order;
});
