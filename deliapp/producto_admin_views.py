from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render, redirect, get_object_or_404

from .forms import ProductoForm
from .models import producto


@staff_member_required
def productos_admin(request):
    productos = producto.objects.all().order_by('-id')

    return render(request, 'deliapp/productos_admin.html', {
        'productos': productos,
        'total_productos': productos.count(),
        'productos_activos': productos.filter(activo=True).count(),
        'productos_agotados': productos.filter(stock=0).count(),
    })


@staff_member_required
def producto_crear(request):
    if request.method == 'POST':
        form = ProductoForm(request.POST, request.FILES)

        if form.is_valid():
            nuevo_producto = form.save(commit=False)
            nuevo_producto.categoria = 'Arepas'
            nuevo_producto.save()

            messages.success(
                request,
                'La arepa se creó correctamente.'
            )
            return redirect('productos_admin')
    else:
        form = ProductoForm(initial={
            'categoria': 'Arepas',
            'activo': True,
            'descuento': 0,
            'stock': 0,
        })

    return render(request, 'deliapp/producto_formulario.html', {
        'form': form,
        'titulo': 'Registrar nueva arepa',
        'descripcion': 'Agrega la información y fotografía de una nueva arepa.',
        'accion': 'Crear arepa',
    })


@staff_member_required
def producto_editar(request, id):
    item = get_object_or_404(producto, id=id)

    if request.method == 'POST':
        form = ProductoForm(
            request.POST,
            request.FILES,
            instance=item
        )

        if form.is_valid():
            producto_editado = form.save(commit=False)
            producto_editado.categoria = 'Arepas'
            producto_editado.save()

            messages.success(
                request,
                'La información de la arepa se actualizó correctamente.'
            )
            return redirect('productos_admin')
    else:
        form = ProductoForm(instance=item)

    return render(request, 'deliapp/producto_formulario.html', {
        'form': form,
        'producto': item,
        'titulo': 'Editar arepa',
        'descripcion': 'Actualiza los datos o reemplaza su fotografía.',
        'accion': 'Guardar cambios',
    })


@staff_member_required
def producto_eliminar(request, id):
    item = get_object_or_404(producto, id=id)

    if request.method == 'POST':
        nombre = item.nombre
        item.delete()

        messages.success(
            request,
            f'La arepa "{nombre}" fue eliminada.'
        )
        return redirect('productos_admin')

    return render(request, 'deliapp/producto_confirmar_eliminar.html', {
        'producto': item,
    })