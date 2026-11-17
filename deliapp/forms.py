
from django import forms
from django.contrib.auth.forms import AuthenticationForm

from .models import pqr, producto, cliente


# =========================================================
# FORMULARIO DE PQR
# =========================================================

class PQRForm(forms.ModelForm):

    class Meta:
        model = pqr

        fields = [
            'nombre',
            'contacto',
            'mensaje',
        ]

        labels = {
            'nombre': 'Nombre completo',
            'contacto': 'Correo electrónico o teléfono',
            'mensaje': 'Mensaje',
        }

        widgets = {
            'nombre': forms.TextInput(attrs={
                'class': 'formInput',
                'placeholder': 'Escribe tu nombre...',
                'autocomplete': 'name',
                'required': True,
                'maxlength': 150,
            }),

            'contacto': forms.TextInput(attrs={
                'class': 'formInput',
                'placeholder': 'Escribe tu correo o número...',
                'autocomplete': 'email',
                'required': True,
                'maxlength': 150,
            }),

            'mensaje': forms.Textarea(attrs={
                'class': 'formTextarea',
                'placeholder': 'Escribe tu consulta o pedido aquí...',
                'rows': 4,
                'required': True,
            }),
        }

    def clean_nombre(self):
        nombre = self.cleaned_data.get('nombre', '').strip()

        if len(nombre) < 3:
            raise forms.ValidationError(
                'El nombre debe tener al menos 3 caracteres.'
            )

        return nombre

    def clean_contacto(self):
        contacto = self.cleaned_data.get('contacto', '').strip()

        if len(contacto) < 5:
            raise forms.ValidationError(
                'Ingresa un correo o número de contacto válido.'
            )

        return contacto

    def clean_mensaje(self):
        mensaje = self.cleaned_data.get('mensaje', '').strip()

        if len(mensaje) < 5:
            raise forms.ValidationError(
                'El mensaje debe tener al menos 5 caracteres.'
            )

        return mensaje


# =========================================================
# FORMULARIO DE PRODUCTOS / AREPAS
# =========================================================

class ProductoForm(forms.ModelForm):

    class Meta:
        model = producto

        fields = [
            'nombre',
            'descripcion',
            'precio',
            'stock',
            'imagen_archivo',
            'descuento',
            'activo',
        ]

        labels = {
            'nombre': 'Nombre de la arepa',
            'descripcion': 'Descripción',
            'precio': 'Precio de venta',
            'stock': 'Unidades disponibles',
            'imagen_archivo': 'Fotografía de la arepa',
            'descuento': 'Descuento (%)',
            'activo': 'Producto disponible en el menú',
        }

        widgets = {
            'nombre': forms.TextInput(attrs={
                'class': 'product-input',
                'placeholder': 'Ej. Arepa de queso',
                'maxlength': 255,
            }),

            'descripcion': forms.Textarea(attrs={
                'class': 'product-input',
                'rows': 4,
                'placeholder': (
                    'Describe los ingredientes y características...'
                ),
            }),

            'precio': forms.NumberInput(attrs={
                'class': 'product-input',
                'min': '0',
                'step': '0.01',
                'placeholder': 'Ej. 8000',
            }),

            'stock': forms.NumberInput(attrs={
                'class': 'product-input',
                'min': '0',
                'step': '1',
                'placeholder': 'Cantidad disponible',
            }),

            'imagen_archivo': forms.ClearableFileInput(attrs={
                'class': 'product-file-input',
                'accept': '.jpg,.jpeg,.png,.webp',
            }),

            'descuento': forms.NumberInput(attrs={
                'class': 'product-input',
                'min': '0',
                'max': '100',
                'step': '1',
                'placeholder': '0',
            }),

            'activo': forms.CheckboxInput(attrs={
                'class': 'product-checkbox',
            }),
        }

    # -----------------------------------------------------
    # NOMBRE
    # -----------------------------------------------------

    def clean_nombre(self):
        nombre = self.cleaned_data.get('nombre', '').strip()

        if len(nombre) < 3:
            raise forms.ValidationError(
                'El nombre debe tener al menos 3 caracteres.'
            )

        return nombre

    # -----------------------------------------------------
    # PRECIO
    # -----------------------------------------------------

    def clean_precio(self):
        precio = self.cleaned_data.get('precio')

        if precio is None or precio < 0:
            raise forms.ValidationError(
                'El precio no puede ser negativo.'
            )

        return precio

    # -----------------------------------------------------
    # INVENTARIO
    # -----------------------------------------------------

    def clean_stock(self):
        stock = self.cleaned_data.get('stock')

        if stock is None or stock < 0:
            raise forms.ValidationError(
                'El inventario no puede ser negativo.'
            )

        return stock

    # -----------------------------------------------------
    # DESCUENTO
    # -----------------------------------------------------

    def clean_descuento(self):
        descuento = self.cleaned_data.get('descuento')

        if descuento is None or not 0 <= descuento <= 100:
            raise forms.ValidationError(
                'El descuento debe estar entre 0 y 100.'
            )

        return descuento

    # -----------------------------------------------------
    # IMAGEN
    # -----------------------------------------------------

    def clean_imagen_archivo(self):
        imagen = self.cleaned_data.get('imagen_archivo')

        if not imagen:
            return imagen

        # Tamaño máximo: 5 MB.
        if imagen.size > 5 * 1024 * 1024:
            raise forms.ValidationError(
                'La imagen no puede superar los 5 MB.'
            )

        extensiones = (
            '.jpg',
            '.jpeg',
            '.png',
            '.webp',
        )

        nombre = imagen.name.lower()

        if not nombre.endswith(extensiones):
            raise forms.ValidationError(
                'Selecciona una imagen JPG, JPEG, PNG o WEBP.'
            )

        # Validar que el archivo sea realmente una imagen.
        try:
            from PIL import Image

            imagen.seek(0)

            imagen_validar = Image.open(imagen)
            imagen_validar.verify()

            imagen.seek(0)

        except Exception:
            raise forms.ValidationError(
                'El archivo seleccionado no es una imagen válida.'
            )

        return imagen


# =========================================================
# FORMULARIO DE CLIENTES
# =========================================================

class ClienteForm(forms.ModelForm):

    class Meta:
        model = cliente

        fields = [
            'nombre',
            'telefono',
            'direccion',
        ]

        labels = {
            'nombre': 'Nombre completo',
            'telefono': 'Teléfono',
            'direccion': 'Dirección',
        }

        widgets = {
            'nombre': forms.TextInput(attrs={
                'class': 'formInput',
                'placeholder': 'Nombre completo',
                'autocomplete': 'name',
                'maxlength': 255,
            }),

            'telefono': forms.TextInput(attrs={
                'class': 'formInput',
                'placeholder': 'Teléfono de contacto',
                'autocomplete': 'tel',
                'maxlength': 50,
            }),

            'direccion': forms.TextInput(attrs={
                'class': 'formInput',
                'placeholder': 'Dirección de entrega',
                'autocomplete': 'street-address',
                'maxlength': 255,
            }),
        }

    def clean_nombre(self):
        nombre = self.cleaned_data.get('nombre', '').strip()

        if len(nombre) < 3:
            raise forms.ValidationError(
                'El nombre debe tener al menos 3 caracteres.'
            )

        return nombre

    def clean_telefono(self):
        telefono = self.cleaned_data.get('telefono', '').strip()

        if len(telefono) < 7:
            raise forms.ValidationError(
                'Ingresa un teléfono válido.'
            )

        return telefono

    def clean_direccion(self):
        direccion = self.cleaned_data.get('direccion', '').strip()

        if len(direccion) < 5:
            raise forms.ValidationError(
                'Ingresa una dirección válida.'
            )

        return direccion


# =========================================================
# FORMULARIO DE INICIO DE SESIÓN
# =========================================================

class CustomLoginForm(AuthenticationForm):

    username = forms.CharField(
        label='Usuario o correo electrónico',
        widget=forms.TextInput(attrs={
            'class': 'formInput',
            'placeholder': 'Correo o usuario',
            'autocomplete': 'username',
            'autofocus': True,
        })
    )

    password = forms.CharField(
        label='Contraseña',
        widget=forms.PasswordInput(attrs={
            'class': 'formInput',
            'placeholder': '••••••••',
            'autocomplete': 'current-password',
        })
    )
