
(() => {
    "use strict";

    const ICON_SHOW = `
        <svg viewBox="0 0 24 24" fill="none"
             stroke="currentColor" stroke-width="1.8"
             stroke-linecap="round" stroke-linejoin="round"
             aria-hidden="true">
            <path d="M2 12s3.6-7 10-7 10 7 10 7-3.6 7-10 7S2 12 2 12Z"/>
            <circle cx="12" cy="12" r="3"/>
        </svg>
    `;

    const ICON_HIDE = `
        <svg viewBox="0 0 24 24" fill="none"
             stroke="currentColor" stroke-width="1.8"
             stroke-linecap="round" stroke-linejoin="round"
             aria-hidden="true">
            <path d="M3 3l18 18"/>
            <path d="M10.6 10.6a2 2 0 0 0 2.8 2.8"/>
            <path d="M9.9 5.2A10.8 10.8 0 0 1 12 5c6.4 0 10 7 10 7a16 16 0 0 1-3.1 3.8"/>
            <path d="M6.2 6.2C3.5 8 2 12 2 12s3.6 7 10 7c1.2 0 2.3-.2 3.3-.6"/>
        </svg>
    `;

    function actualizarBoton(button, mostrar) {
        button.innerHTML = mostrar ? ICON_HIDE : ICON_SHOW;

        button.setAttribute("aria-pressed", String(mostrar));

        button.setAttribute(
            "aria-label",
            mostrar ? "Ocultar contraseña" : "Mostrar contraseña"
        );

        button.setAttribute(
            "title",
            mostrar ? "Ocultar contraseña" : "Mostrar contraseña"
        );
    }

    function obtenerCampo(button) {
        const target = button.getAttribute("data-target");

        if (target) {
            return document.getElementById(target);
        }

        return button.closest(".passwordWrapper")?.querySelector("input");
    }

    function configurarContraseñas() {
        document.querySelectorAll(".togglePassword").forEach((button) => {
            button.type = "button";

            const input = obtenerCampo(button);

            if (!input) {
                console.error(
                    "No se encontró el campo de contraseña:",
                    button
                );
                return;
            }

            actualizarBoton(button, input.type === "text");
        });
    }

    function configurarEventos() {
        document.addEventListener("click", (event) => {
            const button = event.target.closest(".togglePassword");

            if (!button) return;

            event.preventDefault();

            const input = obtenerCampo(button);

            if (!input) return;

            const mostrar = input.type === "password";

            input.type = mostrar ? "text" : "password";

            actualizarBoton(button, mostrar);

            input.focus();
        });
    }

    function configurarLogos() {
        document.querySelectorAll(".brandLogo").forEach((logo) => {
            const contenedor = logo.closest(".visualLogo");

            if (!contenedor) return;

            const logoNoDisponible = () => {
                contenedor.classList.add("logoMissing");
            };

            logo.addEventListener("error", logoNoDisponible);

            if (logo.complete && logo.naturalWidth === 0) {
                logoNoDisponible();
            }
        });
    }

    function inicializar() {
        configurarContraseñas();
        configurarEventos();
        configurarLogos();
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", inicializar, {
            once: true
        });
    } else {
        inicializar();
    }
})();
