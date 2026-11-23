from django.contrib.auth import views as django_auth_views
from django.urls import path

from . import auth_views, views, producto_admin_views


urlpatterns = [

    # =====================================================
    # PÁGINA PRINCIPAL
    # =====================================================

    path(
        '',
        views.home_page,
        name='inicio'
    ),

    # =====================================================
    # MENÚ Y PRODUCTOS
    # =====================================================

    path(
        'menu/',
        views.menu_page,
        name='menu'
    ),

    path(
        'producto/<int:id>/',
        views.detalle_producto,
        name='detalle_producto'
    ),

    # =====================================================
    # PEDIDOS, PAGOS Y CONSULTA PÚBLICA
    # =====================================================

    path(
        'api/pedidos/',
        views.crear_pedido,
        name='crear_pedido'
    ),

    path(
        'api/pagos/iniciar/',
        views.api_iniciar_pago,
        name='api_iniciar_pago'
    ),

    path(
        'pagos/retorno/',
        views.retorno_pago,
        name='retorno_pago'
    ),

    path(
        'api/pagos/webhook/',
        views.api_webhook_pago,
        name='api_webhook_pago'
    ),

    path(
        'consultar-pedido/',
        views.consultar_pedido,
        name='consultar_pedido'
    ),

    # =====================================================
    # PANEL ADMINISTRATIVO
    # =====================================================

    path(
        'admin-dashboard/',
        views.admin_dashboard,
        name='admin_dashboard'
    ),

    path(
        'api/stats/',
        views.api_stats,
        name='api_stats'
    ),

    # =====================================================
    # ADMINISTRACIÓN DE PRODUCTOS
    # =====================================================

    path(
        'admin-dashboard/productos/',
        producto_admin_views.productos_admin,
        name='productos_admin'
    ),

    path(
        'admin-dashboard/productos/crear/',
        producto_admin_views.producto_crear,
        name='producto_crear'
    ),

    path(
        'admin-dashboard/productos/editar/<int:id>/',
        producto_admin_views.producto_editar,
        name='producto_editar'
    ),

    path(
        'admin-dashboard/productos/eliminar/<int:id>/',
        producto_admin_views.producto_eliminar,
        name='producto_eliminar'
    ),

    # =====================================================
    # ADMINISTRACIÓN DE PEDIDOS
    # =====================================================

    path(
        'admin-dashboard/pedidos/',
        views.pedidos_admin,
        name='pedidos_admin'
    ),

    path(
        'admin-dashboard/pedidos/<int:pedido_id>/estado/',
        views.actualizar_estado_pedido,
        name='actualizar_estado_pedido'
    ),

        path(
        'admin-dashboard/pedidos/<int:pedido_id>/editar/',
        views.api_editar_pedido_admin,
        name='api_editar_pedido_admin'
    ),

    # =====================================================
    # ADMINISTRACIÓN DE USUARIOS
    # =====================================================

    path(
        'usuarios/',
        views.usuarios_page,
        name='usuarios'
    ),

    path(
        'api/usuarios/',
        views.api_usuarios,
        name='api_usuarios'
    ),

    # =====================================================
    # GESTIÓN DE PQR
    # =====================================================

    path(
        'gestion-pqr/',
        views.gestion_pqr_page,
        name='gestion_pqr'
    ),

    path(
        'gestion-pqr/editar/<int:id>/',
        views.editar_pqr,
        name='editar_pqr'
    ),

    path(
        'gestion-pqr/eliminar/<int:id>/',
        views.eliminar_pqr,
        name='eliminar_pqr'
    ),

    # =====================================================
    # FACTURACIÓN
    # =====================================================

    path(
        'facturacion/',
        views.facturacion,
        name='facturacion'
    ),

    path(
        'facturacion/<int:pedido_id>/editar/',
        views.editar_factura,
        name='editar_factura'
    ),

    path(
        'facturacion/<int:pedido_id>/eliminar/',
        views.eliminar_factura,
        name='eliminar_factura'
    ),

    # =====================================================
    # PANEL DE EMPLEADOS
    # =====================================================

    path(
        'empleado-pedidos/',
        views.empleado_pedidos,
        name='empleado_pedidos'
    ),

    path(
        'api/empleado/pedidos/<int:pedido_id>/',
        views.api_empleado_actualizar_estado,
        name='api_empleado_actualizar_estado'
    ),

    # =====================================================
    # GESTIÓN GENERAL DE PEDIDOS
    # =====================================================

    path(
        'gestion/',
        views.gestion_pedidos_page,
        name='gestion'
    ),

    path(
        'api/gestion/pedidos/',
        views.api_gestion_pedidos,
        name='api_gestion_pedidos'
    ),

    # =====================================================
    # MÓDULO DE CLIENTE
    # =====================================================

    path(
        'cliente/',
        views.cliente_dashboard,
        name='cliente'
    ),

    # =====================================================
    # AUTENTICACIÓN
    # =====================================================

    path(
        'login/',
        auth_views.login_usuario,
        name='login'
    ),

    path(
        'registro/',
        auth_views.registro_usuario,
        name='register'
    ),

    path(
        'logout/',
        auth_views.cerrar_sesion,
        name='logout'
    ),

    # =====================================================
    # RECUPERACIÓN DE CONTRASEÑA
    # =====================================================

    path(
        'recuperar-contrasena/',
        auth_views.recuperar_password,
        name='password_reset'
    ),

    path(
        'recuperar-contrasena/enviado/',
        django_auth_views.PasswordResetDoneView.as_view(
            template_name='deliapp/password_reset_done.html'
        ),
        name='password_reset_done'
    ),

    path(
        'restablecer-contrasena/<uidb64>/<token>/',
        django_auth_views.PasswordResetConfirmView.as_view(
            template_name='deliapp/restablecer_password.html',
            success_url='/restablecer-contrasena/completado/'
        ),
        name='password_reset_confirm'
    ),

    path(
        'restablecer-contrasena/completado/',
        django_auth_views.PasswordResetCompleteView.as_view(
            template_name='deliapp/password_reset_complete.html'
        ),
        name='password_reset_complete'
    ),

]