from django.urls import path
from . import views
from . import proveedores_views

urlpatterns = [
    path('catalogo/', views.catalogo_cliente, name='catalogo_cliente'),
    path('producto/<int:pk>/', views.detalle_producto_cliente, name='detalle_producto_cliente'),

    path('carrito/', views.carrito, name='carrito'),
    path('carrito/agregar/<int:pk>/', views.agregar_carrito, name='agregar_carrito'),
    path('carrito/quitar/<int:pk>/', views.quitar_carrito, name='quitar_carrito'),
    path('carrito/vaciar/', views.vaciar_carrito, name='vaciar_carrito'),

    path('checkout/', views.checkout, name='checkout'),
    path('factura/<int:pk>/', views.factura_view, name='factura_view'),

    path('productos/', views.productos_list, name='productos_list'),
    path('productos/nuevo/', views.producto_create, name='producto_create'),
    path('productos/<int:pk>/', views.producto_detail, name='producto_detail'),
    path('productos/<int:pk>/editar/', views.producto_update, name='producto_update'),
    path('productos/<int:pk>/eliminar/', views.producto_delete, name='producto_delete'),

    path('clientes/', views.clientes_list, name='clientes_list'),
    path('clientes/nuevo/', views.cliente_create, name='cliente_create'),
    path('clientes/<int:pk>/editar/', views.cliente_update, name='cliente_update'),
    path('clientes/<int:pk>/eliminar/', views.cliente_delete, name='cliente_delete'),

    path('ventas/', views.ventas_list, name='ventas_list'),
    path('ventas/<int:pk>/', views.venta_detail, name='venta_detail'),

    path('pagos-pendientes/', views.pagos_pendientes, name='pagos_pendientes'),
    path('pagos-pendientes/<int:pk>/confirmar/', views.confirmar_pago, name='confirmar_pago'),
    path('pagos-pendientes/<int:pk>/rechazar/', views.rechazar_pago, name='rechazar_pago'),

    path('notificaciones/pago/consultar/', views.consultar_notificacion_pago, name='consultar_notificacion_pago'),
    path('notificaciones/pago/<int:pk>/vista/', views.marcar_notificacion_pago_vista, name='marcar_notificacion_pago_vista'),

    # PROVEEDORES
    path('proveedores/', proveedores_views.proveedores_list, name='proveedores_list'),
    path('proveedores/nuevo/', proveedores_views.proveedor_create, name='proveedor_create'),
    path('proveedores/<int:pk>/editar/', proveedores_views.proveedor_update, name='proveedor_update'),
    path('proveedores/<int:pk>/toggle-estado/', proveedores_views.proveedor_toggle_estado, name='proveedor_toggle_estado'),

    # COMPRAS PROVEEDOR
    path('compras-proveedor/', proveedores_views.compras_proveedor_list, name='compras_proveedor_list'),
    path('compras-proveedor/nueva/', proveedores_views.compra_proveedor_create, name='compra_proveedor_create'),
    path('compras-proveedor/<int:pk>/', proveedores_views.compra_proveedor_detail, name='compra_proveedor_detail'),
    path('compras-proveedor/<int:pk>/confirmar/', proveedores_views.compra_proveedor_confirmar, name='compra_proveedor_confirmar'),

    # RECLAMOS / DEVOLUCIONES
    path('reclamos-proveedor/', proveedores_views.reclamos_proveedor_list, name='reclamos_proveedor_list'),
    path('reclamos-proveedor/nuevo/', proveedores_views.reclamo_proveedor_create, name='reclamo_proveedor_create'),
    path('reclamos-proveedor/<int:pk>/', proveedores_views.reclamo_proveedor_detail, name='reclamo_proveedor_detail'),
    path('reclamos-proveedor/<int:reclamo_pk>/devolucion/', proveedores_views.devolucion_proveedor_create, name='devolucion_proveedor_create'),
]