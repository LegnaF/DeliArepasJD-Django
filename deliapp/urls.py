from django.urls import path
from . import views

urlpatterns = [
    # Ruta principal nombrada 'inicio'
    path('', views.home_page, name='inicio'),
    path('menu/', views.menu_page, name='menu'),
    path('producto/<int:id>/', views.detalle_producto, name='detalle_producto'),
    
    # API AJAX para procesar pedidos desde el carrito
    path('api/pedidos/', views.crear_pedido, name='crear_pedido'),

    # Gestión de PQRS
    path('gestion-pqr/', views.gestion_pqr_page, name='gestion_pqr'),
    path('gestion-pqr/editar/<int:id>/', views.editar_pqr, name='editar_pqr'),
    path('gestion-pqr/eliminar/<int:id>/', views.eliminar_pqr, name='eliminar_pqr'),

    # Rutas auxiliares llamadas por el Navbar (evitan errores de NoReverseMatch)
    path('login/', views.login, name='login'),
    path('logout/', views.home_page, name='logout'),
    path('admin-dashboard/', views.home_page, name='admin_dashboard'),
    path('empleado-pedidos/', views.home_page, name='empleado_pedidos'),
    path('gestion/', views.home_page, name='gestion'),
    path('facturacion/', views.home_page, name='facturacion'),
    path('usuarios/', views.home_page, name='usuarios'),
    path('cliente/', views.home_page, name='cliente'),
]