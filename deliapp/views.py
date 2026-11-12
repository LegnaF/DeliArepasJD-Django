
import json
from datetime import timedelta

from django.contrib import messages
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone

from .forms import PQRForm
from .models import (
    producto,
    pqr,
    cliente,
    pedido,
    detallepedido,
    PedidoEstado,
)


# =========================================================
# INICIO
# =========================================================

def home_page(request):
    """
    Página principal y formulario de PQR.
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
    )[:4]

    context = {
        'form': form,
        'productos': productos_destacados,
    }

    return render(request, 'deliapp/index.html', context)


# =========================================================
# MENÚ
# =========================================================

def menu_page(request):
    """
    Catálogo de productos activos.
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

    return render(request, 'deliapp/menu.html', context)


# =========================================================
# DETALLE DEL PRODUCTO
# =========================================================

def detalle_producto(request, id):
    """
    Muestra la información de un producto.
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

def crear_pedido(request):
    """
    Registra un pedido enviado desde el carrito mediante AJAX.
    """

    if request.method != 'POST':
        return JsonResponse(
            {'error': 'Método no permitido.'},
            status=405
        )

    try:
        data = json.loads(request.body or '{}')

        cliente_nombre = str(
            data.get('clienteNombre', '')
        ).strip()

        telefono = str(
            data.get('telefono', '')
        ).strip() or 'Sin teléfono'

        direccion = str(
            data.get('direccion', '')
        ).strip()

        items = data.get('items', [])

        if not cliente_nombre or not direccion:
            return JsonResponse(
                {
                    'error': 'Por favor ingresa tu nombre y dirección de entrega.'
                },
                status=400
            )

        if not isinstance(items, list) or not items:
            return JsonResponse(
                {'error': 'El carrito está vacío.'},
                status=400
            )

        # Validar todos los productos antes de guardar el pedido.
        productos_pedido = []
        total_acumulado = 0.0

        for item in items:
            try:
                producto_id = int(item.get('productoId'))
                cantidad = int(item.get('cantidad', 1))
                precio_unitario = float(
                    item.get('precioUnitario', 0)
                )
            except (TypeError, ValueError, AttributeError):
                return JsonResponse(
                    {'error': 'Hay información inválida en el carrito.'},
                    status=400
                )

            if cantidad < 1:
                return JsonResponse(
                    {'error': 'La cantidad de productos debe ser mayor que cero.'},
                    status=400
                )

            if precio_unitario < 0:
                return JsonResponse(
                    {'error': 'El precio del producto no es válido.'},
                    status=400
                )

            prod_obj = get_object_or_404(
                producto,
                id=producto_id,
                activo=True
            )

            if prod_obj.stock < cantidad:
                return JsonResponse(
                    {
                        'error': (
                            f'No hay suficiente inventario de {prod_obj.nombre}. '
                            f'Disponibles: {prod_obj.stock}.'
                        )
                    },
                    status=400
                )

            productos_pedido.append({
                'producto': prod_obj,
                'cantidad': cantidad,
                'precio': precio_unitario,
            })

            total_acumulado += precio_unitario * cantidad

        # Guardar todo en una transacción.
        with transaction.atomic():

            nuevo_cliente = cliente.objects.create(
                nombre=cliente_nombre,
                telefono=telefono,
                direccion=direccion
            )

            nuevo_pedido = pedido.objects.create(
                cliente=nuevo_cliente,
                estado=PedidoEstado.PENDIENTE,
                total=0.0
            )

            for item in productos_pedido:
                prod_obj = item['producto']
                cantidad = item['cantidad']

                prod_obj.stock -= cantidad
                prod_obj.save(update_fields=['stock'])

                detallepedido.objects.create(
                    pedido=nuevo_pedido,
                    producto=prod_obj,
                    cantidad=cantidad,
                    precioUnit=item['precio']
                )

            nuevo_pedido.total = total_acumulado
            nuevo_pedido.save(update_fields=['total'])

        return JsonResponse({
            'ok': True,
            'id': nuevo_pedido.id,
            'total': nuevo_pedido.total,
            'cliente': nuevo_cliente.nombre,
        })

    except json.JSONDecodeError:
        return JsonResponse(
            {'error': 'La información enviada no tiene un formato válido.'},
            status=400
        )

    except Exception:
        return JsonResponse(
            {
                'error': 'Ocurrió un problema al registrar el pedido. Inténtalo nuevamente.'
            },
            status=500
        )


# =========================================================
# GESTIÓN DE PQR
# =========================================================

def gestion_pqr_page(request):
    """
    Panel de gestión de PQR y estadísticas.
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


def editar_pqr(request, id):
    """
    Actualiza una PQR mediante AJAX.
    """

    if request.method != 'POST':
        return JsonResponse(
            {'error': 'Método no permitido.'},
            status=405
        )

    item = get_object_or_404(pqr, id=id)

    try:
        data = json.loads(request.body or '{}')

        item.nombre = data.get('nombre', item.nombre)
        item.contacto = data.get('contacto', item.contacto)
        item.mensaje = data.get('mensaje', item.mensaje)

        item.save()

        return JsonResponse({
            'status': 'success',
            'message': 'PQR actualizada correctamente.',
        })

    except json.JSONDecodeError:
        return JsonResponse(
            {'error': 'Los datos enviados no son válidos.'},
            status=400
        )

    except Exception:
        return JsonResponse(
            {'error': 'No fue posible actualizar la PQR.'},
            status=500
        )


def eliminar_pqr(request, id):
    """
    Elimina una PQR mediante AJAX.
    """

    if request.method not in ['POST', 'DELETE']:
        return JsonResponse(
            {'error': 'Método no permitido.'},
            status=405
        )

    item = get_object_or_404(pqr, id=id)
    item.delete()

    return JsonResponse({
        'status': 'success',
        'message': 'PQR eliminada correctamente.',
    })
