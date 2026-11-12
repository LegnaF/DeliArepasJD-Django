
from django import forms
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import (
    get_user_model,
    login,
    logout,
)
from django.contrib.auth.forms import (
    AuthenticationForm,
    UserCreationForm,
    PasswordResetForm,
)
from django.core.mail import BadHeaderError
from django.core.exceptions import ValidationError
from django.shortcuts import redirect, render
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST


User = get_user_model()


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

    form = AuthenticationForm(
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
            'No pudimos iniciar sesión. Revisa tu usuario y contraseña.'
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

            if not settings.EMAIL_HOST_USER or not settings.EMAIL_HOST_PASSWORD:

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
                        from_email=settings.DEFAULT_FROM_EMAIL,
                        email_template_name=(
                            'registration/password_reset_email.html'
                        ),
                        subject_template_name=(
                            'registration/password_reset_subject.txt'
                        ),
                        html_email_template_name=(
                            'registration/password_reset_email.html'
                        ),
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

                except BadHeaderError:

                    messages.error(
                        request,
                        'No se pudo enviar el correo. '
                        'Verifica la información e inténtalo nuevamente.'
                    )

                except Exception:

                    messages.error(
                        request,
                        'Ocurrió un problema al enviar el correo. '
                        'Verifica la configuración del servicio de correo '
                        'e inténtalo nuevamente.'
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
