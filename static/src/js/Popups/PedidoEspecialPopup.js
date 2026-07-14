/** @odoo-module **/

import { Component, useState } from "@odoo/owl";
import { Dialog } from "@web/core/dialog/dialog";
import { _t } from "@web/core/l10n/translation";

function initialValue(order, getterName) {
    return order?.[getterName]?.() || "";
}

export class PedidoEspecialPopup extends Component {
    static template = "quemen.PedidoEspecialPopup";
    static components = { Dialog };
    static props = {
        title: { type: String, optional: true },
        order: { type: Object, optional: true },
        getPayload: Function,
        close: Function,
    };
    static defaultProps = {
        title: _t("Pedido especial"),
    };

    setup() {
        const order = this.props.order;
        this.state = useState({
            fecha: initialValue(order, "get_fecha"),
            hora: initialValue(order, "get_hora"),
            observaciones: initialValue(order, "get_observaciones"),
            sucursal_entrega: initialValue(order, "get_entrega"),
            autorizo: initialValue(order, "get_autorizo"),
        });
    }

    get isValid() {
        return Boolean(this.state.fecha && this.state.hora && this.state.autorizo.trim());
    }

    confirm() {
        if (!this.isValid) {
            return;
        }
        this.props.getPayload({
            fecha: this.state.fecha,
            hora: this.state.hora,
            observaciones: this.state.observaciones,
            sucursal_entrega: this.state.sucursal_entrega,
            autorizo: this.state.autorizo,
        });
        this.props.close();
    }

    cancel() {
        this.props.close();
    }
}
