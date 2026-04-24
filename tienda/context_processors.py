from urllib.parse import urlencode

from django.urls import reverse

from .models import Producto, Venta


def notificacion_pago_cliente(request):
    if not request.user.is_authenticated:
        return {'notificacion_pago_cliente': None}

    venta = (
        Venta.objects
        .select_related('cliente')
        .filter(
            cliente__user=request.user,
            estado_pago__in=['pagado', 'rechazado'],
            notificacion_cliente_vista=False
        )
        .order_by('-fecha')
        .first()
    )

    return {'notificacion_pago_cliente': venta}


def storefront_categories(request):
    current_name = getattr(getattr(request, 'resolver_match', None), 'url_name', '')
    storefront_names = {
        'catalogo_cliente',
        'detalle_producto_cliente',
        'carrito',
        'checkout',
        'factura_view',
    }

    if current_name not in storefront_names:
        return {'storefront_categories': []}

    q = request.GET.get('q', '').strip()
    active_tipo = request.GET.get('tipo', '').strip().lower()
    active_categoria = request.GET.get('categoria', '').strip()
    base_url = reverse('catalogo_cliente')

    def build_url(*, tipo='', categoria=''):
        params = {}
        if q:
            params['q'] = q
        if tipo:
            params['tipo'] = tipo
        if categoria:
            params['categoria'] = categoria
        return f"{base_url}?{urlencode(params)}" if params else base_url

    tipo_labels = {
        'celular': 'Celulares',
        'accesorio': 'Accesorios',
        'otro': 'Otros',
    }

    categorias = [
        {
            'label': 'Todos',
            'url': build_url(),
            'is_active': not active_tipo and not active_categoria,
        }
    ]

    for value, default_label in Producto.TIPO_PRODUCTO_CHOICES:
        categorias.append({
            'label': tipo_labels.get(value, default_label),
            'url': build_url(tipo=value),
            'is_active': active_tipo == value and not active_categoria,
        })

    categorias_db = (
        Producto.objects
        .filter(activo=True)
        .exclude(categoria='')
        .values_list('categoria', flat=True)
        .distinct()
    )

    for categoria in categorias_db:
        categoria = (categoria or '').strip()
        if not categoria:
            continue
        categorias.append({
            'label': categoria.title(),
            'url': build_url(categoria=categoria),
            'is_active': active_categoria.lower() == categoria.lower(),
        })

    return {'storefront_categories': categorias}
