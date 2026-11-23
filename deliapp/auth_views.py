import logging
from smtplib import SMTPException

from django import forms
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import (
    authenticate,
    get_user_model,
    login,
    logout,
)
from django.contrib.auth.forms import (
    PasswordResetForm,
    UserCreationForm,
)
from django.core.exceptions import ValidationError
from django.core.mail import BadHeaderError
from django.shortcuts import redirect, render
from django.template import TemplateDoesNotExist
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

logger = logging.getLogger(__name__)

User = get_user_model()


# =====================================================
# FORMULARIO DE INICIO DE SESIÓN POR CORREO
# =====================================================

class EmailAuthenticationForm(forms.Form):
    email = forms.EmailField(
        required=True,
        label='Correo electrónico',
    )
    password = forms.CharField(
        required=True,
        label='Contraseña',
        strip=False,
        widget=forms.PasswordInput,
    )

    def __init__(self, request=None, *args, **kwargs):
        self.request = request
        self.user_cache = None
        super().__init__(*args, **kwargs)

    def clean(self):
        cleaned_data = super().clean()
        email = cleaned_data.get('email', '').strip().lower()
        password = cleaned_data.get('password')

        if email and password:
            usuario_obj = (
                User.objects.filter(email__iexact=email).first()
                or User.objects.filter(username__iexact=email).first()
            )

            if usuario_obj is not None:
                self.user_cache = authenticate(
                    self.request,
                    username=usuario_obj.username,
                    password=password,
                )

            if self.user_cache is None:
                raise ValidationError(
                    'Correo electrónico o contraseña incorrectos.',
                    code='invalid_login',
                )

            if not self.user_cache.is_active:
                raise ValidationError(
                    'Esta cuenta se encuentra inactiva.',
                    code='inactive',
                )

        return cleaned_data

    def get_user(self):
        return self.user_cache


# =====================================================
# FORMULARIO DE REGISTRO
# =====================================================

class RegistroForm(UserCreationForm):

    email = forms.EmailField(
        required=True,
        label='Correo electrónico',
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'ejemplo@correo.com',
            'autocomplete': 'email',
        })
    )

    class Meta:
        model = User
        fields = ('username', 'email')

    def clean_email(self):
        email = self.cleaned_data['email'].strip().lower()

        if User.objects.filter(email__iexact=email).exists():
            raise ValidationError(
                'Este correo electrónico ya está registrado.'
            )

        return email


# =====================================================
# INICIAR SESIÓN
# =====================================================

def login_usuario(request):

    if request.user.is_authenticated:
        return redirect('inicio')

    form = EmailAuthenticationForm(
        request,
        data=request.POST or None
    )

    destino = (
        request.POST.get('next')
        or request.GET.get('next')
        or ''
    )

    if request.method == 'POST':

        if form.is_valid():

            usuario_autenticado = form.get_user()

            login(request, usuario_autenticado)

            messages.success(
                request,
                '¡Bienvenido a Deli Arepas JD!'
            )

            if destino and url_has_allowed_host_and_scheme(
                url=destino,
                allowed_hosts={request.get_host()},
                require_https=request.is_secure()
            ):
                return redirect(destino)

            return redirect('inicio')

        messages.error(
            request,
            'No pudimos iniciar sesión. Revisa tu correo electrónico y contraseña.'
        )

    return render(
        request,
        'deliapp/login.html',
        {
            'form': form,
            'next': destino,
        }
    )


# =====================================================
# REGISTRO DE USUARIOS
# =====================================================

def registro_usuario(request):

    if request.user.is_authenticated:
        return redirect('inicio')

    form = RegistroForm(request.POST or None)

    if request.method == 'POST':

        if form.is_valid():

            usuario = form.save()

            login(
                request,
                usuario,
                backend='django.contrib.auth.backends.ModelBackend'
            )

            messages.success(
                request,
                'Tu cuenta ha sido creada correctamente. '
                '¡Bienvenido a Deli Arepas JD!'
            )

            return redirect('inicio')

    return render(
        request,
        'deliapp/registro.html',
        {
            'form': form,
        }
    )


# =====================================================
# RECUPERAR CONTRASEÑA
# =====================================================

def recuperar_password(request):

    if request.user.is_authenticated:
        return redirect('inicio')

    form = PasswordResetForm(request.POST or None)

    if request.method == 'POST':

        if form.is_valid():

            if (
                not getattr(settings, 'EMAIL_HOST_USER', None)
                or not getattr(settings, 'EMAIL_HOST_PASSWORD', None)
            ):

                logger.error(
                    'Recuperación de contraseña: faltan las credenciales '
                    'EMAIL_HOST_USER o EMAIL_HOST_PASSWORD.'
                )

                messages.error(
                    request,
                    'El servicio de correo todavía no está configurado. '
                    'Por favor, inténtalo más tarde.'
                )

            else:

                try:

                    form.save(
                        request=request,
                        use_https=request.is_secure(),
                        email_template_name='deliapp/registration/password_reset_email.txt',
                        subject_template_name='deliapp/registration/password_reset_subject.txt',
                        html_email_template_name='deliapp/registration/password_reset_email.html',
                        extra_email_context={
                            'nombre_negocio': 'Deli Arepas JD',
                            'dominio': request.get_host(),
                        },
                    )

                    messages.success(
                        request,
                        'Si existe una cuenta activa asociada a ese correo, '
                        'recibirás las instrucciones para recuperar tu '
                        'contraseña. Revisa también la carpeta de spam.'
                    )

                    return redirect('password_reset_done')

                except TemplateDoesNotExist:

                    logger.exception(
                        'No se encontró una plantilla de recuperación '
                        'de contraseña.'
                    )

                    messages.error(
                        request,
                        'No se encontraron las plantillas necesarias '
                        'para enviar la recuperación.'
                    )

                except BadHeaderError:

                    logger.exception(
                        'Error en el encabezado del correo de recuperación.'
                    )

                    messages.error(
                        request,
                        'No se pudo preparar el correo de recuperación.'
                    )

                except (SMTPException, OSError):

                    logger.exception(
                        'Error de conexión al enviar el correo de recuperación.'
                    )

                    messages.error(
                        request,
                        'No fue posible conectar con el servicio de correo. '
                        'Verifica la configuración e inténtalo nuevamente.'
                    )

                except Exception:

                    logger.exception(
                        'Error inesperado durante la recuperación '
                        'de contraseña.'
                    )

                    messages.error(
                        request,
                        'Ocurrió un problema al procesar la recuperación. '
                        'Inténtalo nuevamente.'
                    )

    return render(
        request,
        'deliapp/recuperar_password.html',
        {
            'form': form,
        }
    )


# =====================================================
# CERRAR SESIÓN
# =====================================================

@require_POST
def cerrar_sesion(request):

    if request.user.is_authenticated:

        logout(request)

        messages.success(
            request,
            'Has cerrado sesión correctamente.'
        )

    return redirect('inicio')