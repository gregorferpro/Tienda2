from django.contrib import admin
from .models import (
    Producto, ProductoImagen, Cliente, Venta, DetalleVenta,
    Proveedor, CompraProveedor, DetalleCompraProveedor,
    ReclamoProveedor, DevolucionProveedor, MovimientoInventario
)

admin.site.register(Producto)
admin.site.register(ProductoImagen)
admin.site.register(Cliente)
admin.site.register(Venta)
admin.site.register(DetalleVenta)

admin.site.register(Proveedor)
admin.site.register(CompraProveedor)
admin.site.register(DetalleCompraProveedor)
admin.site.register(ReclamoProveedor)
admin.site.register(DevolucionProveedor)
admin.site.register(MovimientoInventario)