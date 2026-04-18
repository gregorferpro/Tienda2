from decimal import Decimal
from django.db import models
from django.contrib.auth.models import User


class Producto(models.Model):
    codigo = models.CharField(max_length=50, unique=True)
    nombre = models.CharField(max_length=150)
    marca = models.CharField(max_length=100)
    modelo = models.CharField(max_length=100)
    descripcion = models.TextField(blank=True)
    precio = models.DecimalField(max_digits=10, decimal_places=2)
    stock = models.PositiveIntegerField(default=0)
    activo = models.BooleanField(default=True)

    def __str__(self):
        return self.nombre


class ProductoImagen(models.Model):
    producto = models.ForeignKey(
        Producto,
        on_delete=models.CASCADE,
        related_name='imagenes_extra'
    )
    imagen = models.ImageField(upload_to='productos/extra/')

    def __str__(self):
        return f"Imagen de {self.producto.nombre}"


class Cliente(models.Model):
    user = models.OneToOneField(User, on_delete=models.SET_NULL, null=True, blank=True)
    nombres = models.CharField(max_length=100)
    apellidos = models.CharField(max_length=100)
    ci_nit = models.CharField(max_length=30)
    telefono = models.CharField(max_length=30)
    email = models.EmailField(blank=True)
    direccion = models.TextField(blank=True)
    estado = models.CharField(max_length=20, default='activo')

    @property
    def nombre_completo(self):
        return f'{self.nombres} {self.apellidos}'

    def __str__(self):
        return self.nombre_completo


ESTADO_PAGO_CHOICES = [
    ('pendiente', 'Pendiente'),
    ('pagado', 'Pagado'),
    ('rechazado', 'Rechazado'),
]

METODO_PAGO_CHOICES = [
    ('EFECTIVO', 'Efectivo'),
    ('QR', 'QR'),
    ('TRANSFERENCIA', 'Transferencia'),
]


class Venta(models.Model):
    cliente = models.ForeignKey(Cliente, on_delete=models.PROTECT, related_name='ventas')
    usuario = models.ForeignKey(User, on_delete=models.PROTECT, related_name='ventas_realizadas')
    numero_factura = models.CharField(max_length=30, unique=True)
    metodo_pago = models.CharField(max_length=20, choices=METODO_PAGO_CHOICES)
    subtotal = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    descuento = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    estado_pago = models.CharField(
        max_length=20,
        choices=ESTADO_PAGO_CHOICES,
        default='pendiente'
    )
    notificacion_cliente_vista = models.BooleanField(default=False)
    fecha = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'Factura {self.numero_factura}'


class DetalleVenta(models.Model):
    venta = models.ForeignKey(Venta, on_delete=models.CASCADE, related_name='detalles')
    producto = models.ForeignKey(Producto, on_delete=models.PROTECT)
    cantidad = models.PositiveIntegerField(default=1)
    precio_unitario = models.DecimalField(max_digits=10, decimal_places=2)
    subtotal = models.DecimalField(max_digits=10, decimal_places=2)

    def save(self, *args, **kwargs):
        self.subtotal = Decimal(self.cantidad) * self.precio_unitario
        super().save(*args, **kwargs)