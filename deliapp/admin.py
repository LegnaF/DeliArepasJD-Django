from django.contrib import admin
from django.utils.html import format_html

from .models import (
    cliente,
    producto,
    pedido,
    detallepedido,
    usuario,
    pqr,
)


@admin.register(cliente)
class ClienteAdmin(admin.ModelAdmin):
    list_display = ('id', 'nombre', 'telefono', 'direccion', 'createdAt')
    search_fields = ('nombre', 'telefono')


@admin.register(producto)
class ProductoAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'vista_previa',
        'nombre',
        'precio',
        'stock',
        'categoria',
        'activo',
        'createdAt',
    )
    list_filter = ('categoria', 'activo')
    search_fields = ('nombre', 'descripcion')
    list_editable = ('precio', 'stock', 'activo')
    readonly_fields = ('vista_previa', 'createdAt')
    fieldsets = (
        ('Información de la arepa', {
            'fields': ('nombre', 'descripcion', 'categoria'),
        }),
        ('Precio e inventario', {
            'fields': ('precio', 'stock', 'descuento', 'activo'),
        }),
        ('Fotografía', {
            'fields': ('imagen_archivo', 'imagen', 'vista_previa'),
        }),
        ('Registro', {
            'fields': ('createdAt',),
        }),
    )

    @admin.display(description='Fotografía')
    def vista_previa(self, obj):
        if obj and obj.imagen_archivo:
            return format_html(
                '<img src="{}" style="width:76px;height:64px;'
                'object-fit:cover;border-radius:10px;" />',
                obj.imagen_archivo.url,
            )

        return 'Sin fotografía'


class DetallePedidoInline(admin.TabularInline):
    model = detallepedido
    extra = 1


@admin.register(pedido)
class PedidoAdmin(admin.ModelAdmin):
    list_display = ('id', 'cliente', 'estado', 'total', 'createdAt')
    list_filter = ('estado',)
    search_fields = ('cliente__nombre',)
    inlines = [DetallePedidoInline]


@admin.register(usuario)
class UsuarioAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'nombre',
        'email',
        'rol',
        'intentosFallidos',
        'createdAt',
    )
    list_filter = ('rol',)
    search_fields = ('nombre', 'email')


@admin.register(pqr)
class PQRAdmin(admin.ModelAdmin):
    list_display = ('id', 'nombre', 'contacto', 'createdAt')
    search_fields = ('nombre', 'contacto', 'mensaje')