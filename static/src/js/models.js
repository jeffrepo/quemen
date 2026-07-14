/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { PosOrder } from "@point_of_sale/app/models/pos_order";
import { PosOrderline } from "@point_of_sale/app/models/pos_order_line";

function cleanText(value) {
    return (value || "").toString().trim();
}

function formatDateForTicket(value) {
    if (!value) {
        return "";
    }
    const [year, month, day] = value.split("-");
    return year && month && day ? `${day}/${month}/${year}` : value;
}

function nowForTicket() {
    const now = new Date();
    const pad = (value) => String(value).padStart(2, "0");
    return `${pad(now.getDate())}/${pad(now.getMonth() + 1)}/${now.getFullYear()} ${pad(
        now.getHours()
    )}:${pad(now.getMinutes())}`;
}

patch(PosOrderline.prototype, {
    setup(vals) {
        super.setup(...arguments);
        this.producto_especial =
            vals?.producto_especial || this.producto_especial || this.uiState?.productoEspecial || false;
    },

    set_producto_especial(productoEspecial) {
        this.producto_especial = Boolean(productoEspecial);
        this.uiState.productoEspecial = this.producto_especial;
        this._markDirty();
    },

    get_producto_especial() {
        return Boolean(this.producto_especial || this.uiState?.productoEspecial);
    },
});

patch(PosOrder.prototype, {
    setup(vals) {
        super.setup(...arguments);
        this.tipo_venta = vals?.tipo_venta || this.tipo_venta || false;
        this.pedido_especial = vals?.pedido_especial || this.pedido_especial || false;
        this.fecha_especial = vals?.fecha_especial || this.fecha_especial || false;
        this.hora_especial = vals?.hora_especial || this.hora_especial || "";
        this.observaciones_especial =
            vals?.observaciones_especial || this.observaciones_especial || "";
        this.sucursal_entrega = vals?.sucursal_entrega || this.sucursal_entrega || "";
        this.autorizo_especial = vals?.autorizo_especial || this.autorizo_especial || "";
        this.fecha_hora_pedido_especial =
            vals?.fecha_hora_pedido_especial || this.fecha_hora_pedido_especial || "";
    },

    setPedidoEspecial(payload = {}) {
        this.tipo_venta = "especial";
        this.pedido_especial = true;
        this.fecha_especial = payload.fecha || false;
        this.hora_especial = cleanText(payload.hora);
        this.observaciones_especial = cleanText(payload.observaciones);
        this.sucursal_entrega = cleanText(payload.sucursal_entrega);
        this.autorizo_especial = cleanText(payload.autorizo);
        this.fecha_hora_pedido_especial = payload.fecha_hora_actual || nowForTicket();
        this._markDirty();
    },

    get_fecha() {
        return this.fecha_especial;
    },

    get_hora() {
        return this.hora_especial;
    },

    get_observaciones() {
        return this.observaciones_especial;
    },

    get_autorizo() {
        return this.autorizo_especial;
    },

    get_entrega() {
        return this.sucursal_entrega;
    },

    get_fecha_formato() {
        return formatDateForTicket(this.fecha_especial);
    },

    get_fecha_hora_actual() {
        return this.fecha_hora_pedido_especial || nowForTicket();
    },

    get_terminos_condiciones() {
        return this.config?.terminos_condiciones || "";
    },

    get_dicc_prod_especiales() {
        const productos = {};
        for (const line of this.lines || []) {
            if (!line.get_producto_especial?.()) {
                continue;
            }
            const product = line.getProduct();
            if (!product) {
                continue;
            }
            const productId = product.id;
            if (!productos[productId]) {
                productos[productId] = {
                    nombre_producto: product.display_name || product.name,
                    cantidad: 0,
                    precio_unitario: line.price_unit,
                    precio_unitario_con_iva: line.displayPriceUnitIncl,
                    precio_total: 0,
                    total_con_iva: 0,
                    estado: false,
                };
            }
            productos[productId].cantidad += line.getQuantity();
            productos[productId].precio_total += line.priceExcl;
            productos[productId].total_con_iva += line.priceIncl;
        }
        return productos;
    },

    get_dicc_total() {
        return {
            sub_total: this.priceExcl,
            total_iva: this.amountTaxes,
            total: this.priceIncl,
        };
    },

    getPedidoEspecialTicketData() {
        return {
            pedido_especial: this.pedido_especial,
            fecha: this.get_fecha(),
            hora: this.get_hora(),
            fecha_formato: this.get_fecha_formato(),
            fecha_hora_actual: this.get_fecha_hora_actual(),
            observaciones: this.get_observaciones(),
            sucursal_entrega: this.get_entrega(),
            autorizo: this.get_autorizo(),
            productos: this.get_dicc_prod_especiales(),
            totales: this.get_dicc_total(),
            terminos_condiciones: this.get_terminos_condiciones(),
        };
    },

    serializeForORM(opts = {}) {
        const data = super.serializeForORM(...arguments);
        if (
            this.pedido_especial ||
            this.fecha_especial ||
            this.hora_especial ||
            this.observaciones_especial ||
            this.sucursal_entrega ||
            this.autorizo_especial
        ) {
            data.tipo_venta = "especial";
            data.pedido_especial = true;
            data.fecha_especial = this.fecha_especial || false;
            data.hora_especial = this.hora_especial || false;
            data.observaciones_especial = this.observaciones_especial || false;
            data.sucursal_entrega = this.sucursal_entrega || false;
            data.autorizo_especial = this.autorizo_especial || false;
        }
        return data;
    },
});
