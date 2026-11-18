
(() => {
    "use strict";

    const CART_KEY = "deli_arepas_jd_carrito";

    const $ = (selector, parent = document) =>
        parent.querySelector(selector);

    const $$ = (selector, parent = document) =>
        [...parent.querySelectorAll(selector)];

    const dinero = new Intl.NumberFormat("es-CO", {
        style: "currency",
        currency: "COP",
        maximumFractionDigits: 0
    });

    const elementos = {
        carrito: $("#cartDrawer"),
        overlay: $("#cartOverlay"),
        abrir: $("#openCart"),
        cerrar: $("#closeCart"),
        lista: $("#cartItems"),
        vacio: $("#cartEmpty"),
        contenido: $("#cartContent"),
        contador: $("#cartCount"),
        total: $("#cartTotal"),
        subtotal: $("#cartSubtotal"),
        formulario: $("#checkoutForm"),
        nombre: $("#checkoutName"),
        telefono: $("#checkoutPhone"),
        direccion: $("#checkoutAddress"),
        observaciones: $("#checkoutNotes"),
        confirmar: $("#confirmOrder"),
        notificacion: $("#menuToast"),
        resultado: $("#orderSuccess")
    };

    let carrito = cargarCarrito();
    let enviando = false;
    let temporizadorToast;

    function cargarCarrito() {
        try {
            const datos = JSON.parse(localStorage.getItem(CART_KEY) || "[]");
            return Array.isArray(datos) ? datos : [];
        } catch {
            return [];
        }
    }

    function guardarCarrito() {
        localStorage.setItem(CART_KEY, JSON.stringify(carrito));
    }

    function precioFinal(precio, descuento) {
        return Math.round(
            Number(precio) * (1 - Number(descuento) / 100)
        );
    }

    function totalUnidades() {
        return carrito.reduce((total, item) => total + item.cantidad, 0);
    }

    function totalCarrito() {
        return carrito.reduce(
            (total, item) => total + item.precioFinal * item.cantidad,
            0
        );
    }

    function mostrarToast(mensaje) {
        if (!elementos.notificacion) return;

        elementos.notificacion.textContent = mensaje;
        elementos.notificacion.classList.add("show");

        clearTimeout(temporizadorToast);

        temporizadorToast = setTimeout(() => {
            elementos.notificacion.classList.remove("show");
        }, 2600);
    }

    function actualizarContador() {
        if (elementos.contador) {
            elementos.contador.textContent = totalUnidades();
            elementos.contador.classList.toggle(
                "has-items",
                totalUnidades() > 0
            );
        }
    }

    function renderizarCarrito() {
        if (!elementos.lista) return;

        elementos.lista.replaceChildren();

        const estaVacio = carrito.length === 0;

        elementos.vacio.hidden = !estaVacio;
        elementos.contenido.hidden = estaVacio;

        carrito.forEach(item => {
            const fila = document.createElement("article");
            fila.className = "cart-item";

            const imagen = document.createElement("img");
            imagen.className = "cart-item-image";
            imagen.src = item.imagen || "/static/deliapp/img/arepa3.jpg";
            imagen.alt = item.nombre;
            imagen.onerror = () => {
                imagen.src = "/static/deliapp/img/arepa3.jpg";
            };

            const informacion = document.createElement("div");
            informacion.className = "cart-item-info";

            const nombre = document.createElement("h4");
            nombre.textContent = item.nombre;

            const precio = document.createElement("span");
            precio.className = "cart-item-price";
            precio.textContent = dinero.format(
                item.precioFinal * item.cantidad
            );

            const controles = document.createElement("div");
            controles.className = "cart-quantity";

            const menos = document.createElement("button");
            menos.type = "button";
            menos.textContent = "−";
            menos.setAttribute("aria-label", `Disminuir ${item.nombre}`);
            menos.disabled = item.cantidad <= 1;
            menos.addEventListener("click", () => {
                cambiarCantidad(item.id, -1);
            });

            const cantidad = document.createElement("span");
            cantidad.textContent = item.cantidad;

            const mas = document.createElement("button");
            mas.type = "button";
            mas.textContent = "+";
            mas.setAttribute("aria-label", `Aumentar ${item.nombre}`);
            mas.disabled = item.cantidad >= item.stock;
            mas.addEventListener("click", () => {
                cambiarCantidad(item.id, 1);
            });

            controles.append(menos, cantidad, mas);
            informacion.append(nombre, precio, controles);

            const eliminar = document.createElement("button");
            eliminar.type = "button";
            eliminar.className = "cart-remove";
            eliminar.textContent = "Eliminar";
            eliminar.addEventListener("click", () => {
                eliminarProducto(item.id);
            });

            fila.append(imagen, informacion, eliminar);
            elementos.lista.append(fila);
        });

        const total = dinero.format(totalCarrito());

        if (elementos.total) elementos.total.textContent = total;
        if (elementos.subtotal) elementos.subtotal.textContent = total;

        actualizarContador();
        guardarCarrito();
    }

    function agregarProducto(datos) {
        const id = Number(datos.id);
        const stock = Number(datos.stock);
        const precio = Number(datos.precio);
        const descuento = Number(datos.descuento || 0);

        if (
            !id ||
            !Number.isFinite(stock) ||
            stock <= 0 ||
            !Number.isFinite(precio) ||
            precio < 0
        ) {
            mostrarToast("Este producto no está disponible.");
            return;
        }

        const existente = carrito.find(item => item.id === id);

        if (existente) {
            if (existente.cantidad >= stock) {
                mostrarToast("Has alcanzado el máximo disponible.");
                return;
            }

            existente.cantidad += 1;
            existente.stock = stock;
        } else {
            carrito.push({
                id,
                nombre: datos.nombre,
                precio,
                descuento,
                precioFinal: precioFinal(precio, descuento),
                stock,
                imagen: datos.imagen || "",
                cantidad: 1
            });
        }

        renderizarCarrito();
        mostrarToast(`${datos.nombre} se agregó a tu pedido.`);
    }

    function cambiarCantidad(id, cambio) {
        const item = carrito.find(producto => producto.id === id);
        if (!item) return;

        const nuevaCantidad = item.cantidad + cambio;

        if (nuevaCantidad < 1 || nuevaCantidad > item.stock) return;

        item.cantidad = nuevaCantidad;
        renderizarCarrito();
    }

    function eliminarProducto(id) {
        carrito = carrito.filter(item => item.id !== id);
        renderizarCarrito();
        mostrarToast("Producto eliminado del carrito.");
    }

    function abrirCarrito() {
        elementos.overlay.hidden = false;
        document.body.classList.add("cart-is-open");
        elementos.cerrar?.focus();
    }

    function cerrarCarrito() {
        elementos.overlay.hidden = true;
        document.body.classList.remove("cart-is-open");
        elementos.abrir?.focus();
    }

    function obtenerCSRF() {
        const campo = $('input[name="csrfmiddlewaretoken"]');
        return campo?.value || "";
    }

    async function confirmarPedido(event) {
        event.preventDefault();

        if (enviando || carrito.length === 0) return;

        if (!elementos.formulario.reportValidity()) return;

        enviando = true;
        elementos.confirmar.disabled = true;
        elementos.confirmar.textContent = "Registrando pedido...";

        try {
            const respuesta = await fetch(
                elementos.formulario.dataset.endpoint,
                {
                    method: "POST",
                    headers: {
                        "Content-Type": "application/json",
                        "X-CSRFToken": obtenerCSRF()
                    },
                    body: JSON.stringify({
                        clienteNombre: elementos.nombre.value.trim(),
                        telefono: elementos.telefono.value.trim(),
                        direccion: elementos.direccion.value.trim(),
                        observaciones: elementos.observaciones.value.trim(),
                        items: carrito.map(item => ({
                            productoId: item.id,
                            cantidad: item.cantidad
                        }))
                    })
                }
            );

            const datos = await respuesta.json();

            if (!respuesta.ok) {
                throw new Error(
                    datos.error || "No se pudo registrar el pedido."
                );
            }

            carrito = [];
            guardarCarrito();
            renderizarCarrito();

            elementos.formulario.reset();
            mostrarResultado(datos);

            document.dispatchEvent(
                new CustomEvent("deli:pedido-confirmado", {
                    detail: datos
                })
            );

        } catch (error) {
            mostrarToast(error.message || "Ocurrió un error.");
        } finally {
            enviando = false;
            elementos.confirmar.disabled = false;
            elementos.confirmar.textContent = "Confirmar pedido";
        }
    }

    function mostrarResultado(datos) {
        if (!elementos.resultado) return;

        $("#successOrderId", elementos.resultado).textContent = `#${datos.id}`;
        $("#successOrderTotal", elementos.resultado).textContent =
            dinero.format(datos.total);

        elementos.resultado.hidden = false;
        elementos.contenido.hidden = true;
        elementos.vacio.hidden = true;
    }

    function reiniciarCarrito() {
        elementos.resultado.hidden = true;
        cerrarCarrito();
    }

    // Botones para agregar productos.
    $$(".product-button:not(.disabled)").forEach(boton => {
        boton.addEventListener("click", () => {
            const tarjeta = boton.closest(".product-card");
            const imagen = $(".product-image", tarjeta);

            agregarProducto({
                id: boton.dataset.productId,
                nombre: boton.dataset.productName,
                precio: boton.dataset.productPrice,
                descuento: boton.dataset.productDiscount,
                stock: boton.dataset.productStock,
                imagen: imagen?.getAttribute("src") || ""
            });
        });
    });

    // Filtros y búsqueda.
    const buscador = $("#productSearch");
    const limpiar = $("#clearSearch");
    const botonesCategoria = $$(".category-button");
    const tarjetas = $$(".product-card");
    const sinResultados = $("#noSearchResults");

    let categoriaActiva = "todos";

    function filtrarProductos() {
        const texto = (buscador?.value || "").trim().toLowerCase();
        let visibles = 0;

        tarjetas.forEach(tarjeta => {
            const nombre = tarjeta.dataset.name || "";
            const categoria = tarjeta.dataset.category || "";

            const coincideTexto = nombre.includes(texto);
            const coincideCategoria =
                categoriaActiva === "todos" ||
                categoria === categoriaActiva;

            const mostrar = coincideTexto && coincideCategoria;

            tarjeta.hidden = !mostrar;
            if (mostrar) visibles++;
        });

        if (sinResultados) sinResultados.hidden = visibles > 0;
        if (limpiar) limpiar.hidden = texto.length === 0;
    }

    buscador?.addEventListener("input", filtrarProductos);

    limpiar?.addEventListener("click", () => {
        buscador.value = "";
        filtrarProductos();
        buscador.focus();
    });

    botonesCategoria.forEach(boton => {
        boton.addEventListener("click", () => {
            botonesCategoria.forEach(item =>
                item.classList.remove("active")
            );

            boton.classList.add("active");
            categoriaActiva = boton.dataset.category || "todos";
            filtrarProductos();
        });
    });

    // Carrito.
    elementos.abrir?.addEventListener("click", abrirCarrito);
    elementos.cerrar?.addEventListener("click", cerrarCarrito);

    elementos.overlay?.addEventListener("click", event => {
        if (event.target === elementos.overlay) cerrarCarrito();
    });

    document.addEventListener("keydown", event => {
        if (event.key === "Escape" && !elementos.overlay.hidden) {
            cerrarCarrito();
        }
    });

    elementos.formulario?.addEventListener("submit", confirmarPedido);

    $("#continueShopping")?.addEventListener("click", reiniciarCarrito);

    $("#clearCart")?.addEventListener("click", () => {
        if (!carrito.length) return;

        if (confirm("¿Deseas vaciar todo el carrito?")) {
            carrito = [];
            renderizarCarrito();
            mostrarToast("Tu carrito está vacío.");
        }
    });

    // Compatibilidad con el evento personalizado anterior.
    window.addEventListener("deli:agregar-producto", event => {
        const datos = event.detail || {};
        const boton = $(
            `.product-button[data-product-id="${CSS.escape(String(datos.productoId))}"]`
        );

        if (!boton) return;

        const tarjeta = boton.closest(".product-card");
        const imagen = $(".product-image", tarjeta);

        agregarProducto({
            id: datos.productoId,
            nombre: datos.nombre,
            precio: datos.precio,
            descuento: datos.descuento,
            stock: boton.dataset.productStock,
            imagen: imagen?.getAttribute("src") || ""
        });
    });

    renderizarCarrito();
})();
