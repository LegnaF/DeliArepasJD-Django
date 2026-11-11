from django.db import models

# ==========================================
# ENUMS
# ==========================================

class PedidoEstado(models.TextChoices):
    PENDIENTE = 'PENDIENTE', 'PENDIENTE'
    EN_PREPARACION = 'EN_PREPARACION', 'EN_PREPARACION'
    ENTREGADO = 'ENTREGADO', 'ENTREGADO'
    CANCELADO = 'CANCELADO', 'CANCELADO'

class UsuarioRol(models.TextChoices):
    ADMIN = 'ADMIN', 'ADMIN'
    EMPLEADO = 'EMPLEADO', 'EMPLEADO'
    USUARIO = 'USUARIO', 'USUARIO'


# ==========================================
# MODELOS
# ==========================================

class cliente(models.Model):
    nombre = models.CharField(max_length=255)
    telefono = models.CharField(max_length=50)
    direccion = models.CharField(max_length=255)
    createdAt = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'cliente'
        verbose_name = 'Cliente'
        verbose_name_plural = 'Clientes'

    def __str__(self):
        return self.nombre


class producto(models.Model):
    nombre = models.CharField(max_length=255)
    descripcion = models.TextField(default="", blank=True)
    precio = models.FloatField()
    stock = models.IntegerField(default=0)
    categoria = models.CharField(max_length=100, default="Arepas")
    imagen = models.CharField(max_length=255, default="/arepa3.jpg")
    descuento = models.IntegerField(default=0)
    activo = models.BooleanField(default=True)
    createdAt = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'producto'
        verbose_name = 'Producto'
        verbose_name_plural = 'Productos'

    def __str__(self):
        return self.nombre


class pedido(models.Model):
    cliente = models.ForeignKey(
        cliente, 
        on_delete=models.CASCADE, 
        db_column='clienteId', 
        related_name='pedido'
    )
    estado = models.CharField(
        max_length=20, 
        choices=PedidoEstado.choices, 
        default=PedidoEstado.PENDIENTE
    )
    total = models.FloatField()
    createdAt = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'pedido'
        verbose_name = 'Pedido'
        verbose_name_plural = 'Pedidos'

    def __str__(self):
        return f"Pedido #{self.id} - {self.cliente.nombre}"


class detallepedido(models.Model):
    pedido = models.ForeignKey(
        pedido, 
        on_delete=models.CASCADE, 
        db_column='pedidoId', 
        related_name='detallepedido'
    )
    producto = models.ForeignKey(
        producto, 
        on_delete=models.CASCADE, 
        db_column='productoId', 
        related_name='detalles'
    )
    cantidad = models.IntegerField()
    precioUnit = models.FloatField()

    class Meta:
        db_table = 'detallepedido'
        verbose_name = 'Detalle de Pedido'
        verbose_name_plural = 'Detalles de Pedidos'


class usuario(models.Model):
    nombre = models.CharField(max_length=255)
    email = models.CharField(max_length=255, unique=True)
    password = models.CharField(max_length=255)
    rol = models.CharField(
        max_length=20, 
        choices=UsuarioRol.choices, 
        default=UsuarioRol.USUARIO
    )
    intentosFallidos = models.IntegerField(default=0)
    bloqueadoHasta = models.DateTimeField(null=True, blank=True)
    resetCode = models.CharField(max_length=255, null=True, blank=True)
    resetCodeExpires = models.DateTimeField(null=True, blank=True)
    createdAt = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'usuario'
        verbose_name = 'Usuario'
        verbose_name_plural = 'Usuarios'

    def __str__(self):
        return self.email


class pqr(models.Model):
    nombre = models.CharField(max_length=150)
    contacto = models.CharField(max_length=150)
    mensaje = models.TextField()
    createdAt = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'pqr'
        verbose_name = 'PQR'
        verbose_name_plural = 'PQRs'

    def __str__(self):
        return f"PQR de {self.nombre}"