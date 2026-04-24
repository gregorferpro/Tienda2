from decimal import Decimal
from django.db import models
from django.contrib.auth.models import User


class Producto(models.Model):
    TIPO_PRODUCTO_CHOICES = [
        ('celular', 'Celular'),
        ('accesorio', 'Accesorio'),
        ('otro', 'Otro'),
    ]

    codigo = models.CharField(max_length=50, unique=True)
    nombre = models.CharField(max_length=150)
    marca = models.CharField(max_length=100)
    modelo = models.CharField(max_length=100)
    tipo_producto = models.CharField(max_length=20, choices=TIPO_PRODUCTO_CHOICES, default='otro')
    categoria = models.CharField(max_length=100, blank=True, default='')
    descripcion = models.TextField(blank=True)
    precio = models.DecimalField(max_digits=10, decimal_places=2)
    costo_referencia = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    stock = models.PositiveIntegerField(default=0)
    activo = models.BooleanField(default=True)

    def _catalog_images(self):
        imagenes = list(self.imagenes_extra.all())
        if not imagenes:
            return None, None

        base = None
        flotante = None

        for imagen in imagenes:
            nombre = (imagen.imagen.name or '').lower()
            if flotante is None and nombre.endswith('.png'):
                flotante = imagen
            if base is None and not nombre.endswith('.png'):
                base = imagen

        if base is None:
            base = imagenes[0]

        return base, flotante

    @property
    def catalog_base_image(self):
        base, _ = self._catalog_images()
        return base

    @property
    def catalog_float_image(self):
        _, flotante = self._catalog_images()
        return flotante

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


# =========================
# MODULO DE PROVEEDORES
# =========================

TIPO_PROVEEDOR_CHOICES = [
    ('PERSONA', 'Persona'),
    ('EMPRESA', 'Empresa'),
]

ESTADO_PROVEEDOR_CHOICES = [
    ('activo', 'Activo'),
    ('inactivo', 'Inactivo'),
]

TIPO_DOCUMENTO_COMPRA_CHOICES = [
    ('FACTURA', 'Factura'),
    ('NOTA_VENTA', 'Nota de venta'),
    ('RECIBO', 'Recibo'),
    ('REFERENCIA', 'Referencia libre'),
]

ESTADO_COMPRA_CHOICES = [
    ('borrador', 'Borrador'),
    ('confirmada', 'Confirmada'),
    ('anulada', 'Anulada'),
]

ESTADO_RECLAMO_CHOICES = [
    ('pendiente', 'Pendiente'),
    ('en_revision', 'En revisión'),
    ('aprobado', 'Aprobado'),
    ('rechazado', 'Rechazado'),
    ('devuelto', 'Devuelto'),
    ('cerrado', 'Cerrado'),
]

ESTADO_DEVOLUCION_CHOICES = [
    ('registrada', 'Registrada'),
    ('enviada', 'Enviada'),
    ('cerrada', 'Cerrada'),
]

TIPO_MOVIMIENTO_CHOICES = [
    ('entrada', 'Entrada'),
    ('salida', 'Salida'),
]


class Proveedor(models.Model):
    tipo_proveedor = models.CharField(max_length=20, choices=TIPO_PROVEEDOR_CHOICES, default='EMPRESA')
    nombre = models.CharField(max_length=150)
    razon_social = models.CharField(max_length=180, blank=True, default='')
    nombre_comercial = models.CharField(max_length=180, blank=True, default='')
    documento_ref = models.CharField(max_length=50, blank=True, default='')
    nit = models.CharField(max_length=30, blank=True, default='')
    telefono = models.CharField(max_length=30, blank=True, default='')
    email = models.EmailField(blank=True)
    direccion = models.TextField(blank=True)
    contacto = models.CharField(max_length=150, blank=True, default='')
    observaciones = models.TextField(blank=True)
    estado = models.CharField(max_length=20, choices=ESTADO_PROVEEDOR_CHOICES, default='activo')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['nombre']

    def __str__(self):
        return self.nombre


class CompraProveedor(models.Model):
    proveedor = models.ForeignKey(Proveedor, on_delete=models.PROTECT, related_name='compras')
    usuario = models.ForeignKey(User, on_delete=models.PROTECT, related_name='compras_proveedor')
    fecha_compra = models.DateField()
    tipo_documento = models.CharField(
        max_length=20,
        choices=TIPO_DOCUMENTO_COMPRA_CHOICES,
        default='REFERENCIA'
    )
    numero_documento = models.CharField(max_length=80, blank=True, default='')
    referencia_libre = models.CharField(max_length=150, blank=True, default='')
    observaciones = models.TextField(blank=True)
    subtotal = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    descuento = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    estado = models.CharField(max_length=20, choices=ESTADO_COMPRA_CHOICES, default='borrador')
    stock_aplicado = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'Compra #{self.id} - {self.proveedor.nombre}'


class DetalleCompraProveedor(models.Model):
    compra = models.ForeignKey(CompraProveedor, on_delete=models.CASCADE, related_name='detalles')

    # Si el producto ya existe, se usa este FK
    producto = models.ForeignKey(
        Producto,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='detalles_compra'
    )

    # Si el producto no existe todavía, se guardan los datos base
    producto_codigo = models.CharField(max_length=50, blank=True, default='')
    producto_nombre = models.CharField(max_length=150, blank=True, default='')
    producto_marca = models.CharField(max_length=100, blank=True, default='')
    producto_modelo = models.CharField(max_length=100, blank=True, default='')
    tipo_producto = models.CharField(max_length=20, choices=Producto.TIPO_PRODUCTO_CHOICES, default='otro')
    categoria = models.CharField(max_length=100, blank=True, default='')
    descripcion_base = models.TextField(blank=True)
    precio_venta_sugerido = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    cantidad = models.PositiveIntegerField(default=1)
    costo_unitario = models.DecimalField(max_digits=10, decimal_places=2)
    subtotal = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    def save(self, *args, **kwargs):
        self.subtotal = Decimal(self.cantidad) * self.costo_unitario
        super().save(*args, **kwargs)

    @property
    def nombre_mostrado(self):
        return self.producto.nombre if self.producto else self.producto_nombre

    def __str__(self):
        return f'{self.nombre_mostrado} x {self.cantidad}'


class ReclamoProveedor(models.Model):
    proveedor = models.ForeignKey(Proveedor, on_delete=models.PROTECT, related_name='reclamos')
    compra = models.ForeignKey(CompraProveedor, on_delete=models.PROTECT, related_name='reclamos')
    producto = models.ForeignKey(Producto, on_delete=models.PROTECT, related_name='reclamos_proveedor')
    cantidad = models.PositiveIntegerField(default=1)
    motivo = models.CharField(max_length=200)
    observaciones = models.TextField(blank=True)
    estado = models.CharField(max_length=20, choices=ESTADO_RECLAMO_CHOICES, default='pendiente')
    fecha_reclamo = models.DateField()
    usuario = models.ForeignKey(User, on_delete=models.PROTECT, related_name='reclamos_proveedor')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'Reclamo #{self.id} - {self.producto.nombre}'


class DevolucionProveedor(models.Model):
    reclamo = models.OneToOneField(ReclamoProveedor, on_delete=models.PROTECT, related_name='devolucion')
    proveedor = models.ForeignKey(Proveedor, on_delete=models.PROTECT, related_name='devoluciones')
    compra = models.ForeignKey(CompraProveedor, on_delete=models.PROTECT, related_name='devoluciones')
    producto = models.ForeignKey(Producto, on_delete=models.PROTECT, related_name='devoluciones_proveedor')
    cantidad = models.PositiveIntegerField(default=1)
    motivo = models.CharField(max_length=200)
    estado = models.CharField(max_length=20, choices=ESTADO_DEVOLUCION_CHOICES, default='registrada')
    fecha_devolucion = models.DateField()
    usuario = models.ForeignKey(User, on_delete=models.PROTECT, related_name='devoluciones_proveedor')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'Devolución #{self.id} - {self.producto.nombre}'


class MovimientoInventario(models.Model):
    producto = models.ForeignKey(Producto, on_delete=models.PROTECT, related_name='movimientos_inventario')
    compra = models.ForeignKey(CompraProveedor, on_delete=models.SET_NULL, null=True, blank=True, related_name='movimientos')
    devolucion = models.ForeignKey(DevolucionProveedor, on_delete=models.SET_NULL, null=True, blank=True, related_name='movimientos')
    cantidad = models.PositiveIntegerField(default=1)
    tipo_movimiento = models.CharField(max_length=20, choices=TIPO_MOVIMIENTO_CHOICES)
    motivo = models.CharField(max_length=200)
    stock_anterior = models.PositiveIntegerField(default=0)
    stock_nuevo = models.PositiveIntegerField(default=0)
    usuario = models.ForeignKey(User, on_delete=models.PROTECT, related_name='movimientos_inventario')
    fecha = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'{self.tipo_movimiento} - {self.producto.nombre} - {self.cantidad}'
