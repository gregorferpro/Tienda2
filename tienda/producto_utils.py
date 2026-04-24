from .models import Producto


def _clean_text(value):
    return (value or '').strip()


def product_payload_from_purchase_detail(detalle):
    return {
        'codigo': _clean_text(detalle.producto_codigo),
        'nombre': _clean_text(detalle.producto_nombre),
        'marca': _clean_text(detalle.producto_marca),
        'modelo': _clean_text(detalle.producto_modelo),
        'tipo_producto': _clean_text(detalle.tipo_producto) or 'otro',
        'categoria': _clean_text(detalle.categoria),
        'descripcion': _clean_text(detalle.descripcion_base),
        'precio': detalle.precio_venta_sugerido or detalle.costo_unitario,
        'costo_referencia': detalle.costo_unitario,
        'stock': 0,
        'activo': True,
    }


def find_matching_product_from_purchase_detail(detalle):
    if getattr(detalle, 'producto_id', None):
        return detalle.producto

    payload = product_payload_from_purchase_detail(detalle)
    codigo = payload['codigo']

    if codigo:
        producto = Producto.objects.filter(codigo__iexact=codigo).first()
        if producto:
            return producto

    nombre = payload['nombre']
    marca = payload['marca']
    modelo = payload['modelo']
    tipo_producto = payload['tipo_producto']
    categoria = payload['categoria']

    if not (nombre and marca and modelo):
        return None

    productos = Producto.objects.filter(
        nombre__iexact=nombre,
        marca__iexact=marca,
        modelo__iexact=modelo,
    )

    if tipo_producto:
        productos = productos.filter(tipo_producto=tipo_producto)

    if categoria:
        producto = productos.filter(categoria__iexact=categoria).order_by('-id').first()
        if producto:
            return producto

    return productos.order_by('-id').first()


def build_product_from_purchase_detail(detalle, codigo_fallback_factory):
    producto = find_matching_product_from_purchase_detail(detalle)
    if producto:
        return producto

    payload = product_payload_from_purchase_detail(detalle)
    if not payload['codigo']:
        payload['codigo'] = codigo_fallback_factory()
    return Producto(**payload)


def get_or_create_product_from_purchase_detail(detalle, codigo_fallback_factory):
    producto = find_matching_product_from_purchase_detail(detalle)
    if producto:
        return producto

    payload = product_payload_from_purchase_detail(detalle)
    if not payload['codigo']:
        payload['codigo'] = codigo_fallback_factory()
    return Producto.objects.create(**payload)
