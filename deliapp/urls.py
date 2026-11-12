
from django.contrib.auth import views as django_auth_views
from django.urls import path, reverse_lazy

from . import auth_views, views


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
    # PEDIDOS
    # =====================================================

    path(
        'api/pedidos/',
        views.crear_pedido,
        name='crear_pedido'
    ),

    # =====================================================
    # GESTIÓN DE PQRS
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
        django_auth_views.PasswordResetView.as_view(
            template_name='deliapp/recuperar_password.html',
            email_template_name='registration/password_reset_email.txt',
            html_email_template_name='registration/password_reset_email.html',
            subject_template_name='registration/password_reset_subject.txt',
            from_email=None,
            extra_email_context={
                'nombre_negocio': 'Deli Arepas JD',
            },
            success_url=reverse_lazy('password_reset_done'),
        ),
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
            success_url=reverse_lazy('password_reset_complete')
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

    # =====================================================
    # MÓDULOS AUXILIARES
    # =====================================================

    path(
        'admin-dashboard/',
        views.home_page,
        name='admin_dashboard'
    ),

    path(
        'empleado-pedidos/',
        views.home_page,
        name='empleado_pedidos'
    ),

    path(
        'gestion/',
        views.home_page,
        name='gestion'
    ),

    path(
        'facturacion/',
        views.home_page,
        name='facturacion'
    ),

    path(
        'usuarios/',
        views.home_page,
        name='usuarios'
    ),

    path(
        'cliente/',
        views.home_page,
        name='cliente'
    ),

]
