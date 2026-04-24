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

    def normalize_category_key(value):
        value = ' '.join((value or '').strip().lower().split())
        aliases = {
            'celular': 'celulares',
            'celulares': 'celulares',
            'accesorio': 'accesorios',
            'accesorios': 'accesorios',
            'otro': 'otros',
            'otros': 'otros',
        }
        return aliases.get(value, value)

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

    tipo_entries = []
    tipo_seen_keys = set()

    for index, (value, default_label) in enumerate(Producto.TIPO_PRODUCTO_CHOICES):
        label = tipo_labels.get(value, default_label)
        normalized_key = normalize_category_key(label)
        tipo_seen_keys.add(normalized_key)
        tipo_entries.append({
            'value': value,
            'label': label,
            'index': index,
            'sort_order': 99 if value == 'otro' else 0,
            'is_active': (
                active_tipo == value or
                (not active_tipo and normalize_category_key(active_categoria) == normalized_key)
            ) and not (active_tipo and active_categoria),
        })

    otros_entry = None

    for entry in sorted(tipo_entries, key=lambda item: (item['sort_order'], item['index'])):
        item = {
            'label': entry['label'],
            'url': build_url(tipo=entry['value']),
            'is_active': entry['is_active'],
        }
        if entry['value'] == 'otro':
            otros_entry = item
            continue
        categorias.append(item)

    categorias_db = (
        Producto.objects
        .filter(activo=True)
        .exclude(categoria='')
        .values_list('categoria', flat=True)
        .distinct()
    )

    categorias_agregadas = set()

    for categoria in categorias_db:
        categoria = (categoria or '').strip()
        if not categoria:
            continue
        normalized_key = normalize_category_key(categoria)
        if normalized_key in tipo_seen_keys or normalized_key in categorias_agregadas:
            continue
        categorias_agregadas.add(normalized_key)
        categorias.append({
            'label': categoria.title(),
            'url': build_url(categoria=categoria),
            'is_active': active_categoria.lower() == categoria.lower(),
        })

    if otros_entry:
        categorias.append(otros_entry)

    return {'storefront_categories': categorias}
