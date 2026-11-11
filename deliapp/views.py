import json
from datetime import timedelta
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.contrib import messages
from django.utils import timezone
from django.db import transaction
from .forms import PQRForm
from .models import producto, pqr, cliente, pedido, detallepedido, PedidoEstado


def home_page(request):
    """
    Vista principal de la aplicación.
    Maneja la presentación del inicio y el procesamiento del formulario de PQR.
    """
    if request.method == 'POST':
        form = PQRForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, '¡Mensaje enviado con éxito! Nos pondremos en contacto pronto.')
            return redirect('inicio')
        else:
            messages.error(request, 'No se pudo enviar el mensaje. Verifica los datos ingresados.')
    else:
        form = PQRForm()

    productos_destacados = producto.objects.filter(activo=True)[:4]

    context = {
        'form': form,
        'productos': productos_destacados,
    }
    return render(request, 'deliapp/index.html', context)

from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login
from django.contrib import messages
from django.contrib.auth.forms import AuthenticationForm

def login(request):
    """
    Vista de inicio de sesión que maneja tanto la petición GET 
    (mostrar el formulario) como la petición POST (procesar el login).
    """
    # Si el usuario ya está autenticado, lo redirigimos a la página principal o menú
    if request.user.is_authenticated:
        return redirect('inicio')  # Cambia 'inicio' por la ruta a donde va el usuario logueado

    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            user = authenticate(username=username, password=password)
            
            if user is not None:
                login(request, user)
                messages.success(request, f'¡Bienvenido de nuevo, {user.username}!')
                
                # Redirigir a la página a la que intentaba entrar o a 'inicio'
                next_url = request.GET.get('next', 'inicio')
                return redirect(next_url)
            else:
                messages.error(request, 'Usuario o contraseña incorrectos.')
        else:
            messages.error(request, 'Por favor, verifica tus datos. Hay un error en el formulario.')
    else:
        form = AuthenticationForm()

    context = {
        'form': form,
        'vista': 'login', # Para que el HTML sepa que estamos en la vista de login
    }
    
    return render(request, 'deliapp/login.html', context)


def menu_page(request):
    """
    Vista del catálogo de productos.
    """
    productos = producto.objects.filter(
        activo=True
    ).order_by('nombre')

    categorias_bd = producto.objects.filter(
        activo=True
    ).values_list(
        'categoria',
        flat=True
    ).distinct()

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


def detalle_producto(request, id):
    """
    Vista para ver el detalle individual de un producto.
    """
    prod = get_object_or_404(producto, id=id, activo=True)
    return render(request, 'deliapp/detalle_producto.html', {'producto': prod})


def crear_pedido(request):
    """
    Endpoint AJAX para registrar un pedido realizado desde el carrito de compras.
    Crea el cliente, el pedido y cada uno de los detalles en la base de datos PostgreSQL.
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'Método no permitido'}, status=405)

    try:
        data = json.loads(request.body)
        cliente_nombre = data.get('clienteNombre', '').strip()
        telefono = data.get('telefono', '').strip() or 'Sin teléfono'
        direccion = data.get('direccion', '').strip()
        items = data.get('items', [])

        if not cliente_nombre or not direccion:
            return JsonResponse({'error': 'Por favor ingresa tu nombre y dirección de entrega.'}, status=400)

        if not items:
            return JsonResponse({'error': 'El carrito está vacío.'}, status=400)

        with transaction.atomic():
            # 1. Registrar cliente
            nuevo_cliente = cliente.objects.create(
                nombre=cliente_nombre,
                telefono=telefono,
                direccion=direccion
            )

            # 2. Registrar pedido base
            nuevo_pedido = pedido.objects.create(
                cliente=nuevo_cliente,
                estado=PedidoEstado.PENDIENTE,
                total=0.0
            )

            total_acumulado = 0.0

            # 3. Guardar detalles y descontar stock de los productos
            for item in items:
                prod_id = item.get('productoId')
                cantidad = int(item.get('cantidad', 1))
                precio_unitario = float(item.get('precioUnitario', 0))

                prod_obj = get_object_or_404(producto, id=prod_id)

                if prod_obj.stock >= cantidad:
                    prod_obj.stock -= cantidad
                    prod_obj.save()

                detallepedido.objects.create(
                    pedido=nuevo_pedido,
                    producto=prod_obj,
                    cantidad=cantidad,
                    precioUnit=precio_unitario
                )

                total_acumulado += precio_unitario * cantidad

            # 4. Actualizar total final del pedido
            nuevo_pedido.total = total_acumulado
            nuevo_pedido.save()

        return JsonResponse({
            'ok': True,
            'id': nuevo_pedido.id,
            'total': nuevo_pedido.total,
            'cliente': nuevo_cliente.nombre
        })

    except Exception as e:
        return JsonResponse({'error': f'Error al registrar el pedido: {str(e)}'}, status=500)


def gestion_pqr_page(request):
    """
    Renderiza el panel de gestión de PQRS con estadísticas.
    """
    lista_pqrs = pqr.objects.all().order_by('-createdAt')
    hace_siete_dias = timezone.now() - timedelta(days=7)
    recientes_count = pqr.objects.filter(createdAt__gte=hace_siete_dias).count()

    context = {
        'pqrs': lista_pqrs,
        'total_count': lista_pqrs.count(),
        'recientes_count': recientes_count,
    }
    return render(request, 'deliapp/gestion_pqr.html', context)


def editar_pqr(request, id):
    """
    Endpoint para actualizar una PQR existente vía AJAX.
    """
    item = get_object_or_404(pqr, id=id)
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            item.nombre = data.get('nombre', item.nombre)
            item.contacto = data.get('contacto', item.contacto)
            item.mensaje = data.get('mensaje', item.mensaje)
            item.save()
            return JsonResponse({'status': 'success', 'message': 'PQR actualizada correctamente'})
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)
    return JsonResponse({'error': 'Método no permitido'}, status=405)


def eliminar_pqr(request, id):
    """
    Endpoint para eliminar una PQR vía AJAX.
    """
    item = get_object_or_404(pqr, id=id)
    if request.method in ['POST', 'DELETE']:
        item.delete()
        return JsonResponse({'status': 'success', 'message': 'PQR eliminada correctamente'})
    return JsonResponse({'error': 'Método no permitido'}, status=405)