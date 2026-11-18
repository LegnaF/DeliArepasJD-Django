from .correos import enviar_correo_deli
import json
from collections import defaultdict
from datetime import timedelta

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import user_passes_test
from django.db import transaction
from django.db.models import Sum, Q, F
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
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
# PERMISOS Y ROLES
# =========================================================

def es_administrador(user):
    """
    Solo permite el acceso a cuentas administradoras.
    """
    return user.is_authenticated and user.is_superuser


def es_empleado(user):
    """
    Permite el acceso a empleados, sin incluir administradores.
    """
    return (
        user.is_authenticated
        and user.is_staff
        and not user.is_superuser
    )


def es_empleado_o_admin(user):
    """
    Permite el acceso tanto a empleados (is_staff) como a administradores (is_superuser).
    """
    return user.is_authenticated and (user.is_staff or user.is_superuser)


solo_administrador = user_passes_test(
    es_administrador,
    login_url='login'
)

solo_empleado = user_passes_test(
    es_empleado,
    login_url='login'
)

solo_empleado_o_admin = user_passes_test(
    es_empleado_o_admin,
    login_url='login'
)


def _obtener_rol_usuario(user):
    """
    Determina el rol utilizando los permisos de Django.
    """

    if user.is_superuser:
        return 'ADMIN'

    if user.is_staff:
        return 'EMPLEADO'

    return 'CLIENTE'


def _asignar_rol_usuario(user, rol):
    """
    Asigna el rol a una cuenta de Django.
    """

    rol = str(rol).strip().upper()

    if rol == 'ADMIN':
        user.is_superuser = True
        user.is_staff = True

    elif rol == 'EMPLEADO':
        user.is_superuser = False
        user.is_staff = True

    elif rol == 'CLIENTE':
        user.is_superuser = False
        user.is_staff = False

    else:
        raise ValueError('El rol seleccionado no es válido.')


# =========================================================
# INICIO
# =========================================================

def home_page(request):
    """
    Página principal y formulario público de PQR.
    """

    if request.method == 'POST':
        form = PQRForm(request.POST)

        if form.is_valid():
            form.save()

            messages.success(
                request,
                '¡Mensaje enviado con éxito! Nos pondremos en contacto pronto.'
            )

            return redirect('inicio')

        messages.error(
            request,
            'No se pudo enviar el mensaje. Verifica los datos ingresados.'
        )

    else:
        form = PQRForm()

    productos_destacados = producto.objects.filter(
        activo=True
    ).order_by('-id')[:4]

    context = {
        'form': form,
        'productos': productos_destacados,
    }

    return render(
        request,
        'deliapp/index.html',
        context
    )


# =========================================================
# MENÚ
# =========================================================

def menu_page(request):
    """
    Catálogo público de productos activos.
    """

    productos = producto.objects.filter(
        activo=True
    ).order_by('nombre')

    categorias_bd = (
        producto.objects
        .filter(activo=True)
        .values_list('categoria', flat=True)
        .distinct()
    )

    categorias = ['Todos'] + list(categorias_bd)

    context = {
        'productos': productos,
        'categorias': categorias,
    }

    return render(
        request,
        'deliapp/menu.html',
        context
    )


# =========================================================
# DETALLE DEL PRODUCTO
# =========================================================

def detalle_producto(request, id):
    """
    Muestra la información de un producto activo.
    """

    prod = get_object_or_404(
        producto,
        id=id,
        activo=True
    )

    return render(
        request,
        'deliapp/detalle_producto.html',
        {'producto': prod}
    )


# =========================================================
# REGISTRO DE PEDIDOS
# =========================================================

import json
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from django.db import transaction
from django.http import JsonResponse
from django.views.decorators.http import require_POST

from .models import cliente, producto, pedido, detallepedido


@require_POST
def crear_pedido(request):
    try:
        datos = json.loads(request.body or "{}")
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse(
            {"error": "Los datos enviados no tienen un formato válido."},
            status=400
        )

    nombre = str(datos.get("clienteNombre", "")).strip()
    telefono = str(datos.get("telefono", "")).strip()
    direccion = str(datos.get("direccion", "")).strip()
    items = datos.get("items", [])

    if not nombre or not telefono or not direccion:
        return JsonResponse(
            {"error": "Debes completar nombre, teléfono y dirección."},
            status=400
        )

    if not isinstance(items, list) or not items:
        return JsonResponse(
            {"error": "Tu carrito no contiene productos."},
            status=400
        )

    # Unificar productos repetidos y validar cantidades.
    cantidades = {}

    for item in items:
        if not isinstance(item, dict):
            return JsonResponse(
                {"error": "Hay un producto con información incorrecta."},
                status=400
            )

        try:
            producto_id = int(item.get("productoId"))
            cantidad = int(item.get("cantidad"))
        except (TypeError, ValueError):
            return JsonResponse(
                {"error": "Hay un producto con identificación o cantidad inválida."},
                status=400
            )

        if producto_id <= 0 or cantidad <= 0:
            return JsonResponse(
                {"error": "Las cantidades de los productos deben ser mayores que cero."},
                status=400
            )

        cantidades[producto_id] = cantidades.get(producto_id, 0) + cantidad

    try:
        with transaction.atomic():

            productos = producto.objects.select_for_update().filter(
                id__in=cantidades.keys()
            )

            productos_por_id = {
                prod.id: prod for prod in productos
            }

            if len(productos_por_id) != len(cantidades):
                return JsonResponse(
                    {"error": "Uno o más productos ya no están disponibles."},
                    status=400
                )

            total = Decimal("0.00")
            detalles = []

            # Validar disponibilidad y calcular precios desde la base de datos.
            for producto_id, cantidad in cantidades.items():
                prod = productos_por_id[producto_id]

                if not prod.activo:
                    return JsonResponse(
                        {"error": f"El producto {prod.nombre} ya no está disponible."},
                        status=400
                    )

                if cantidad > prod.stock:
                    return JsonResponse(
                        {
                            "error": (
                                f"No hay suficientes unidades de {prod.nombre}. "
                                f"Disponibles: {prod.stock}."
                            )
                        },
                        status=400
                    )

                try:
                    precio = Decimal(str(prod.precio))
                    descuento = Decimal(str(prod.descuento or 0))
                except (InvalidOperation, TypeError, ValueError):
                    return JsonResponse(
                        {"error": f"El precio de {prod.nombre} no es válido."},
                        status=400
                    )

                if precio < 0 or descuento < 0 or descuento > 100:
                    return JsonResponse(
                        {"error": f"El precio o descuento de {prod.nombre} no es válido."},
                        status=400
                    )

                precio_final = (
                    precio * (Decimal("1") - descuento / Decimal("100"))
                ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

                subtotal_producto = precio_final * cantidad
                total += subtotal_producto

                detalles.append({
                    "producto": prod,
                    "cantidad": cantidad,
                    "precio": precio_final
                })

            total = total.quantize(
                Decimal("0.01"),
                rounding=ROUND_HALF_UP
            )

            # Crear cliente y pedido.
            nuevo_cliente = cliente.objects.create(
                nombre=nombre,
                telefono=telefono,
                direccion=direccion
            )

            nuevo_pedido = pedido.objects.create(
                cliente=nuevo_cliente,
                total=float(total)
            )

            # Guardar detalles y descontar inventario.
            for detalle in detalles:
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
                "total": float(total)
            },
            status=201
        )

    except Exception:
        return JsonResponse(
            {"error": "Ocurrió un error al registrar el pedido. Intenta nuevamente."},
            status=500
        )
# =========================================================
# GESTIÓN DE PQR
# =========================================================

@solo_administrador
def gestion_pqr_page(request):
    """
    Panel administrativo de gestión de PQR.
    """

    lista_pqrs = pqr.objects.all().order_by('-createdAt')

    hace_siete_dias = timezone.now() - timedelta(days=7)

    recientes_count = pqr.objects.filter(
        createdAt__gte=hace_siete_dias
    ).count()

    context = {
        'pqrs': lista_pqrs,
        'total_count': lista_pqrs.count(),
        'recientes_count': recientes_count,
    }

    return render(
        request,
        'deliapp/gestion_pqr.html',
        context
    )


@solo_administrador
@require_http_methods(['POST'])
def editar_pqr(request, id):
    """
    Actualiza una PQR mediante AJAX.
    """

    item = get_object_or_404(
        pqr,
        id=id
    )

    try:
        data = json.loads(request.body or '{}')

        if not isinstance(data, dict):
            return JsonResponse(
                {'error': 'Los datos enviados no son válidos.'},
                status=400
            )

        nombre = str(data.get('nombre', item.nombre)).strip()
        contacto = str(data.get('contacto', item.contacto)).strip()
        mensaje = str(data.get('mensaje', item.mensaje)).strip()

        if not nombre or not contacto or not mensaje:
            return JsonResponse(
                {'error': 'Todos los campos son obligatorios.'},
                status=400
            )

        item.nombre = nombre
        item.contacto = contacto
        item.mensaje = mensaje

        item.save()

        return JsonResponse({
            'status': 'success',
            'message': 'PQR actualizada correctamente.',
        })

    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse(
            {'error': 'Los datos enviados no son válidos.'},
            status=400
        )


@solo_administrador
@require_http_methods(['POST', 'DELETE'])
def eliminar_pqr(request, id):
    """
    Elimina una PQR mediante AJAX.
    """

    item = get_object_or_404(
        pqr,
        id=id
    )

    item.delete()

    return JsonResponse({
        'status': 'success',
        'message': 'PQR eliminada correctamente.',
    })


# =========================================================
# ESTADÍSTICAS Y PANEL ADMIN
# =========================================================

def _obtener_estadisticas():
    total_usuarios = User.objects.count()

    total_productos = producto.objects.filter(activo=True).count()

    total_pedidos = pedido.objects.count()

    ventas = pedido.objects.exclude(
        estado=PedidoEstado.CANCELADO
    ).aggregate(
        total=Sum('total')
    )['total'] or 0

    return {
        'usuarios': total_usuarios,
        'productos': total_productos,
        'pedidos': total_pedidos,
        'ventas': float(ventas),
    }


@solo_administrador
def api_stats(request):
    """
    Devuelve los indicadores generales en JSON para el botón Actualizar del Panel Admin.
    """
    return JsonResponse(_obtener_estadisticas())


@solo_administrador
def admin_dashboard(request):
    """
    Panel principal del administrador.
    """

    hoy = timezone.localdate()
    inicio_semana = hoy - timedelta(days=6)

    stats = _obtener_estadisticas()

    total_pedidos = stats['pedidos']

    ventas_semana = []

    for desplazamiento in range(7):
        fecha = inicio_semana + timedelta(days=desplazamiento)

        total_dia = pedido.objects.filter(
            createdAt__date=fecha
        ).exclude(
            estado=PedidoEstado.CANCELADO
        ).aggregate(
            total=Sum('total')
        )['total'] or 0

        ventas_semana.append({
            'fecha': fecha.strftime('%d/%m'),
            'dia': fecha.strftime('%a').capitalize(),
            'total': float(total_dia),
        })

    mayor_venta = max(
        (dia['total'] for dia in ventas_semana),
        default=0
    )

    for dia in ventas_semana:
        dia['porcentaje'] = (
            (dia['total'] / float(mayor_venta)) * 100
            if mayor_venta else 0
        )

    estados_reporte = [
        {
            'nombre': 'Pendientes',
            'codigo': PedidoEstado.PENDIENTE,
            'clase': 'pending',
        },
        {
            'nombre': 'En preparación',
            'codigo': PedidoEstado.EN_PREPARACION,
            'clase': 'preparing',
        },
        {
            'nombre': 'Entregados',
            'codigo': PedidoEstado.ENTREGADO,
            'clase': 'delivered',
        },
        {
            'nombre': 'Cancelados',
            'codigo': PedidoEstado.CANCELADO,
            'clase': 'cancelled',
        },
    ]

    for estado in estados_reporte:
        estado['cantidad'] = pedido.objects.filter(
            estado=estado['codigo']
        ).count()

        estado['porcentaje'] = (
            estado['cantidad'] / total_pedidos * 100
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
        .values('producto__nombre')
        .annotate(
            unidades=Sum('cantidad'),
            ingresos=Sum(F('cantidad') * F('precioUnit'))
        )
        .order_by('-unidades')[:5]
    )

    pedidos_recientes = (
        pedido.objects
        .select_related('cliente')
        .order_by('-createdAt')[:5]
    )

    context = {
        'stats': stats,
        'pedidos_recientes': pedidos_recientes,
        'ventas_semana': ventas_semana,
        'estados_reporte': estados_reporte,
        'productos_destacados': productos_destacados,
        'total_pedidos_reporte': total_pedidos,
        'fecha_actual': hoy,
        'mayor_venta': mayor_venta,
    }

    return render(
        request,
        'deliapp/admin_dashboard.html',
        context
    )


# =========================================================
# GESTIÓN DE USUARIOS
# =========================================================

@solo_administrador
def usuarios_page(request):
    """
    Página de administración de usuarios.
    """

    return render(
        request,
        'deliapp/usuarios.html'
    )


@solo_administrador
@require_http_methods(['GET', 'PUT', 'DELETE'])
def api_usuarios(request):
    """
    API administrativa para listar, editar y eliminar usuarios.
    """

    if request.method == 'GET':

        lista = []

        usuarios = User.objects.all().order_by('id')

        for u in usuarios:

            nombre_completo = (
                u.get_full_name().strip()
                or u.username
            )

            lista.append({
                'id': u.id,
                'nombre': nombre_completo,
                'email': u.email or '',
                'rol': _obtener_rol_usuario(u),
                'createdAt': (
                    u.date_joined.isoformat()
                    if hasattr(u, 'date_joined')
                    else ''
                ),
            })

        return JsonResponse(
            lista,
            safe=False
        )

    if request.method == 'PUT':

        try:
            body = json.loads(
                request.body.decode('utf-8')
            )

        except (ValueError, UnicodeDecodeError):
            return JsonResponse(
                {'error': 'Datos JSON inválidos.'},
                status=400
            )

        if not isinstance(body, dict):
            return JsonResponse(
                {'error': 'Los datos enviados no son válidos.'},
                status=400
            )

        user_id = body.get('id')

        nombre = str(
            body.get('nombre', '')
        ).strip()

        email = str(
            body.get('email', '')
        ).strip().lower()

        rol = str(
            body.get('rol', 'CLIENTE')
        ).strip().upper()

        if not user_id or not nombre or not email:
            return JsonResponse(
                {
                    'error': 'Nombre y correo electrónico son obligatorios.'
                },
                status=400
            )

        if rol not in ('ADMIN', 'EMPLEADO', 'CLIENTE'):
            return JsonResponse(
                {'error': 'El rol seleccionado no es válido.'},
                status=400
            )

        usuario = User.objects.filter(
            id=user_id
        ).first()

        if usuario is None:
            return JsonResponse(
                {'error': 'Usuario no encontrado.'},
                status=404
            )

        if (
            usuario.is_superuser
            and rol != 'ADMIN'
            and User.objects.filter(is_superuser=True).count() <= 1
        ):
            return JsonResponse(
                {
                    'error': (
                        'No puedes quitar el rol al último administrador '
                        'del sistema.'
                    )
                },
                status=400
            )

        if User.objects.filter(
            email__iexact=email
        ).exclude(
            id=usuario.id
        ).exists():

            return JsonResponse(
                {
                    'error': (
                        'Ya existe otra cuenta con ese correo electrónico.'
                    )
                },
                status=400
            )

        usuario.first_name = nombre
        usuario.last_name = ''
        usuario.email = email

        _asignar_rol_usuario(
            usuario,
            rol
        )

        usuario.save()

        return JsonResponse({
            'id': usuario.id,
            'nombre': nombre,
            'email': usuario.email,
            'rol': _obtener_rol_usuario(usuario),
        })

    if request.method == 'DELETE':

        user_id = request.GET.get('id')

        if not user_id:
            return JsonResponse(
                {'error': 'ID de usuario requerido.'},
                status=400
            )

        if str(request.user.id) == str(user_id):
            return JsonResponse(
                {
                    'error': (
                        'No puedes eliminar tu propia cuenta '
                        'mientras tienes la sesión iniciada.'
                    )
                },
                status=400
            )

        usuario = User.objects.filter(
            id=user_id
        ).first()

        if usuario is None:
            return JsonResponse(
                {'error': 'Usuario no encontrado.'},
                status=404
            )

        if (
            usuario.is_superuser
            and User.objects.filter(is_superuser=True).count() <= 1
        ):
            return JsonResponse(
                {
                    'error': (
                        'No puedes eliminar al último administrador '
                        'del sistema.'
                    )
                },
                status=400
            )

        usuario.delete()

        return JsonResponse({
            'ok': True,
            'message': 'Usuario eliminado correctamente.'
        })


# =========================================================
# CONSULTAR PEDIDO
# =========================================================

def consultar_pedido(request):
    """
    Permite consultar un pedido sin iniciar sesión.
    """

    pedido_encontrado = None
    error = None
    pedido_id = ''
    telefono = ''

    if request.method == 'POST':

        pedido_id = request.POST.get(
            'pedido_id',
            ''
        ).strip()

        telefono = request.POST.get(
            'telefono',
            ''
        ).strip()

        if not pedido_id.isdigit() or not telefono:

            error = (
                'Ingresa un número de pedido y un teléfono válidos.'
            )

        else:

            pedido_encontrado = (
                pedido.objects
                .select_related('cliente')
                .prefetch_related('detallepedido__producto')
                .filter(
                    id=int(pedido_id),
                    cliente__telefono=telefono
                )
                .first()
            )

            if pedido_encontrado is None:

                error = (
                    'No encontramos un pedido con esos datos. '
                    'Verifica el número y el teléfono registrado.'
                )

    return render(
        request,
        'deliapp/consultar_pedido.html',
        {
            'pedido': pedido_encontrado,
            'error': error,
            'pedido_id': pedido_id,
            'telefono': telefono,
        }
    )


# ==========================================
# FACTURACIÓN - FUNCIONES AUXILIARES
# ==========================================

def obtener_estado_factura(estado):
    estados = {
        PedidoEstado.ENTREGADO: 'Pagada',
        PedidoEstado.PENDIENTE: 'Pendiente',
        PedidoEstado.CANCELADO: 'Anulada',
        PedidoEstado.EN_PREPARACION: 'Pendiente',
    }

    return estados.get(estado, 'Pendiente')


def numero_factura(pedido_id):
    return f"FAC-{str(pedido_id).zfill(3)}"


# ==========================================
# LISTAR FACTURAS
# ==========================================

def facturacion(request):

    busqueda = request.GET.get('buscar', '').strip()
    filtro = request.GET.get('estado', 'Todas')

    pedidos = pedido.objects.select_related(
        'cliente'
    ).prefetch_related(
        'detallepedido__producto'
    ).order_by('-createdAt')

    if busqueda:
        if busqueda.upper().startswith('FAC-'):
            numero = busqueda.upper().replace('FAC-', '').strip()
            if numero.isdigit():
                pedidos = pedidos.filter(id=int(numero))
            else:
                pedidos = pedidos.none()
        elif busqueda.isdigit():
            pedidos = pedidos.filter(
                Q(id=int(busqueda)) |
                Q(cliente__nombre__icontains=busqueda)
            )
        else:
            pedidos = pedidos.filter(
                cliente__nombre__icontains=busqueda
            )

    if filtro == 'Pagadas':
        pedidos = pedidos.filter(estado=PedidoEstado.ENTREGADO)

    elif filtro == 'Pendientes':
        pedidos = pedidos.filter(
            estado__in=[
                PedidoEstado.PENDIENTE,
                PedidoEstado.EN_PREPARACION
            ]
        )

    elif filtro == 'Anuladas':
        pedidos = pedidos.filter(estado=PedidoEstado.CANCELADO)

    total_facturas = pedido.objects.count()

    pagadas = pedido.objects.filter(
        estado=PedidoEstado.ENTREGADO
    ).count()

    pendientes = pedido.objects.filter(
        estado__in=[
            PedidoEstado.PENDIENTE,
            PedidoEstado.EN_PREPARACION
        ]
    ).count()

    anuladas = pedido.objects.filter(
        estado=PedidoEstado.CANCELADO
    ).count()

    total_facturado = pedido.objects.filter(
        estado=PedidoEstado.ENTREGADO
    ).aggregate(
        total=Sum('total')
    )['total'] or 0

    facturas = []

    for p in pedidos:
        detalles = p.detallepedido.all()

        productos = []

        for detalle in detalles:
            productos.append({
                'nombre': detalle.producto.nombre,
                'cantidad': detalle.cantidad,
                'precio': detalle.precioUnit,
                'subtotal': detalle.cantidad * detalle.precioUnit,
            })

        facturas.append({
            'pedido': p,
            'numero': numero_factura(p.id),
            'cliente': p.cliente.nombre,
            'fecha': p.createdAt,
            'total': p.total,
            'estado': obtener_estado_factura(p.estado),
            'metodo': 'Efectivo',
            'productos': productos,
        })

    factura_seleccionada = None

    factura_id = request.GET.get('ver')

    if factura_id and factura_id.isdigit():

        p = pedido.objects.select_related(
            'cliente'
        ).prefetch_related(
            'detallepedido__producto'
        ).filter(
            id=int(factura_id)
        ).first()

        if p:
            productos = []

            for detalle in p.detallepedido.all():
                productos.append({
                    'nombre': detalle.producto.nombre,
                    'cantidad': detalle.cantidad,
                    'precio': detalle.precioUnit,
                    'subtotal': detalle.cantidad * detalle.precioUnit,
                })

            factura_seleccionada = {
                'pedido': p,
                'numero': numero_factura(p.id),
                'cliente': p.cliente.nombre,
                'fecha': p.createdAt,
                'total': p.total,
                'estado': obtener_estado_factura(p.estado),
                'metodo': 'Efectivo',
                'productos': productos,
            }

    contexto = {
        'facturas': facturas,
        'total_facturas': total_facturas,
        'pagadas': pagadas,
        'pendientes': pendientes,
        'anuladas': anuladas,
        'total_facturado': total_facturado,
        'busqueda': busqueda,
        'filtro': filtro,
        'factura_seleccionada': factura_seleccionada,
    }

    return render(
        request,
        'deliapp/facturacion.html',
        contexto
    )


# ==========================================
# EDITAR FACTURA
# ==========================================

def editar_factura(request, pedido_id):

    factura = get_object_or_404(
        pedido.objects.select_related('cliente'),
        id=pedido_id
    )

    if request.method == 'POST':

        cliente_nombre = request.POST.get(
            'cliente',
            ''
        ).strip()

        estado = request.POST.get(
            'estado',
            ''
        )

        if not cliente_nombre:
            messages.error(
                request,
                'El nombre del cliente es obligatorio.'
            )

        elif estado not in PedidoEstado.values:
            messages.error(
                request,
                'El estado seleccionado no es válido.'
            )

        else:

            factura.cliente.nombre = cliente_nombre
            factura.cliente.save(update_fields=['nombre'])

            factura.estado = estado
            factura.save(update_fields=['estado'])

            messages.success(
                request,
                'La factura se actualizó correctamente.'
            )

            return redirect('facturacion')

    return render(
        request,
        'facturacion/editar_factura.html',
        {
            'factura': factura,
            'numero_factura': numero_factura(factura.id),
            'estados': PedidoEstado.choices,
        }
    )


# ==========================================
# ELIMINAR FACTURA
# ==========================================

@require_POST
def eliminar_factura(request, pedido_id):

    factura = get_object_or_404(
        pedido,
        id=pedido_id
    )

    factura.delete()

    messages.success(
        request,
        'La factura y su pedido asociado fueron eliminados correctamente.'
    )

    return redirect('facturacion')


# =========================================================
# ADMINISTRACIÓN DE PEDIDOS
# =========================================================

@solo_administrador
def pedidos_admin(request):
    """
    Lista los pedidos para su consulta y administración.
    """

    busqueda = request.GET.get('buscar', '').strip()
    estado_filtro = request.GET.get('estado', '')

    pedidos_lista = (
        pedido.objects
        .select_related('cliente')
        .prefetch_related('detallepedido__producto')
        .order_by('-createdAt')
    )

    if busqueda:
        if busqueda.isdigit():
            pedidos_lista = pedidos_lista.filter(
                Q(id=int(busqueda)) |
                Q(cliente__nombre__icontains=busqueda) |
                Q(cliente__telefono__icontains=busqueda)
            )
        else:
            pedidos_lista = pedidos_lista.filter(
                Q(cliente__nombre__icontains=busqueda) |
                Q(cliente__telefono__icontains=busqueda)
            )

    if estado_filtro in PedidoEstado.values:
        pedidos_lista = pedidos_lista.filter(
            estado=estado_filtro
        )

    context = {
        'pedidos': pedidos_lista,
        'busqueda': busqueda,
        'estado_filtro': estado_filtro,
        'estados': PedidoEstado.choices,
        'total_pedidos': pedido.objects.count(),
        'pendientes': pedido.objects.filter(
            estado=PedidoEstado.PENDIENTE
        ).count(),
        'en_preparacion': pedido.objects.filter(
            estado=PedidoEstado.EN_PREPARACION
        ).count(),
        'entregados': pedido.objects.filter(
            estado=PedidoEstado.ENTREGADO
        ).count(),
        'cancelados': pedido.objects.filter(
            estado=PedidoEstado.CANCELADO
        ).count(),
    }

    return render(
        request,
        'deliapp/pedidos_admin.html',
        context
    )


@solo_administrador
@require_POST
def actualizar_estado_pedido(request, pedido_id):
    """
    Actualiza el estado de un pedido desde el panel.
    """

    pedido_actual = get_object_or_404(
        pedido,
        id=pedido_id
    )

    nuevo_estado = request.POST.get(
        'estado',
        ''
    ).strip()

    if nuevo_estado not in PedidoEstado.values:
        messages.error(
            request,
            'El estado seleccionado no es válido.'
        )
        return redirect('pedidos_admin')

    pedido_actual.estado = nuevo_estado

    pedido_actual.save(
        update_fields=['estado']
    )

    messages.success(
        request,
        f'El pedido #{pedido_actual.id} fue actualizado correctamente.'
    )

    return redirect('pedidos_admin')


# =========================================================
# PANEL DE EMPLEADOS
# =========================================================

@solo_empleado_o_admin
def empleado_pedidos(request):
    """
    Panel operativo para empleados y administradores.
    """
    pedidos_lista = (
        pedido.objects
        .select_related('cliente')
        .prefetch_related('detallepedido__producto')
        .order_by('-createdAt')
    )

    context = {
        'pedidos': pedidos_lista,
        'total_pedidos': pedidos_lista.count(),
        'pendientes': pedidos_lista.filter(estado=PedidoEstado.PENDIENTE).count(),
        'preparacion': pedidos_lista.filter(estado=PedidoEstado.EN_PREPARACION).count(),
        'completados': pedidos_lista.filter(estado=PedidoEstado.ENTREGADO).count(),
    }

    return render(
        request,
        'deliapp/empleado_pedidos.html',
        context
    )


@solo_empleado_o_admin
@require_http_methods(['PATCH'])
def api_empleado_actualizar_estado(request, pedido_id):
    """
    Actualiza el estado de un pedido mediante AJAX (PATCH) desde el panel de empleados y gestión.
    """
    pedido_actual = get_object_or_404(
        pedido,
        id=pedido_id
    )

    try:
        data = json.loads(request.body or '{}')
        nuevo_estado = str(data.get('estado', '')).strip()

        if nuevo_estado not in PedidoEstado.values:
            return JsonResponse(
                {'error': 'El estado seleccionado no es válido.'},
                status=400
            )

        pedido_actual.estado = nuevo_estado
        pedido_actual.save(update_fields=['estado'])

        return JsonResponse({
            'ok': True,
            'id': pedido_actual.id,
            'estado': pedido_actual.estado,
        })

    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse(
            {'error': 'Datos JSON inválidos.'},
            status=400
        )


# =========================================================
# PANEL DE GESTIÓN DE PEDIDOS (GRÁFICAS Y FILTROS)
# =========================================================

@solo_empleado_o_admin
def gestion_pedidos_page(request):
    """
    Vista principal de Gestión de Pedidos con gráficas y filtros (/gestion/).
    """
    pedidos_qs = (
        pedido.objects
        .select_related('cliente')
        .prefetch_related('detallepedido__producto')
        .order_by('-createdAt')
    )

    pedidos_serializados = []
    for p in pedidos_qs:
        items = [
            {
                'nombre': det.producto.nombre,
                'cantidad': det.cantidad,
                'precio': float(det.precioUnit),
            }
            for det in p.detallepedido.all()
        ]
        pedidos_serializados.append({
            'id': p.id,
            'cliente': p.cliente.nombre,
            'direccion': p.cliente.direccion or 'Sin dirección',
            'total': float(p.total),
            'estado': p.estado,
            'fecha': p.createdAt.isoformat() if p.createdAt else '',
            'items': items,
        })

    return render(
        request,
        'deliapp/gestion.html',
        {
            'pedidos_json': json.dumps(pedidos_serializados),
        }
    )


@solo_empleado_o_admin
@require_http_methods(['GET'])
def api_gestion_pedidos(request):
    """
    Endpoint GET para recargar la lista de pedidos en /gestion/ sin recargar la página.
    """
    pedidos_qs = (
        pedido.objects
        .select_related('cliente')
        .prefetch_related('detallepedido__producto')
        .order_by('-createdAt')
    )

    lista = []
    for p in pedidos_qs:
        lista.append({
            'id': p.id,
            'cliente': p.cliente.nombre,
            'direccion': p.cliente.direccion or 'Sin dirección',
            'total': float(p.total),
            'estado': p.estado,
            'fecha': p.createdAt.isoformat() if p.createdAt else '',
            'items': [
                {
                    'nombre': det.producto.nombre,
                    'cantidad': det.cantidad,
                    'precio': float(det.precioUnit),
                }
                for det in p.detallepedido.all()
            ],
        })

    return JsonResponse(lista, safe=False)

# =========================================================
# PANEL DE CLIENTE
# =========================================================

def cliente_dashboard(request):
    """
    Panel principal del cliente con acceso a servicios e historial de pedidos.
    """
    if request.user.is_authenticated:
        nombre_cliente = (
            request.user.get_full_name().strip()
            or request.user.first_name.strip()
            or request.user.username
        )

        pedidos_cliente = (
            pedido.objects
            .select_related('cliente')
            .prefetch_related('detallepedido__producto')
            .filter(
                Q(cliente__nombre__iexact=nombre_cliente) |
                Q(cliente__nombre__iexact=request.user.username)
            )
            .order_by('-createdAt')
        )
    else:
        nombre_cliente = "Cliente"
        pedidos_cliente = pedido.objects.none()

    context = {
        'nombre_cliente': nombre_cliente,
        'pedidos': pedidos_cliente,
    }

    return render(
        request,
        'deliapp/cliente_dashboard.html',
        context
    )