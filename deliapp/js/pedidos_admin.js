
/* =========================================================
   DELI AREPAS JD
   GESTIÓN DE PEDIDOS — INTERACCIONES
========================================================= */

document.addEventListener("DOMContentLoaded", () => {
    "use strict";

    const config = window.ORDERS_ADMIN_CONFIG || {};

    const modal = document.getElementById("orderModal");
    const closeModalButton = document.getElementById("closeOrderModal");
    const cancelModalButton = document.getElementById("cancelOrderEdit");
    const saveButton = document.getElementById("saveOrderChanges");
    const addProductButton = document.getElementById("addOrderProduct");

    const productEditor = document.getElementById("orderProductEditor");
    const modalOrderNumber = document.getElementById("modalOrderNumber");
    const modalCustomerName = document.getElementById("modalCustomerName");
    const modalOrderStatus = document.getElementById("modalOrderStatus");
    const modalOrderTotal = document.getElementById("modalOrderTotal");
    const modalFeedback = document.getElementById("modalFeedback");
    const toast = document.getElementById("ordersToast");

    const searchInput = document.getElementById("ordersSearch");
    const clearSearch = document.getElementById("clearSearch");
    const statusFilter = document.getElementById("ordersStatusFilter");
    const filterForm = document.getElementById("ordersFilterForm");
    const tableBody = document.getElementById("ordersTableBody");

    let currentOrderId = null;
    let availableProducts = [];
    let toastTimeout = null;

    const money = (value) => {
        return new Intl.NumberFormat("es-CO", {
            style: "currency",
            currency: "COP",
            maximumFractionDigits: 0
        }).format(Number(value) || 0);
    };

    const escapeHTML = (value) => {
        return String(value ?? "").replace(/[&<>"']/g, (character) => ({
            "&": "&amp;",
            "<": "&lt;",
            ">": "&gt;",
            '"': "&quot;",
            "'": "&#039;"
        })[character]);
    };

    function showToast(message) {
        toast.textContent = message;
        toast.classList.add("is-visible");

        clearTimeout(toastTimeout);

        toastTimeout = setTimeout(() => {
            toast.classList.remove("is-visible");
        }, 3400);
    }

    function getEditUrl(orderId) {
        if (!config.editUrlTemplate) {
            throw new Error("No está configurada la URL de edición.");
        }

        return config.editUrlTemplate.replace(/\/0\/editar\/?$/, `/${orderId}/editar/`);
    }

    async function requestOrder(orderId, method = "GET", data = null) {
        const options = {
            method,
            headers: {
                "X-Requested-With": "XMLHttpRequest"
            }
        };

        if (method === "POST") {
            options.headers["Content-Type"] = "application/json";
            options.headers["X-CSRFToken"] = config.csrfToken;
            options.body = JSON.stringify(data);
        }

        const response = await fetch(getEditUrl(orderId), options);

        let result;

        try {
            result = await response.json();
        } catch {
            throw new Error("El servidor devolvió una respuesta no válida.");
        }

        if (!response.ok) {
            throw new Error(result.error || "No se pudo completar la operación.");
        }

        return result;
    }

    function openModal() {
        modal.classList.add("is-open");
        modal.setAttribute("aria-hidden", "false");
        document.body.classList.add("order-modal-open");

        setTimeout(() => closeModalButton.focus(), 100);
    }

    function closeModal() {
        modal.classList.remove("is-open");
        modal.setAttribute("aria-hidden", "true");
        document.body.classList.remove("order-modal-open");

        currentOrderId = null;
    }

    function updateTotal() {
        let total = 0;

        productEditor.querySelectorAll(".order-product-row").forEach((row) => {
            const quantity = Number(row.querySelector(".product-quantity").value) || 0;
            const price = Number(row.querySelector(".product-price").value) || 0;
            const discount = Number(row.querySelector(".product-discount").value) || 0;

            const finalPrice = price * (1 - discount / 100);
            const subtotal = quantity * finalPrice;

            total += subtotal;

            row.querySelector(".product-subtotal").textContent = money(subtotal);
        });

        modalOrderTotal.textContent = money(total);
    }

    function renderProductRow(detail = {}) {
        const row = document.createElement("div");
        row.className = "order-product-row";

        const selectedId = String(detail.producto_id ?? "");
        const selectedProduct = availableProducts.find(
            product => String(product.id) === selectedId
        );

        let options = '<option value="">Seleccionar producto</option>';

        availableProducts.forEach((product) => {
            const selected = String(product.id) === selectedId ? "selected" : "";

            options += `
                <option value="${product.id}" ${selected}>
                    ${escapeHTML(product.nombre)} — Stock: ${product.stock}
                </option>
            `;
        });

        if (!selectedProduct && selectedId) {
            options += `
                <option value="${escapeHTML(selectedId)}" selected>
                    ${escapeHTML(detail.nombre || "Producto no disponible")}
                </option>
            `;
        }

        row.innerHTML = `
            <div class="order-product-field">
                <label>Producto</label>
                <select class="product-select">${options}</select>
            </div>

            <div class="order-product-field">
                <label>Cantidad</label>
                <input class="product-quantity" type="number"
                       min="1" step="1" value="${Number(detail.cantidad) || 1}">
            </div>

            <div class="order-product-field">
                <label>Precio base</label>
                <input class="product-price" type="number"
                       min="0" step="0.01"
                       value="${Number(detail.precio) || 0}">
            </div>

            <div class="order-product-field">
                <label>Descuento %</label>
                <input class="product-discount" type="number"
                       min="0" max="100" step="1"
                       value="${Number(detail.descuento) || 0}">
            </div>

            <div class="order-product-field">
                <label>Subtotal</label>
                <input class="product-subtotal" type="text"
                       readonly value="$0">
            </div>

            <button type="button" class="remove-product-button"
                    title="Eliminar producto" aria-label="Eliminar producto">×</button>
        `;

        const select = row.querySelector(".product-select");
        const priceInput = row.querySelector(".product-price");
        const discountInput = row.querySelector(".product-discount");

        select.addEventListener("change", () => {
            const product = availableProducts.find(
                item => String(item.id) === select.value
            );

            if (product) {
                priceInput.value = product.precio;
                discountInput.value = product.descuento;
            }

            updateTotal();
        });

        row.querySelectorAll("input").forEach((input) => {
            input.addEventListener("input", updateTotal);
        });

        row.querySelector(".remove-product-button").addEventListener("click", () => {
            row.remove();

            if (!productEditor.querySelector(".order-product-row")) {
                productEditor.innerHTML = `
                    <div class="editor-empty">
                        No hay productos. Utiliza el botón para agregar uno.
                    </div>
                `;
            }

            updateTotal();
        });

        const emptyMessage = productEditor.querySelector(".editor-empty");

        if (emptyMessage) {
            emptyMessage.remove();
        }

        productEditor.appendChild(row);
        updateTotal();
    }

    async function loadOrder(orderId) {
        currentOrderId = orderId;

        modalFeedback.textContent = "Cargando información...";
        productEditor.innerHTML = `
            <div class="editor-empty">Cargando productos del pedido...</div>
        `;

        modalOrderNumber.textContent = `#${orderId}`;
        modalCustomerName.textContent = "Cargando...";
        openModal();

        try {
            const data = await requestOrder(orderId);

            availableProducts = data.productos || [];

            modalOrderNumber.textContent = `#${data.id}`;
            modalCustomerName.textContent = data.cliente.nombre;
            modalOrderStatus.value = data.estado;

            productEditor.innerHTML = "";

            (data.detalles || []).forEach((detail) => {
                renderProductRow(detail);
            });

            if (!data.detalles || data.detalles.length === 0) {
                productEditor.innerHTML = `
                    <div class="editor-empty">
                        Este pedido todavía no tiene productos.
                    </div>
                `;
            }

            modalFeedback.textContent = "";
            updateTotal();

        } catch (error) {
            modalFeedback.textContent = error.message;
            showToast(error.message);
        }
    }

    async function saveOrder() {
        if (!currentOrderId) return;

        const rows = [...productEditor.querySelectorAll(".order-product-row")];

        if (!rows.length) {
            showToast("Agrega al menos un producto.");
            return;
        }

        const products = [];

        for (const row of rows) {
            const productoId = row.querySelector(".product-select").value;
            const cantidad = Number(row.querySelector(".product-quantity").value);
            const precio = Number(row.querySelector(".product-price").value);
            const descuento = Number(row.querySelector(".product-discount").value);

            if (!productoId || !Number.isInteger(Number(productoId))) {
                showToast("Selecciona todos los productos.");
                return;
            }

            if (!Number.isInteger(cantidad) || cantidad <= 0) {
                showToast("Las cantidades deben ser números enteros mayores que cero.");
                return;
            }

            if (!Number.isFinite(precio) || precio < 0) {
                showToast("Revisa los precios ingresados.");
                return;
            }

            if (!Number.isFinite(descuento) || descuento < 0 || descuento > 100) {
                showToast("El descuento debe estar entre 0 y 100.");
                return;
            }

            products.push({
                producto_id: Number(productoId),
                cantidad,
                precio,
                descuento
            });
        }

        const ids = products.map(product => product.producto_id);

        if (new Set(ids).size !== ids.length) {
            showToast("No repitas el mismo producto en varias filas.");
            return;
        }

        saveButton.disabled = true;
        saveButton.textContent = "Guardando...";
        modalFeedback.textContent = "Aplicando cambios...";

        try {
            const result = await requestOrder(currentOrderId, "POST", {
                productos: products,
                estado: modalOrderStatus.value
            });

            showToast(result.mensaje || "Pedido actualizado correctamente.");

            closeModal();

            // Refrescar la información para reflejar los cambios del servidor.
            window.location.reload();

        } catch (error) {
            modalFeedback.textContent = error.message;
            showToast(error.message);

        } finally {
            saveButton.disabled = false;
            saveButton.textContent = "Guardar cambios";
        }
    }

    // Abrir modal desde cada pedido.
    document.querySelectorAll(".edit-order-button").forEach((button) => {
        button.addEventListener("click", () => {
            loadOrder(button.dataset.orderId);
        });
    });

    // Añadir productos.
    addProductButton.addEventListener("click", () => {
        if (!availableProducts.length) {
            showToast("No hay productos disponibles para agregar.");
            return;
        }

        renderProductRow();
    });

    // Cerrar modal.
    closeModalButton.addEventListener("click", closeModal);
    cancelModalButton.addEventListener("click", closeModal);

    modal.addEventListener("click", (event) => {
        if (event.target === modal) {
            closeModal();
        }
    });

    document.addEventListener("keydown", (event) => {
        if (event.key === "Escape" && modal.classList.contains("is-open")) {
            closeModal();
        }
    });

    saveButton.addEventListener("click", saveOrder);

    // Búsqueda dinámica sobre los pedidos cargados en la tabla.
    function filterOrders() {
        const query = searchInput.value.trim().toLocaleLowerCase("es");
        const selectedStatus = statusFilter.value.toLowerCase();

        document.querySelectorAll(".order-row").forEach((row) => {
            const text = row.textContent.toLocaleLowerCase("es");
            const status = row.querySelector(".status-badge")
                ?.className.toLowerCase() || "";

            const matchesText = text.includes(query);

            const matchesStatus = !selectedStatus ||
                status.includes(selectedStatus.toLowerCase().replace("_", "_"));

            row.style.display = matchesText && matchesStatus ? "" : "none";
        });
    }

    searchInput.addEventListener("input", filterOrders);
    statusFilter.addEventListener("change", filterOrders);

    clearSearch.addEventListener("click", () => {
        searchInput.value = "";
        filterOrders();
        searchInput.focus();
    });

    filterForm.addEventListener("submit", (event) => {
        event.preventDefault();

        const params = new URLSearchParams();

        if (searchInput.value.trim()) {
            params.set("buscar", searchInput.value.trim());
        }

        if (statusFilter.value) {
            params.set("estado", statusFilter.value);
        }

        const query = params.toString();

        window.location.href = query
            ? `${window.location.pathname}?${query}`
            : window.location.pathname;
    });

    // Aplicar los filtros al cargar la página.
    filterOrders();
});
