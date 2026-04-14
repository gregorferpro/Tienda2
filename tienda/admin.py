from django.contrib import admin
from .models import Producto, ProductoImagen, Cliente, Venta, DetalleVenta

admin.site.register(Producto)
admin.site.register(ProductoImagen)
admin.site.register(Cliente)
admin.site.register(Venta)
admin.site.register(DetalleVenta)