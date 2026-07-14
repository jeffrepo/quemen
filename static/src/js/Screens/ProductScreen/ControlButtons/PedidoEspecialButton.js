/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";
import { AlertDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { makeAwaitable } from "@point_of_sale/app/utils/make_awaitable_dialog";
import { ControlButtons } from "@point_of_sale/app/screens/product_screen/control_buttons/control_buttons";
import { PedidoEspecialPopup } from "../../../Popups/PedidoEspecialPopup";

patch(ControlButtons.prototype, {
    async clickPedidoEspecial() {
        const order = this.currentOrder;
        if (!order || order.isEmpty()) {
            this.dialog.add(AlertDialog, {
                title: _t("Pedido especial"),
                body: _t("Agregue al menos un producto antes de registrar el pedido especial."),
            });
            return;
        }

        const selectedOrderline = order.getSelectedOrderline() || order.getLastOrderline();
        if (!selectedOrderline) {
            this.dialog.add(AlertDialog, {
                title: _t("Pedido especial"),
                body: _t("Seleccione una linea del pedido para marcarla como producto especial."),
            });
            return;
        }

        const payload = await makeAwaitable(this.dialog, PedidoEspecialPopup, {
            title: _t("Pedido especial"),
            order,
        });
        if (!payload) {
            return;
        }

        selectedOrderline.set_producto_especial(true);
        order.setPedidoEspecial(payload);

        if (this.props.close) {
            this.props.close();
        }
    },
});
