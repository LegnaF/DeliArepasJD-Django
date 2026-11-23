
from .correos import enviar_correo_deli

import hashlib
import json
import uuid
from datetime import timedelta
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from urllib.parse import urlencode

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import user_passes_test
from django.db import transaction
from django.db.models import Sum, Q, F
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods, require_POST

from .forms import PQRForm
from .models import (
    PedidoEstado,
    cliente,
    detallepedido,
    pedido,
    pqr,
    producto,
)

User = get_user_model()


# =========================================================
# CONFIGURACIÓN GENERAL Y UTILIDADES
# =========================================================

CENTAVOS = Decimal("0.01")
CIEN = Decimal("100")


def _decimal(valor, defecto=None):
    """
    Convierte un valor a Decimal sin perder precisión innecesariamente.
    """
    try:
        return Decimal(str(valor))
    except (InvalidOperation, TypeError, ValueError):
        return defecto


def _dinero(valor):
    """
    Redondea un valor monetario a dos decimales.
    """
    return _decimal(valor, Decimal("0.00")).quantize(
        CENTAVOS,
        rounding=ROUND_HALF_UP
    )


def _precio_con_descuento(precio, descuento):
    """
    Calcula el precio final de un producto.
    """
    precio = _decimal(precio)
    descuento = _decimal(descuento, Decimal("0"))

    if precio is None or descuento is None:
        raise ValueError("El precio o descuento no es válido.")

    if precio < 0:
        raise ValueError("El precio no puede ser negativo.")

    if descuento < 0 or descuento > CIEN:
        raise ValueError("El descuento debe estar entre 0 y 100.")

    return _dinero(
        precio * (Decimal("1") - descuento / CIEN)
    )


def _respuesta_error(mensaje, status=400):
    return JsonResponse(
        {"error": mensaje},
        status=status
    )


def _leer_json(request):
    """
    Lee y valida el cuerpo JSON de una solicitud.
    """
    try:
        datos = json.loads(request.body or "{}")
    except (json.JSONDecodeError, UnicodeDecodeError):
        raise ValueError("Los datos enviados no tienen un formato válido.")

    if not isinstance(datos, dict):
        raise ValueError("Los datos enviados no son válidos.")

    return datos


# =========================================================
# PERMISOS Y ROLES
# =========================================================

def es_administrador(user):
    return user.is_authenticated and user.is_superuser


def es_empleado(user):
    return (
        user.is_authenticated
        and user.is_staff
        and not user.is_superuser
    )


def es_empleado_o_admin(user):
    return (
        user.is_authenticated
        and (user.is_staff or user.is_superuser)
    )


solo_administrador = user_passes_test(
    es_administrador,
    login_url="login"
)

solo_empleado = user_passes_test(
    es_empleado,
    login_url="login"
)

solo_empleado_o_admin = user_passes_test(
    es_empleado_o_admin,
    login_url="login"
)


def _obtener_rol_usuario(user):
    if user.is_superuser:
        return "ADMIN"

    if user.is_staff:
        return "EMPLEADO"

    return "CLIENTE"


def _asignar_rol_usuario(user, rol):
    rol = str(rol).strip().upper()

    if rol == "ADMIN":
        user.is_superuser = True
        user.is_staff = True

    elif rol == "EMPLEADO":
        user.is_superuser = False
        user.is_staff = True

    elif rol == "CLIENTE":
        user.is_superuser = False
        user.is_staff = False

    else:
        raise ValueError("El rol seleccionado no es válido.")


# =========================================================
# INVENTARIO Y ESTADOS DE PEDIDOS
# =========================================================

def _cambiar_estado_pedido_con_inventario(pedido_id, nuevo_estado):
    """
    Actualiza el estado y sincroniza el inventario.

    Los pedidos cancelados no reservan inventario.
    Los demás estados mantienen las unidades reservadas.
    """

    if nuevo_estado not in PedidoEstado.values:
        raise ValueError("El estado seleccionado no es válido.")

    with transaction.atomic():

        pedido_actual = pedido.objects.select_for_update().get(
            id=pedido_id
        )

        estado_anterior = pedido_actual.estado

        if estado_anterior == nuevo_estado:
            return pedido_actual

        detalles = list(
            detallepedido.objects.filter(
                pedido=pedido_actual
            ).order_by("producto_id")
        )

        ids_productos = sorted({
            detalle.producto_id
            for detalle in detalles
        })

        productos_bloqueados = {
            prod.id: prod
            for prod in producto.objects.select_for_update().filter(
                id__in=ids_productos
            ).order_by("id")
        }

        if len(productos_bloqueados) != len(ids_productos):
            raise ValueError(
                "No se pudieron localizar todos los productos del pedido."
            )

        # Pedido activo -> cancelado.
        # Se devuelve el inventario.
        if (
            estado_anterior != PedidoEstado.CANCELADO
            and nuevo_estado == PedidoEstado.CANCELADO
        ):
            for detalle in detalles:
                prod = productos_bloqueados[detalle.producto_id]
                prod.stock += detalle.cantidad

        # Pedido cancelado -> activo.
        # Se comprueba y reserva nuevamente el inventario.
        elif (
            estado_anterior == PedidoEstado.CANCELADO
            and nuevo_estado != PedidoEstado.CANCELADO
        ):
            for detalle in detalles:
                prod = productos_bloqueados[detalle.producto_id]

                if not prod.activo:
                    raise ValueError(
                        f'El producto "{prod.nombre}" está inactivo.'
                    )

                if detalle.cantidad > prod.stock:
                    raise ValueError(
                        f'Stock insuficiente para "{prod.nombre}". '
                        f"Disponibles: {prod.stock}; "
                        f"requeridas: {detalle.cantidad}."
                    )

            for detalle in detalles:
                prod = productos_bloqueados[detalle.producto_id]
                prod.stock -= detalle.cantidad

        for prod in productos_bloqueados.values():
            prod.save(update_fields=["stock"])

        pedido_actual.estado = nuevo_estado
        pedido_actual.save(update_fields=["estado"])

        return pedido_actual


def _reemplazar_detalles_pedido(
    pedido_id,
    cantidades,
    estado_nuevo,
    precios_personalizados=None
):
    """
    Reemplaza todos los productos de un pedido y actualiza su total.

    Si el pedido anterior estaba activo, primero devuelve sus unidades.
    Si el nuevo estado no es cancelado, reserva las nuevas cantidades.
    Si el nuevo estado es cancelado, no descuenta inventario.

    precios_personalizados:
        Diccionario opcional {producto_id: precio_final}.
        Si no se proporciona un precio, se conserva el histórico
        o se calcula con el precio y descuento actuales.
    """

    if estado_nuevo not in PedidoEstado.values:
        raise ValueError("El estado seleccionado no es válido.")

    if not cantidades:
        raise ValueError("El pedido debe contener al menos un producto.")

    precios_personalizados = precios_personalizados or {}

    with transaction.atomic():

        pedido_actual = pedido.objects.select_for_update().get(
            id=pedido_id
        )

        estado_anterior = pedido_actual.estado

        detalles_anteriores = list(
            detallepedido.objects.filter(
                pedido=pedido_actual
            ).order_by("producto_id")
        )

        ids_anteriores = {
            detalle.producto_id
            for detalle in detalles_anteriores
        }

        ids_nuevos = set(cantidades.keys())

        ids_involucrados = sorted(
            ids_anteriores | ids_nuevos
        )

        productos_bloqueados = {
            prod.id: prod
            for prod in producto.objects.select_for_update().filter(
                id__in=ids_involucrados
            ).order_by("id")
        }

        if len(productos_bloqueados) != len(ids_involucrados):
            raise ValueError(
                "Uno de los productos seleccionados ya no existe."
            )

        precios_historicos = {}

        for detalle in detalles_anteriores:
            precios_historicos[detalle.producto_id] = _dinero(
                detalle.precioUnit
            )

        # Recuperar stock anterior únicamente si estaba reservado.
        if estado_anterior != PedidoEstado.CANCELADO:
            for detalle in detalles_anteriores:
                prod = productos_bloqueados[detalle.producto_id]
                prod.stock += detalle.cantidad

        # Calcular los precios y validar productos.
        nuevos_detalles = []
        nuevo_total = Decimal("0.00")

        for producto_id, cantidad in cantidades.items():

            prod = productos_bloqueados[producto_id]

            if cantidad <= 0:
                raise ValueError(
                    "Las cantidades deben ser mayores que cero."
                )

            es_producto_nuevo = producto_id not in ids_anteriores

            necesita_reservar = (
                estado_nuevo != PedidoEstado.CANCELADO
            )

            if es_producto_nuevo and not prod.activo:
                raise ValueError(
                    f'El producto "{prod.nombre}" está inactivo.'
                )

            if (
                estado_anterior == PedidoEstado.CANCELADO
                and necesita_reservar
                and not prod.activo
            ):
                raise ValueError(
                    f'El producto "{prod.nombre}" está inactivo '
                    "y no se puede reactivar el pedido."
                )

            if producto_id in precios_personalizados:
                precio_final = _dinero(
                    precios_personalizados[producto_id]
                )

            elif producto_id in precios_historicos:
                precio_final = precios_historicos[producto_id]

            else:
                precio_final = _precio_con_descuento(
                    prod.precio,
                    prod.descuento
                )

            if precio_final < 0:
                raise ValueError("El precio no puede ser negativo.")

            nuevos_detalles.append({
                "producto": prod,
                "cantidad": cantidad,
                "precio": precio_final,
            })

            nuevo_total += precio_final * cantidad

        # Comprobar stock antes de descontar.
        if estado_nuevo != PedidoEstado.CANCELADO:

            for detalle in nuevos_detalles:
                prod = detalle["producto"]
                cantidad = detalle["cantidad"]

                if cantidad > prod.stock:
                    raise ValueError(
                        f'Stock insuficiente para "{prod.nombre}". '
                        f"Disponibles: {prod.stock}; "
                        f"requeridas: {cantidad}."
                    )

        # Eliminar los detalles anteriores.
        detallepedido.objects.filter(
            pedido=pedido_actual
        ).delete()

        # Crear los nuevos detalles.
        for detalle in nuevos_detalles:

            prod = detalle["producto"]
            cantidad = detalle["cantidad"]
            precio_final = detalle["precio"]

            detallepedido.objects.create(
                pedido=pedido_actual,
                producto=prod,
                cantidad=cantidad,
                precioUnit=float(precio_final)
            )

            # Descontar solamente si el pedido no está cancelado.
            if estado_nuevo != PedidoEstado.CANCELADO:
                prod.stock -= cantidad

        # Guardar inventario.
        for prod in productos_bloqueados.values():
            prod.save(update_fields=["stock"])

        nuevo_total = _dinero(nuevo_total)

        pedido_actual.estado = estado_nuevo
        pedido_actual.total = float(nuevo_total)

        pedido_actual.save(
            update_fields=["estado", "total"]
        )

        return pedido_actual


# =========================================================
# INICIO
# =========================================================

def home_page(request):

    if request.method == "POST":
        form = PQRForm(request.POST)

        if form.is_valid():
            form.save()

            messages.success(
                request,
                "¡Mensaje enviado con éxito! Nos pondremos en contacto pronto."
            )

            return redirect("inicio")

        messages.error(
            request,
            "No se pudo enviar el mensaje. Verifica los datos ingresados."
        )

    else:
        form = PQRForm()

    productos_destacados = producto.objects.filter(
        activo=True
    ).order_by("-id")[:4]

    return render(
        request,
        "deliapp/index.html",
        {
            "form": form,
            "productos": productos_destacados,
        }
    )


# =========================================================
# MENÚ
# =========================================================

def menu_page(request):

    productos = producto.objects.filter(
        activo=True
    ).order_by("nombre")

    categorias_bd = (
        producto.objects
        .filter(activo=True)
        .values_list("categoria", flat=True)
        .distinct()
    )

    categorias = ["Todos"] + list(categorias_bd)

    return render(
        request,
        "deliapp/menu.html",
        {
            "productos": productos,
            "categorias": categorias,
        }
    )


# =========================================================
# DETALLE DEL PRODUCTO
# =========================================================

def detalle_producto(request, id):

    prod = get_object_or_404(
        producto,
        id=id,
        activo=True
    )

    return render(
        request,
        "deliapp/detalle_producto.html",
        {"producto": prod}
    )


# =========================================================
# REGISTRO DE PEDIDOS
# =========================================================

@require_POST
def crear_pedido(request):

    try:
        datos = _leer_json(request)
    except ValueError as error:
        return _respuesta_error(str(error))

    nombre = str(datos.get("clienteNombre", "")).strip()
    telefono = str(datos.get("telefono", "")).strip()
    direccion = str(datos.get("direccion", "")).strip()
    items = datos.get("items", [])

    if not nombre or not telefono or not direccion:
        return _respuesta_error(
            "Debes completar nombre, teléfono y dirección."
        )

    if not isinstance(items, list) or not items:
        return _respuesta_error(
            "Tu carrito no contiene productos."
        )

    cantidades = {}

    for item in items:

        if not isinstance(item, dict):
            return _respuesta_error(
                "Hay un producto con información incorrecta."
            )

        try:
            producto_id = int(item.get("productoId"))
            cantidad = int(item.get("cantidad"))
        except (TypeError, ValueError):
            return _respuesta_error(
                "Hay un producto con identificación o cantidad inválida."
            )

        if producto_id <= 0 or cantidad <= 0:
            return _respuesta_error(
                "Las cantidades deben ser mayores que cero."
            )

        cantidades[producto_id] = (
            cantidades.get(producto_id, 0) + cantidad
        )

    try:

        with transaction.atomic():

            productos_bloqueados = {
                prod.id: prod
                for prod in producto.objects.select_for_update().filter(
                    id__in=sorted(cantidades.keys())
                ).order_by("id")
            }

            if len(productos_bloqueados) != len(cantidades):
                raise ValueError(
                    "Uno o más productos ya no están disponibles."
                )

            total = Decimal("0.00")
            detalles_nuevos = []

            for producto_id, cantidad in cantidades.items():

                prod = productos_bloqueados[producto_id]

                if not prod.activo:
                    raise ValueError(
                        f"El producto {prod.nombre} ya no está disponible."
                    )

                if cantidad > prod.stock:
                    raise ValueError(
                        f"No hay suficientes unidades de {prod.nombre}. "
                        f"Disponibles: {prod.stock}."
                    )

                precio_final = _precio_con_descuento(
                    prod.precio,
                    prod.descuento
                )

                total += precio_final * cantidad

                detalles_nuevos.append({
                    "producto": prod,
                    "cantidad": cantidad,
                    "precio": precio_final,
                })

            total = _dinero(total)

            nuevo_cliente = cliente.objects.create(
                nombre=nombre,
                telefono=telefono,
                direccion=direccion
            )

            nuevo_pedido = pedido.objects.create(
                cliente=nuevo_cliente,
                total=float(total),
                estado=PedidoEstado.PENDIENTE
            )

            for detalle in detalles_nuevos:

                prod = detalle["producto"]

                detallepedido.objects.create(
                    pedido=nuevo_pedido,
                    producto=prod,
                    cantidad=detalle["cantidad"],
                    precioUnit=float(detalle["precio"])
                )

                prod.stock -= detalle["cantidad"]
                prod.save(update_fields=["stock"])

        return JsonResponse(
            {
                "mensaje": "Pedido registrado correctamente.",
                "id": nuevo_pedido.id,
                "total": float(total),
            },
            status=201
        )

    except ValueError as error:
        return _respuesta_error(str(error))

    except Exception:
        return _respuesta_error(
            "Ocurrió un error al registrar el pedido. Intenta nuevamente.",
            status=500
        )


# =========================================================
# PAGOS EN LÍNEA - WOMPI
# =========================================================

@require_POST
def api_iniciar_pago(request):

    try:
        datos = _leer_json(request)
        pedido_id = int(datos.get("pedidoId", 0))
    except (ValueError, TypeError):
        return _respuesta_error("ID de pedido inválido.")

    pedido_obj = (
        pedido.objects
        .select_related("cliente")
        .filter(id=pedido_id)
        .first()
    )

    if pedido_obj is None:
        return _respuesta_error(
            "El pedido no existe.",
            status=404
        )

    if pedido_obj.estado == PedidoEstado.CANCELADO:
        return _respuesta_error(
            "No puedes pagar un pedido cancelado."
        )

    monto_cop = int(round(float(pedido_obj.total)))
    monto_centavos = monto_cop * 100

    referencia = (
        f"DELI-{pedido_obj.id}-{uuid.uuid4().hex[:6].upper()}"
    )

    url_retorno = (
        request.build_absolute_uri(reverse("retorno_pago"))
        + f"?pedido_id={pedido_obj.id}"
    )

    wompi_public_key = getattr(
        settings,
        "WOMPI_PUBLIC_KEY",
        ""
    )

    wompi_integrity_secret = getattr(
        settings,
        "WOMPI_INTEGRITY_SECRET",
        ""
    )

    if wompi_public_key and wompi_integrity_secret:

        cadena_firma = (
            f"{referencia}"
            f"{monto_centavos}"
            f"COP"
            f"{wompi_integrity_secret}"
        )

        firma_integridad = hashlib.sha256(
            cadena_firma.encode("utf-8")
        ).hexdigest()

        parametros = {
            "public-key": wompi_public_key,
            "currency": "COP",
            "amount-in-cents": monto_centavos,
            "reference": referencia,
            "signature:integrity": firma_integridad,
            "redirect-url": url_retorno,
        }

        checkout_url = (
            "https://checkout.wompi.co/p/?"
            + urlencode(parametros)
        )

        return JsonResponse({
            "ok": True,
            "referencia": referencia,
            "checkout_url": checkout_url,
        })

    # Modo de simulación para pruebas.
    sandbox_url = (
        request.build_absolute_uri(reverse("retorno_pago"))
        + f"?pedido_id={pedido_obj.id}"
        + f"&ref={referencia}"
        + "&estado_pago=APPROVED"
    )

    return JsonResponse({
        "ok": True,
        "referencia": referencia,
        "checkout_url": sandbox_url,
    })


def retorno_pago(request):

    pedido_id = request.GET.get("pedido_id", "")
    estado_pago = request.GET.get("estado_pago", "").upper()

    if pedido_id.isdigit():

        pedido_obj = pedido.objects.filter(
            id=int(pedido_id)
        ).first()

        if (
            pedido_obj
            and estado_pago == "APPROVED"
            and pedido_obj.estado == PedidoEstado.PENDIENTE
        ):

            pedido_obj.estado = PedidoEstado.EN_PREPARACION

            pedido_obj.save(
                update_fields=["estado"]
            )

            messages.success(
                request,
                f"¡Pago aprobado! Tu pedido #{pedido_obj.id} ya pasó a preparación."
            )

            return redirect("consultar_pedido")

    messages.info(
        request,
        "Tu solicitud de pago fue procesada. "
        "Puedes consultar el estado de tu pedido aquí."
    )

    return redirect("consultar_pedido")


@csrf_exempt
@require_POST
def api_webhook_pago(request):

    try:
        evento = json.loads(request.body or "{}")

        transaccion = (
            evento.get("data", {})
            .get("transaction", {})
        )

        referencia = str(
            transaccion.get("reference", "")
        )

        status_tx = str(
            transaccion.get("status", "")
        ).upper()

        partes = referencia.split("-")

        if (
            len(partes) >= 2
            and partes[0] == "DELI"
            and partes[1].isdigit()
            and status_tx == "APPROVED"
        ):

            pedido_id = int(partes[1])

            with transaction.atomic():

                pedido_obj = pedido.objects.select_for_update().filter(
                    id=pedido_id
                ).first()

                if (
                    pedido_obj
                    and pedido_obj.estado == PedidoEstado.PENDIENTE
                ):

                    pedido_obj.estado = PedidoEstado.EN_PREPARACION

                    pedido_obj.save(
                        update_fields=["estado"]
                    )

        return JsonResponse({"received": True})

    except Exception:
        return _respuesta_error(
            "Evento inválido.",
            status=400
        )


# =========================================================
# GESTIÓN DE PQR
# =========================================================

@solo_administrador
def gestion_pqr_page(request):

    lista_pqrs = pqr.objects.all().order_by("-createdAt")

    hace_siete_dias = timezone.now() - timedelta(days=7)

    recientes_count = pqr.objects.filter(
        createdAt__gte=hace_siete_dias
    ).count()

    return render(
        request,
        "deliapp/gestion_pqr.html",
        {
            "pqrs": lista_pqrs,
            "total_count": lista_pqrs.count(),
            "recientes_count": recientes_count,
        }
    )


@solo_administrador
@require_POST
def editar_pqr(request, id):

    item = get_object_or_404(
        pqr,
        id=id
    )

    try:
        data = _leer_json(request)

        nombre = str(
            data.get("nombre", item.nombre)
        ).strip()

        contacto = str(
            data.get("contacto", item.contacto)
        ).strip()

        mensaje = str(
            data.get("mensaje", item.mensaje)
        ).strip()

        if not nombre or not contacto or not mensaje:
            return _respuesta_error(
                "Todos los campos son obligatorios."
            )

        item.nombre = nombre
        item.contacto = contacto
        item.mensaje = mensaje

        item.save()

        return JsonResponse({
            "status": "success",
            "message": "PQR actualizada correctamente.",
        })

    except ValueError as error:
        return _respuesta_error(str(error))


@solo_administrador
@require_http_methods(["POST", "DELETE"])
def eliminar_pqr(request, id):

    item = get_object_or_404(
        pqr,
        id=id
    )

    item.delete()

    return JsonResponse({
        "status": "success",
        "message": "PQR eliminada correctamente.",
    })


# =========================================================
# ESTADÍSTICAS Y PANEL ADMIN
# =========================================================

def _obtener_estadisticas():

    total_usuarios = User.objects.count()

    total_productos = producto.objects.filter(
        activo=True
    ).count()

    total_pedidos = pedido.objects.count()

    ventas = pedido.objects.exclude(
        estado=PedidoEstado.CANCELADO
    ).aggregate(
        total=Sum("total")
    )["total"] or 0

    return {
        "usuarios": total_usuarios,
        "productos": total_productos,
        "pedidos": total_pedidos,
        "ventas": float(ventas),
    }


@solo_administrador
def api_stats(request):
    return JsonResponse(
        _obtener_estadisticas()
    )


@solo_administrador
def admin_dashboard(request):

    hoy = timezone.localdate()
    inicio_semana = hoy - timedelta(days=6)

    stats = _obtener_estadisticas()
    total_pedidos = stats["pedidos"]

    ventas_semana = []

    for desplazamiento in range(7):

        fecha = inicio_semana + timedelta(
            days=desplazamiento
        )

        total_dia = pedido.objects.filter(
            createdAt__date=fecha
        ).exclude(
            estado=PedidoEstado.CANCELADO
        ).aggregate(
            total=Sum("total")
        )["total"] or 0

        ventas_semana.append({
            "fecha": fecha.strftime("%d/%m"),
            "dia": fecha.strftime("%a").capitalize(),
            "total": float(total_dia),
        })

    mayor_venta = max(
        (dia["total"] for dia in ventas_semana),
        default=0
    )

    for dia in ventas_semana:

        dia["porcentaje"] = (
            (dia["total"] / float(mayor_venta)) * 100
            if mayor_venta else 0
        )

    estados_reporte = [
        {
            "nombre": "Pendientes",
            "codigo": PedidoEstado.PENDIENTE,
            "clase": "pending",
        },
        {
            "nombre": "En preparación",
            "codigo": PedidoEstado.EN_PREPARACION,
            "clase": "preparing",
        },
        {
            "nombre": "Entregados",
            "codigo": PedidoEstado.ENTREGADO,
            "clase": "delivered",
        },
        {
            "nombre": "Cancelados",
            "codigo": PedidoEstado.CANCELADO,
            "clase": "cancelled",
        },
    ]

    for estado in estados_reporte:

        estado["cantidad"] = pedido.objects.filter(
            estado=estado["codigo"]
        ).count()

        estado["porcentaje"] = (
            estado["cantidad"] / total_pedidos * 100
            if total_pedidos else 0
        )

    productos_destacados = (
        detallepedido.objects
        .filter(
            pedido__estado__in=[
                PedidoEstado.PENDIENTE,
                PedidoEstado.EN_PREPARACION,
                PedidoEstado.ENTREGADO,
            ]
        )
        .values("producto__nombre")
        .annotate(
            unidades=Sum("cantidad"),
            ingresos=Sum(
                F("cantidad") * F("precioUnit")
            )
        )
        .order_by("-unidades")[:5]
    )

    pedidos_recientes = (
        pedido.objects
        .select_related("cliente")
        .prefetch_related("detallepedido__producto")
        .order_by("-createdAt")[:5]
    )

    return render(
        request,
        "deliapp/admin_dashboard.html",
        {
            "stats": stats,
            "pedidos_recientes": pedidos_recientes,
            "ventas_semana": ventas_semana,
            "estados_reporte": estados_reporte,
            "productos_destacados": productos_destacados,
            "total_pedidos_reporte": total_pedidos,
            "fecha_actual": hoy,
            "mayor_venta": mayor_venta,
        }
    )


# =========================================================
# GESTIÓN DE USUARIOS
# =========================================================

@solo_administrador
def usuarios_page(request):

    return render(
        request,
        "deliapp/usuarios.html"
    )


@solo_administrador
@require_http_methods(["GET", "PUT", "DELETE"])
def api_usuarios(request):

    if request.method == "GET":

        lista = []

        usuarios = User.objects.all().order_by("id")

        for u in usuarios:

            nombre_completo = (
                u.get_full_name().strip()
                or u.username
            )

            lista.append({
                "id": u.id,
                "nombre": nombre_completo,
                "email": u.email or "",
                "rol": _obtener_rol_usuario(u),
                "createdAt": (
                    u.date_joined.isoformat()
                    if hasattr(u, "date_joined")
                    else ""
                ),
            })

        return JsonResponse(
            lista,
            safe=False
        )

    if request.method == "PUT":

        try:
            body = _leer_json(request)
        except ValueError as error:
            return _respuesta_error(str(error))

        user_id = body.get("id")

        nombre = str(
            body.get("nombre", "")
        ).strip()

        email = str(
            body.get("email", "")
        ).strip().lower()

        rol = str(
            body.get("rol", "CLIENTE")
        ).strip().upper()

        if not user_id or not nombre or not email:
            return _respuesta_error(
                "Nombre y correo electrónico son obligatorios."
            )

        if rol not in ("ADMIN", "EMPLEADO", "CLIENTE"):
            return _respuesta_error(
                "El rol seleccionado no es válido."
            )

        usuario_obj = User.objects.filter(
            id=user_id
        ).first()

        if usuario_obj is None:
            return _respuesta_error(
                "Usuario no encontrado.",
                status=404
            )

        if (
            usuario_obj.is_superuser
            and rol != "ADMIN"
            and User.objects.filter(is_superuser=True).count() <= 1
        ):
            return _respuesta_error(
                "No puedes quitar el rol al último administrador del sistema."
            )

        if User.objects.filter(
            email__iexact=email
        ).exclude(
            id=usuario_obj.id
        ).exists():

            return _respuesta_error(
                "Ya existe otra cuenta con ese correo electrónico."
            )

        usuario_obj.first_name = nombre
        usuario_obj.last_name = ""
        usuario_obj.email = email

        _asignar_rol_usuario(
            usuario_obj,
            rol
        )

        usuario_obj.save()

        return JsonResponse({
            "id": usuario_obj.id,
            "nombre": nombre,
            "email": usuario_obj.email,
            "rol": _obtener_rol_usuario(usuario_obj),
        })

    if request.method == "DELETE":

        user_id = request.GET.get("id")

        if not user_id:
            return _respuesta_error(
                "ID de usuario requerido."
            )

        if str(request.user.id) == str(user_id):
            return _respuesta_error(
                "No puedes eliminar tu propia cuenta mientras tienes la sesión iniciada."
            )

        usuario_obj = User.objects.filter(
            id=user_id
        ).first()

        if usuario_obj is None:
            return _respuesta_error(
                "Usuario no encontrado.",
                status=404
            )

        if (
            usuario_obj.is_superuser
            and User.objects.filter(is_superuser=True).count() <= 1
        ):
            return _respuesta_error(
                "No puedes eliminar al último administrador del sistema."
            )

        usuario_obj.delete()

        return JsonResponse({
            "ok": True,
            "message": "Usuario eliminado correctamente."
        })


# =========================================================
# CONSULTAR PEDIDO
# =========================================================

def consultar_pedido(request):

    pedido_encontrado = None
    error = None
    pedido_id = ""
    telefono = ""

    if request.method == "POST":

        pedido_id = request.POST.get(
            "pedido_id",
            ""
        ).strip()

        telefono = request.POST.get(
            "telefono",
            ""
        ).strip()

        if not pedido_id.isdigit() or not telefono:

            error = (
                "Ingresa un número de pedido y un teléfono válidos."
            )

        else:

            pedido_encontrado = (
                pedido.objects
                .select_related("cliente")
                .prefetch_related("detallepedido__producto")
                .filter(
                    id=int(pedido_id),
                    cliente__telefono=telefono
                )
                .first()
            )

            if pedido_encontrado is None:

                error = (
                    "No encontramos un pedido con esos datos. "
                    "Verifica el número y el teléfono registrado."
                )

    return render(
        request,
        "deliapp/consultar_pedido.html",
        {
            "pedido": pedido_encontrado,
            "error": error,
            "pedido_id": pedido_id,
            "telefono": telefono,
        }
    )


# =========================================================
# FACTURACIÓN - FUNCIONES AUXILIARES
# =========================================================

def obtener_estado_factura(estado):

    estados = {
        PedidoEstado.ENTREGADO: "Pagada",
        PedidoEstado.PENDIENTE: "Pendiente",
        PedidoEstado.CANCELADO: "Anulada",
        PedidoEstado.EN_PREPARACION: "Pendiente",
    }

    return estados.get(
        estado,
        "Pendiente"
    )


def numero_factura(pedido_id):
    return f"FAC-{str(pedido_id).zfill(3)}"


def _serializar_factura(pedido_obj):

    productos_factura = []

    for detalle in pedido_obj.detallepedido.all():

        productos_factura.append({
            "nombre": detalle.producto.nombre,
            "cantidad": detalle.cantidad,
            "precio": detalle.precioUnit,
            "subtotal": (
                detalle.cantidad * detalle.precioUnit
            ),
        })

    return {
        "pedido": pedido_obj,
        "numero": numero_factura(pedido_obj.id),
        "cliente": pedido_obj.cliente.nombre,
        "fecha": pedido_obj.createdAt,
        "total": pedido_obj.total,
        "estado": obtener_estado_factura(pedido_obj.estado),
        "metodo": "Efectivo",
        "productos": productos_factura,
    }



# =========================================================
# LISTAR FACTURAS
# =========================================================

@solo_empleado_o_admin
def facturacion(request):

    busqueda = request.GET.get(
        "buscar",
        ""
    ).strip()

    filtro = request.GET.get(
        "estado",
        "Todas"
    )

    pedidos_qs = (
        pedido.objects
        .select_related("cliente")
        .prefetch_related("detallepedido__producto")
        .order_by("-createdAt")
    )

    if busqueda:

        if busqueda.upper().startswith("FAC-"):

            numero = busqueda.upper().replace(
                "FAC-",
                ""
            ).strip()

            if numero.isdigit():
                pedidos_qs = pedidos_qs.filter(
                    id=int(numero)
                )
            else:
                pedidos_qs = pedidos_qs.none()

        elif busqueda.isdigit():

            pedidos_qs = pedidos_qs.filter(
                Q(id=int(busqueda))
                | Q(cliente__nombre__icontains=busqueda)
                | Q(cliente__telefono__icontains=busqueda)
            )

        else:

            pedidos_qs = pedidos_qs.filter(
                Q(cliente__nombre__icontains=busqueda)
                | Q(cliente__telefono__icontains=busqueda)
            )

    if filtro == "Pagadas":
        pedidos_qs = pedidos_qs.filter(
            estado=PedidoEstado.ENTREGADO
        )

    elif filtro == "Pendientes":
        pedidos_qs = pedidos_qs.filter(
            estado__in=[
                PedidoEstado.PENDIENTE,
                PedidoEstado.EN_PREPARACION,
            ]
        )

    elif filtro == "Anuladas":
        pedidos_qs = pedidos_qs.filter(
            estado=PedidoEstado.CANCELADO
        )

    total_facturas = pedido.objects.count()

    pagadas = pedido.objects.filter(
        estado=PedidoEstado.ENTREGADO
    ).count()

    pendientes = pedido.objects.filter(
        estado__in=[
            PedidoEstado.PENDIENTE,
            PedidoEstado.EN_PREPARACION,
        ]
    ).count()

    anuladas = pedido.objects.filter(
        estado=PedidoEstado.CANCELADO
    ).count()

    total_facturado = pedido.objects.filter(
        estado=PedidoEstado.ENTREGADO
    ).aggregate(
        total=Sum("total")
    )["total"] or 0

    facturas = [
        _serializar_factura(p)
        for p in pedidos_qs
    ]

    factura_seleccionada = None

    factura_id = request.GET.get("ver")

    if factura_id and factura_id.isdigit():

        factura_obj = (
            pedido.objects
            .select_related("cliente")
            .prefetch_related("detallepedido__producto")
            .filter(id=int(factura_id))
            .first()
        )

        if factura_obj:
            factura_seleccionada = _serializar_factura(
                factura_obj
            )

    return render(
        request,
        "deliapp/facturacion.html",
        {
            "facturas": facturas,
            "total_facturas": total_facturas,
            "pagadas": pagadas,
            "pendientes": pendientes,
            "anuladas": anuladas,
            "total_facturado": total_facturado,
            "busqueda": busqueda,
            "filtro": filtro,
            "factura_seleccionada": factura_seleccionada,
        }
    )


# =========================================================
# EDITAR FACTURA
# =========================================================

@solo_administrador
def editar_factura(request, pedido_id):

    factura_obj = get_object_or_404(
        pedido.objects.select_related(
            "cliente"
        ).prefetch_related(
            "detallepedido__producto"
        ),
        id=pedido_id
    )

    productos_disponibles = producto.objects.filter(
        activo=True
    ).order_by("nombre")

    if request.method == "POST":

        cliente_nombre = request.POST.get(
            "cliente",
            ""
        ).strip()

        telefono = request.POST.get(
            "telefono",
            ""
        ).strip()

        direccion = request.POST.get(
            "direccion",
            ""
        ).strip()

        estado = request.POST.get(
            "estado",
            ""
        ).strip()

        productos_ids = request.POST.getlist(
            "producto_id[]"
        )

        cantidades_raw = request.POST.getlist(
            "cantidad[]"
        )

        if not cliente_nombre:

            messages.error(
                request,
                "El nombre del cliente es obligatorio."
            )

        elif estado not in PedidoEstado.values:

            messages.error(
                request,
                "El estado seleccionado no es válido."
            )

        elif len(productos_ids) != len(cantidades_raw):

            messages.error(
                request,
                "La información de los productos está incompleta."
            )

        else:

            nuevas_cantidades = {}
            error_items = None

            for p_id_str, cant_str in zip(
                productos_ids,
                cantidades_raw
            ):

                if not p_id_str:
                    continue

                try:
                    p_id = int(p_id_str)
                    cantidad = int(cant_str)
                except (TypeError, ValueError):
                    error_items = (
                        "Las cantidades ingresadas no son válidas."
                    )
                    break

                if p_id <= 0 or cantidad < 0:
                    error_items = (
                        "Los productos y cantidades ingresados no son válidos."
                    )
                    break

                if cantidad == 0:
                    continue

                nuevas_cantidades[p_id] = (
                    nuevas_cantidades.get(p_id, 0) + cantidad
                )

            if error_items:

                messages.error(
                    request,
                    error_items
                )

            elif not nuevas_cantidades:

                messages.error(
                    request,
                    "El pedido debe contener al menos un producto."
                )

            else:

                try:

                    with transaction.atomic():

                        # Actualizar datos del cliente.
                        cliente_obj = cliente.objects.select_for_update().get(
                            id=factura_obj.cliente_id
                        )

                        cliente_obj.nombre = cliente_nombre
                        cliente_obj.telefono = telefono
                        cliente_obj.direccion = direccion

                        cliente_obj.save(
                            update_fields=[
                                "nombre",
                                "telefono",
                                "direccion",
                            ]
                        )

                        # Actualizar productos, stock, total y estado.
                        _reemplazar_detalles_pedido(
                            pedido_id=factura_obj.id,
                            cantidades=nuevas_cantidades,
                            estado_nuevo=estado,
                        )

                    messages.success(
                        request,
                        f"La factura {numero_factura(factura_obj.id)} "
                        f"y su pedido #{factura_obj.id} "
                        "se actualizaron correctamente."
                    )

                    return redirect("facturacion")

                except ValueError as error:

                    messages.error(
                        request,
                        str(error)
                    )

                except Exception:

                    messages.error(
                        request,
                        "No fue posible actualizar la factura. "
                        "Verifica los datos e inténtalo nuevamente."
                    )

    factura_obj.refresh_from_db()

    return render(
        request,
        "deliapp/editar_factura.html",
        {
            "factura": factura_obj,
            "numero_factura": numero_factura(factura_obj.id),
            "estados": PedidoEstado.choices,
            "productos_disponibles": productos_disponibles,
        }
    )


# =========================================================
# ELIMINAR FACTURA
# =========================================================

@solo_administrador
@require_POST
def eliminar_factura(request, pedido_id):

    try:

        with transaction.atomic():

            factura_obj = pedido.objects.select_for_update().get(
                id=pedido_id
            )

            detalles = list(
                detallepedido.objects.filter(
                    pedido=factura_obj
                ).order_by("producto_id")
            )

            # Si el pedido no estaba cancelado, su inventario
            # todavía estaba reservado y debe devolverse.
            if factura_obj.estado != PedidoEstado.CANCELADO:

                ids_productos = sorted({
                    detalle.producto_id
                    for detalle in detalles
                })

                productos_bloqueados = {
                    prod.id: prod
                    for prod in producto.objects.select_for_update().filter(
                        id__in=ids_productos
                    ).order_by("id")
                }

                for detalle in detalles:

                    prod = productos_bloqueados.get(
                        detalle.producto_id
                    )

                    if prod:
                        prod.stock += detalle.cantidad

                for prod in productos_bloqueados.values():
                    prod.save(update_fields=["stock"])

            factura_obj.delete()

        messages.success(
            request,
            "La factura y su pedido asociado fueron eliminados correctamente."
        )

    except Exception:

        messages.error(
            request,
            "No fue posible eliminar la factura."
        )

    return redirect("facturacion")


# =========================================================
# ADMINISTRACIÓN DE PEDIDOS
# =========================================================

@solo_administrador
def pedidos_admin(request):

    busqueda = request.GET.get(
        "buscar",
        ""
    ).strip()

    estado_filtro = request.GET.get(
        "estado",
        ""
    ).strip()

    pedidos_lista = (
        pedido.objects
        .select_related("cliente")
        .prefetch_related("detallepedido__producto")
        .order_by("-createdAt", "-id")
    )

    if busqueda:

        filtros = (
            Q(cliente__nombre__icontains=busqueda)
            | Q(cliente__telefono__icontains=busqueda)
        )

        if busqueda.isdigit():
            filtros |= Q(id=int(busqueda))

        pedidos_lista = pedidos_lista.filter(filtros)

    if estado_filtro in PedidoEstado.values:

        pedidos_lista = pedidos_lista.filter(
            estado=estado_filtro
        )

    return render(
        request,
        "deliapp/pedidos_admin.html",
        {
            "pedidos": pedidos_lista,
            "busqueda": busqueda,
            "estado_filtro": estado_filtro,
            "estados": PedidoEstado.choices,
            "total_pedidos": pedido.objects.count(),
            "pendientes": pedido.objects.filter(
                estado=PedidoEstado.PENDIENTE
            ).count(),
            "en_preparacion": pedido.objects.filter(
                estado=PedidoEstado.EN_PREPARACION
            ).count(),
            "entregados": pedido.objects.filter(
                estado=PedidoEstado.ENTREGADO
            ).count(),
            "cancelados": pedido.objects.filter(
                estado=PedidoEstado.CANCELADO
            ).count(),
        }
    )


@solo_administrador
@require_POST
def actualizar_estado_pedido(request, pedido_id):

    nuevo_estado = request.POST.get(
        "estado",
        ""
    ).strip()

    if nuevo_estado not in PedidoEstado.values:

        messages.error(
            request,
            "El estado seleccionado no es válido."
        )

        return redirect("pedidos_admin")

    try:

        pedido_actual = _cambiar_estado_pedido_con_inventario(
            pedido_id,
            nuevo_estado
        )

        messages.success(
            request,
            f"El pedido #{pedido_actual.id} fue actualizado correctamente."
        )

    except pedido.DoesNotExist:

        messages.error(
            request,
            "El pedido seleccionado no existe."
        )

    except ValueError as error:

        messages.error(
            request,
            str(error)
        )

    except Exception:

        messages.error(
            request,
            "No fue posible actualizar el estado del pedido."
        )

    return redirect("pedidos_admin")


# =========================================================
# PANEL DE EMPLEADOS
# =========================================================

@solo_empleado_o_admin
def empleado_pedidos(request):

    pedidos_lista = (
        pedido.objects
        .select_related("cliente")
        .prefetch_related("detallepedido__producto")
        .order_by("-createdAt")
    )

    return render(
        request,
        "deliapp/empleado_pedidos.html",
        {
            "pedidos": pedidos_lista,
            "total_pedidos": pedidos_lista.count(),
            "pendientes": pedidos_lista.filter(
                estado=PedidoEstado.PENDIENTE
            ).count(),
            "preparacion": pedidos_lista.filter(
                estado=PedidoEstado.EN_PREPARACION
            ).count(),
            "completados": pedidos_lista.filter(
                estado=PedidoEstado.ENTREGADO
            ).count(),
        }
    )


@solo_empleado_o_admin
@require_http_methods(["PATCH"])
def api_empleado_actualizar_estado(request, pedido_id):

    try:
        data = _leer_json(request)
    except ValueError as error:
        return _respuesta_error(str(error))

    nuevo_estado = str(
        data.get("estado", "")
    ).strip()

    if nuevo_estado not in PedidoEstado.values:
        return _respuesta_error(
            "El estado seleccionado no es válido."
        )

    try:

        pedido_actual = _cambiar_estado_pedido_con_inventario(
            pedido_id,
            nuevo_estado
        )

        return JsonResponse({
            "ok": True,
            "id": pedido_actual.id,
            "estado": pedido_actual.estado,
            "estado_display": pedido_actual.get_estado_display(),
        })

    except pedido.DoesNotExist:

        return _respuesta_error(
            "El pedido no existe.",
            status=404
        )

    except ValueError as error:

        return _respuesta_error(str(error))

    except Exception:

        return _respuesta_error(
            "No fue posible actualizar el estado del pedido.",
            status=500
        )


# =========================================================
# PANEL DE GESTIÓN DE PEDIDOS
# =========================================================

def _serializar_pedido_gestion(pedido_obj):

    detalles = []

    for det in pedido_obj.detallepedido.all():

        detalles.append({
            "producto_id": det.producto_id,
            "nombre": det.producto.nombre,
            "cantidad": det.cantidad,
            "precio": float(det.precioUnit),
            "subtotal": float(
                _dinero(det.cantidad * det.precioUnit)
            ),
        })

    return {
        "id": pedido_obj.id,
        "cliente": pedido_obj.cliente.nombre,
        "telefono": pedido_obj.cliente.telefono,
        "direccion": pedido_obj.cliente.direccion or "Sin dirección",
        "total": float(pedido_obj.total),
        "estado": pedido_obj.estado,
        "estado_display": pedido_obj.get_estado_display(),
        "fecha": (
            pedido_obj.createdAt.isoformat()
            if pedido_obj.createdAt
            else ""
        ),
        "observaciones": pedido_obj.observaciones,
        "items": detalles,
        "cantidad_productos": sum(
            item["cantidad"] for item in detalles
        ),
    }


@solo_empleado_o_admin
def gestion_pedidos_page(request):
    pedidos = (
        pedido.objects
        .select_related('cliente')
        .prefetch_related('detallepedido__producto')
        .order_by('-createdAt')
    )

    total_pedidos = pedidos.count()

    pendientes = pedidos.filter(
        estado=PedidoEstado.PENDIENTE
    ).count()

    preparacion = pedidos.filter(
        estado=PedidoEstado.EN_PREPARACION
    ).count()

    entregados = pedidos.filter(
        estado=PedidoEstado.ENTREGADO
    ).count()

    cancelados = pedidos.filter(
        estado=PedidoEstado.CANCELADO
    ).count()

    contexto = {
        'pedidos': pedidos,
        'total_pedidos': total_pedidos,
        'pendientes': pendientes,

        # Compatibilidad con ambos nombres
        'preparacion': preparacion,
        'en_preparacion': preparacion,

        'entregados': entregados,
        'completados': entregados,

        'cancelados': cancelados,
        'estados': PedidoEstado.choices,
    }

    return render(
        request,
        'deliapp/empleado_pedidos.html',
        contexto
    )

@solo_empleado_o_admin
@require_http_methods(["GET"])
def api_gestion_pedidos(request):

    pedidos_qs = (
        pedido.objects
        .select_related("cliente")
        .prefetch_related("detallepedido__producto")
        .order_by("-createdAt")
    )

    lista = [
        _serializar_pedido_gestion(p)
        for p in pedidos_qs
    ]

    return JsonResponse(
        lista,
        safe=False
    )


# =========================================================
# PANEL DE CLIENTE
# =========================================================

def cliente_dashboard(request):

    if request.user.is_authenticated:

        nombre_cliente = (
            request.user.get_full_name().strip()
            or request.user.first_name.strip()
            or request.user.username
        )

        pedidos_cliente = (
            pedido.objects
            .select_related("cliente")
            .prefetch_related("detallepedido__producto")
            .filter(
                Q(cliente__nombre__iexact=nombre_cliente)
                | Q(cliente__nombre__iexact=request.user.username)
            )
            .order_by("-createdAt")
        )

    else:

        nombre_cliente = "Cliente"
        pedidos_cliente = pedido.objects.none()

    return render(
        request,
        "deliapp/cliente_dashboard.html",
        {
            "nombre_cliente": nombre_cliente,
            "pedidos": pedidos_cliente,
        }
    )


# =========================================================
# EDICIÓN AJAX DE PEDIDOS DESDE EL PANEL ADMINISTRATIVO
# =========================================================

@solo_administrador
@require_http_methods(["GET", "POST"])
def api_editar_pedido_admin(request, pedido_id):

    pedido_actual = get_object_or_404(
        pedido.objects.select_related(
            "cliente"
        ).prefetch_related(
            "detallepedido__producto"
        ),
        id=pedido_id
    )

    # -----------------------------------------------------
    # CONSULTAR PEDIDO PARA EL MODAL
    # -----------------------------------------------------

    if request.method == "GET":

        detalles = []

        for detalle in pedido_actual.detallepedido.all():

            detalles.append({
                "producto_id": detalle.producto_id,
                "nombre": detalle.producto.nombre,
                "cantidad": detalle.cantidad,
                "precio": float(detalle.precioUnit),

                # El modelo no guarda el descuento histórico.
                # Se conserva el precio final que ya fue registrado.
                "descuento": 0,
            })

        productos_disponibles = producto.objects.filter(
            activo=True
        ).order_by("nombre")

        productos_json = [
            {
                "id": prod.id,
                "nombre": prod.nombre,
                "precio": float(prod.precio),
                "descuento": int(prod.descuento or 0),
                "stock": prod.stock,
            }
            for prod in productos_disponibles
        ]

        return JsonResponse({
            "id": pedido_actual.id,
            "cliente": {
                "nombre": pedido_actual.cliente.nombre,
                "telefono": pedido_actual.cliente.telefono,
                "direccion": pedido_actual.cliente.direccion,
            },
            "estado": pedido_actual.estado,
            "estado_display": pedido_actual.get_estado_display(),
            "total": float(pedido_actual.total),
            "observaciones": pedido_actual.observaciones,
            "detalles": detalles,
            "productos": productos_json,
        })

    # -----------------------------------------------------
    # GUARDAR CAMBIOS DEL MODAL
    # -----------------------------------------------------

    try:
        datos = _leer_json(request)
    except ValueError as error:
        return _respuesta_error(str(error))

    productos_recibidos = datos.get(
        "productos",
        []
    )

    nuevo_estado = str(
        datos.get("estado", pedido_actual.estado)
    ).strip()

    if nuevo_estado not in PedidoEstado.values:
        return _respuesta_error(
            "El estado seleccionado no es válido."
        )

    if (
        not isinstance(productos_recibidos, list)
        or not productos_recibidos
    ):
        return _respuesta_error(
            "El pedido debe contener al menos un producto."
        )

    cantidades = {}
    precios_personalizados = {}

    for item in productos_recibidos:

        if not isinstance(item, dict):
            return _respuesta_error(
                "Hay un producto con información incorrecta."
            )

        try:
            producto_id = int(
                item.get("producto_id")
            )

            cantidad = int(
                item.get("cantidad")
            )

            precio_base = _decimal(
                item.get("precio")
            )

            descuento = _decimal(
                item.get("descuento", 0)
            )

        except (TypeError, ValueError):
            return _respuesta_error(
                "Revisa las cantidades, precios y descuentos."
            )

        if (
            producto_id <= 0
            or cantidad <= 0
            or precio_base is None
            or descuento is None
        ):
            return _respuesta_error(
                "Los datos de los productos no son válidos."
            )

        if producto_id in cantidades:
            return _respuesta_error(
                "No repitas el mismo producto en varias filas."
            )

        try:
            precio_final = _precio_con_descuento(
                precio_base,
                descuento
            )
        except ValueError as error:
            return _respuesta_error(str(error))

        cantidades[producto_id] = cantidad
        precios_personalizados[producto_id] = precio_final

    if not cantidades:
        return _respuesta_error(
            "Agrega al menos un producto válido."
        )

    try:

        pedido_actualizado = _reemplazar_detalles_pedido(
            pedido_id=pedido_id,
            cantidades=cantidades,
            estado_nuevo=nuevo_estado,
            precios_personalizados=precios_personalizados,
        )

        return JsonResponse({
            "ok": True,
            "mensaje": "El pedido fue actualizado correctamente.",
            "id": pedido_actualizado.id,
            "total": float(pedido_actualizado.total),
            "estado": pedido_actualizado.estado,
            "estado_display": pedido_actualizado.get_estado_display(),
        })

    except pedido.DoesNotExist:

        return _respuesta_error(
            "El pedido no existe.",
            status=404
        )

    except ValueError as error:

        return _respuesta_error(str(error))

    except Exception:

        return _respuesta_error(
            "Ocurrió un error al actualizar el pedido.",
            status=500
        )
