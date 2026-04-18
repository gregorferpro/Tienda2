from .models import Venta


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