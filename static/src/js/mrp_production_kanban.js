odoo.define('quemen.MrpProductionKanban', function (require) {
    'use strict';

    const core = require('web.core');
    const Dialog = require('web.Dialog');
    const KanbanRecord = require('web.KanbanRecord');

    const _t = core._t;

    KanbanRecord.include({
        events: _.extend({}, KanbanRecord.prototype.events, {
            'click .o_quemen_mrp_qty_input': '_onQuemenQtyInputClick',
            'keydown .o_quemen_mrp_qty_input': '_onQuemenQtyInputKeydown',
            'click .o_quemen_mrp_qty_save': '_onQuemenQtySave',
            'click .o_quemen_mrp_confirm_close': '_onQuemenConfirmAndClose',
        }),

        _getQuemenProductQty: function () {
            const input = this.$('.o_quemen_mrp_qty_input')[0];
            const quantity = input && input.valueAsNumber;
            if (!Number.isFinite(quantity) || quantity <= 0) {
                this.displayNotification({
                    title: _t('Cantidad no válida'),
                    message: _t('La cantidad a producir debe ser mayor que cero.'),
                    type: 'danger',
                });
                return false;
            }
            return quantity;
        },

        _onQuemenQtyInputClick: function (event) {
            event.stopPropagation();
        },

        _onQuemenQtyInputKeydown: function (event) {
            event.stopPropagation();
            if (event.key === 'Enter') {
                event.preventDefault();
                this._saveQuemenProductQty();
            }
        },

        _onQuemenQtySave: function (event) {
            event.preventDefault();
            event.stopPropagation();
            this._saveQuemenProductQty();
        },

        _saveQuemenProductQty: function () {
            const quantity = this._getQuemenProductQty();
            if (quantity === false) {
                return;
            }

            const self = this;
            const $controls = this.$('.o_quemen_mrp_qty_input, .o_quemen_mrp_qty_save');
            $controls.prop('disabled', true);
            return this._rpc({
                model: 'mrp.production',
                method: 'action_update_product_qty',
                args: [[this.id], quantity],
            }).then(function () {
                self.displayNotification({
                    message: _t('Cantidad actualizada.'),
                    type: 'success',
                });
                self.trigger_up('reload');
            }).catch(function (error) {
                $controls.prop('disabled', false);
                throw error;
            });
        },

        _onQuemenConfirmAndClose: function (event) {
            event.preventDefault();
            event.stopPropagation();

            const quantity = this._getQuemenProductQty();
            if (quantity === false) {
                return;
            }

            const self = this;
            Dialog.confirm(
                this,
                _t('Se aplicará la cantidad indicada y se cerrará la orden de producción.'),
                {
                    title: _t('Confirmar y cerrar'),
                    confirm_callback: function () {
                        const $controls = self.$(
                            '.o_quemen_mrp_qty_input, .o_quemen_mrp_qty_save, '
                            + '.o_quemen_mrp_confirm_close'
                        );
                        $controls.prop('disabled', true);
                        return self._rpc({
                            model: 'mrp.production',
                            method: 'action_confirm_and_close',
                            args: [[self.id], quantity],
                        }).then(function (action) {
                            if (action && action.type) {
                                return self.do_action(action, {
                                    on_close: function () {
                                        self.trigger_up('reload');
                                    },
                                });
                            }
                            self.trigger_up('reload');
                        }).catch(function (error) {
                            $controls.prop('disabled', false);
                            throw error;
                        });
                    },
                }
            );
        },
    });
});
