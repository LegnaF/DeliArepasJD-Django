from django.contrib import admin
from .models import cliente, producto, pedido, detallepedido, usuario, pqr

@admin.register(cliente)
class ClienteAdmin(admin.ModelAdmin):
    list_display = ('id', 'nombre', 'telefono', 'direccion', 'createdAt')
    search_fields = ('nombre', 'telefono')

@admin.register(producto)
class ProductoAdmin(admin.ModelAdmin):
    list_display = ('id', 'nombre', 'precio', 'stock', 'categoria', 'activo', 'createdAt')
    list_filter = ('categoria', 'activo')
    search_fields = ('nombre',)

class DetallePedidoInline(admin.TabularInline):
    model = detallepedido
    extra = 1

@admin.register(pedido)
class PedidoAdmin(admin.ModelAdmin):
    list_display = ('id', 'cliente', 'estado', 'total', 'createdAt')
    list_filter = ('estado',)
    inlines = [DetallePedidoInline]

@admin.register(usuario)
class UsuarioAdmin(admin.ModelAdmin):
    list_display = ('id', 'nombre', 'email', 'rol', 'intentosFallidos', 'createdAt')
    list_filter = ('rol',)
    search_fields = ('nombre', 'email')

@admin.register(pqr)
class PQRAdmin(admin.ModelAdmin):
    list_display = ('id', 'nombre', 'contacto', 'createdAt')
    search_fields = ('nombre', 'contacto', 'mensaje')