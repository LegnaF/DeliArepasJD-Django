from django import forms
from .models import pqr, producto, cliente
from django import contrib
from django.contrib.auth.forms import AuthenticationForm

class PQRForm(forms.ModelForm):
    """
    Formulario para la sección de Peticiones, Quejas y Reclamos (PQRs).
    Conecta directamente con el modelo `pqr`.
    """
    class Meta:
        model = pqr
        fields = ['nombre', 'contacto', 'mensaje']
        widgets = {
            'nombre': forms.TextInput(attrs={
                'class': 'formInput',
                'placeholder': 'Escribe tu nombre...',
                'required': True,
            }),
            'contacto': forms.TextInput(attrs={
                'class': 'formInput',
                'placeholder': 'Escribe tu correo o número...',
                'required': True,
            }),
            'mensaje': forms.Textarea(attrs={
                'class': 'formTextarea',
                'placeholder': 'Escribe tu consulta o pedido aquí...',
                'rows': 4,
                'required': True,
            }),
        }


class ProductoForm(forms.ModelForm):
    """
    Formulario para la creación y edición de productos desde el panel o vistas de administración.
    """
    class Meta:
        model = producto
        fields = ['nombre', 'descripcion', 'precio', 'stock', 'categoria', 'imagen', 'descuento', 'activo']
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'formInput', 'placeholder': 'Nombre del producto'}),
            'descripcion': forms.Textarea(attrs={'class': 'formTextarea', 'rows': 3, 'placeholder': 'Descripción del producto'}),
            'precio': forms.NumberInput(attrs={'class': 'formInput', 'step': '0.01', 'placeholder': '0.00'}),
            'stock': forms.NumberInput(attrs={'class': 'formInput', 'placeholder': 'Cantidad disponible'}),
            'categoria': forms.TextInput(attrs={'class': 'formInput', 'placeholder': 'Categoría'}),
            'imagen': forms.TextInput(attrs={'class': 'formInput', 'placeholder': '/arepa3.jpg'}),
            'descuento': forms.NumberInput(attrs={'class': 'formInput', 'placeholder': '0'}),
            'activo': forms.CheckboxInput(attrs={'class': 'formCheckbox'}),
        }


class ClienteForm(forms.ModelForm):
    """
    Formulario para el registro o actualización de datos del cliente.
    """
    class Meta:
        model = cliente
        fields = ['nombre', 'telefono', 'direccion']
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'formInput', 'placeholder': 'Nombre completo'}),
            'telefono': forms.TextInput(attrs={'class': 'formInput', 'placeholder': 'Teléfono de contacto'}),
            'direccion': forms.TextInput(attrs={'class': 'formInput', 'placeholder': 'Dirección de entrega'}),
        }





class CustomLoginForm(AuthenticationForm):
    username = forms.CharField(
        widget=forms.TextInput(attrs={
            'class': 'formInput',
            'placeholder': 'Correo o usuario'
        })
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'formInput',
            'placeholder': '••••••••'
        })
    )