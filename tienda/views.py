from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db import transaction
from django.db.models import Q
from django.db.models.deletion import ProtectedError
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

from .forms import (
    CheckoutForm, ClienteForm, ProductoCatalogoForm, ProductoForm,
    ProveedorForm, CompraProveedorForm
)
from .models import (
    Cliente, DetalleVenta, Producto, ProductoImagen, Venta,
    Proveedor, CompraProveedor, DetalleCompraProveedor,
    ReclamoProveedor, DevolucionProveedor, MovimientoInventario,
)
from .producto_utils import build_product_from_purchase_detail


def generar_numero_factura():
    return timezone.now().strftime('%Y%m%d%H%M%S')


def generar_numero_compra():
    return f"CP-{timezone.now().strftime('%Y%m%d%H%M%S')}"


def generar_codigo_producto():
    return f'PRD-{timezone.now().strftime("%Y%m%d%H%M%S%f")}'


def obtener_detalles_compra_para_catalogo():
    return (
        DetalleCompraProveedor.objects
        .select_related('compra', 'producto')
        .order_by('-id')
    )


def construir_producto_desde_detalle(detalle):
    return build_product_from_purchase_detail(detalle, generar_codigo_producto)


def detalle_compra_tiene_movimiento(detalle, producto):
    if not producto or not detalle.compra_id:
        return False

    return MovimientoInventario.objects.filter(
        compra=detalle.compra,
        producto=producto,
        tipo_movimiento='entrada',
    ).exists()


def compra_stock_completo(compra):
    detalles = compra.detalles.select_related('producto').all()
    if not detalles:
        return False

    for detalle in detalles:
        if not detalle.producto_id:
            return False
        if not detalle_compra_tiene_movimiento(detalle, detalle.producto):
            return False

    return True


def sincronizar_stock_desde_detalle_si_corresponde(detalle, producto, usuario):
    compra = detalle.compra
    if compra.estado != 'confirmada':
        return

    if detalle_compra_tiene_movimiento(detalle, producto):
        if not compra.stock_aplicado and compra_stock_completo(compra):
            compra.stock_aplicado = True
            compra.save(update_fields=['stock_aplicado'])
        return

    stock_anterior = producto.stock
    producto.stock += detalle.cantidad
    producto.save(update_fields=['stock'])

    MovimientoInventario.objects.create(
        producto=producto,
        compra=compra,
        cantidad=detalle.cantidad,
        tipo_movimiento='entrada',
        motivo=f'Entrada sincronizada desde producto por compra proveedor #{compra.id}',
        stock_anterior=stock_anterior,
        stock_nuevo=producto.stock,
        usuario=usuario,
    )

    if compra_stock_completo(compra):
        compra.stock_aplicado = True
        compra.save(update_fields=['stock_aplicado'])


def numero_a_texto_basico(numero):
    try:
        return f'{Decimal(numero):.2f} bolivianos'
    except Exception:
        return f'{numero} bolivianos'


def es_staff_o_superuser(user):
    return user.is_authenticated and (
        user.is_staff or user.is_superuser or (hasattr(user, 'perfil') and getattr(user.perfil, 'rol', None) == 'superuser')
    )


def solo_superuser(user):
    return user.is_authenticated and user.is_superuser


def obtener_carrito(request):
    carrito = request.session.get('carrito')
    if carrito is None:
        carrito = {}
        request.session['carrito'] = carrito
    return carrito


def guardar_carrito(request, carrito):
    request.session['carrito'] = carrito
    request.session.modified = True


def aplicar_stock_compra(compra):
    if compra.stock_aplicado:
        return

    for detalle in compra.detalles.select_related('producto').all():
        producto = detalle.producto
        producto.stock += detalle.cantidad
        producto.save()

    compra.stock_aplicado = True
    compra.save(update_fields=['stock_aplicado'])


def catalogo_cliente(request):
    q = request.GET.get('q', '').strip()
    tipo = request.GET.get('tipo', '').strip().lower()
    categoria = request.GET.get('categoria', '').strip()

    productos = (
        Producto.objects
        .filter(activo=True)
        .prefetch_related('imagenes_extra')
        .order_by('-id')
    )

    tipos_validos = {value for value, _ in Producto.TIPO_PRODUCTO_CHOICES}
    if tipo in tipos_validos:
        productos = productos.filter(tipo_producto=tipo)

    if categoria:
        productos = productos.filter(categoria__iexact=categoria)

    if q:
        productos = productos.filter(
            Q(nombre__icontains=q) |
            Q(codigo__icontains=q) |
            Q(marca__icontains=q) |
            Q(modelo__icontains=q)
        )

    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return render(request, 'tienda/partials/catalogo_grid.html', {
            'productos': productos
        })

    return render(request, 'tienda/catalogo_cliente.html', {
        'productos': productos,
        'q': q,
        'tipo': tipo,
        'categoria': categoria,
    })


def detalle_producto_cliente(request, pk):
    producto = get_object_or_404(
        Producto.objects.prefetch_related('imagenes_extra'),
        pk=pk,
        activo=True
    )
    return render(request, 'tienda/detalle_producto_cliente.html', {
        'producto': producto
    })


@login_required
def agregar_carrito(request, pk):
    producto = get_object_or_404(
        Producto.objects.prefetch_related('imagenes_extra'),
        pk=pk,
        activo=True
    )

    carrito = obtener_carrito(request)
    key = str(pk)

    imagen_url = ''
    primera = producto.imagenes_extra.first()
    if primera and primera.imagen:
        imagen_url = primera.imagen.url

    item = carrito.get(key, {
        'cantidad': 0,
        'codigo': producto.codigo,
        'nombre': producto.nombre,
        'precio': str(producto.precio),
        'imagen_url': imagen_url,
    })

    if item['cantidad'] < producto.stock:
        item['cantidad'] += 1
        item['codigo'] = producto.codigo
        item['nombre'] = producto.nombre
        item['precio'] = str(producto.precio)
        item['imagen_url'] = imagen_url
        carrito[key] = item
        guardar_carrito(request, carrito)
        messages.success(request, 'Producto agregado al carrito.')
    else:
        messages.warning(request, 'No hay suficiente stock disponible para este producto.')

    next_url = request.GET.get('next')
    if next_url:
        return redirect(next_url)

    return redirect('carrito')


@login_required
def quitar_carrito(request, pk):
    carrito = obtener_carrito(request)

    if str(pk) in carrito:
        del carrito[str(pk)]
        guardar_carrito(request, carrito)
        messages.success(request, 'Producto quitado del carrito.')

    return redirect('carrito')


@login_required
def vaciar_carrito(request):
    request.session['carrito'] = {}
    request.session.modified = True
    messages.success(request, 'Carrito vaciado correctamente.')
    return redirect('carrito')


@login_required
def carrito(request):
    carrito_data = obtener_carrito(request)
    items = []
    total = Decimal('0.00')

    for pk, data in carrito_data.items():
        producto = get_object_or_404(
            Producto.objects.prefetch_related('imagenes_extra'),
            pk=int(pk),
            activo=True
        )

        cantidad = int(data.get('cantidad', 0))
        if cantidad <= 0:
            continue

        subtotal = producto.precio * cantidad
        total += subtotal

        items.append({
            'producto': producto,
            'cantidad': cantidad,
            'subtotal': subtotal,
            'imagen_url': data.get('imagen_url', ''),
        })

    return render(request, 'tienda/carrito.html', {
        'items': items,
        'total': total,
    })


@login_required
@transaction.atomic
def checkout(request):
    carrito_data = obtener_carrito(request)

    if not carrito_data:
        messages.warning(request, 'Tu carrito está vacío.')
        return redirect('catalogo_cliente')

    items = []
    total = Decimal('0.00')

    for pk, data in carrito_data.items():
        producto = get_object_or_404(
            Producto.objects.prefetch_related('imagenes_extra'),
            pk=int(pk),
            activo=True
        )

        cantidad = int(data.get('cantidad', 0))
        if cantidad <= 0:
            continue

        subtotal = producto.precio * cantidad
        total += subtotal

        items.append({
            'producto': producto,
            'cantidad': cantidad,
            'subtotal': subtotal,
        })

    if not items:
        messages.warning(request, 'Tu carrito está vacío.')
        return redirect('catalogo_cliente')

    if request.method == 'POST':
        form = CheckoutForm(request.POST)

        if form.is_valid():
            metodo_pago_original = form.cleaned_data['metodo_pago']
            metodo_pago = str(metodo_pago_original).strip().lower()
            qr_confirmado = request.POST.get('qr_confirmado')

            if metodo_pago == 'qr' and not qr_confirmado:
                messages.error(request, 'Debes confirmar el pago por QR antes de finalizar la compra.')
                return render(request, 'tienda/checkout.html', {
                    'form': form,
                    'items': items,
                    'total': total,
                })

            for item in items:
                producto = item['producto']
                cantidad = item['cantidad']

                if producto.stock < cantidad:
                    messages.error(request, f'Stock insuficiente para {producto.nombre}.')
                    return redirect('carrito')

            cliente, _ = Cliente.objects.get_or_create(
                user=request.user,
                defaults={
                    'nombres': form.cleaned_data['nombres'],
                    'apellidos': form.cleaned_data['apellidos'],
                    'ci_nit': form.cleaned_data['ci_nit'],
                    'telefono': form.cleaned_data['telefono'],
                    'email': form.cleaned_data.get('email', ''),
                    'direccion': form.cleaned_data.get('direccion', ''),
                    'estado': 'activo',
                }
            )

            cliente.nombres = form.cleaned_data['nombres']
            cliente.apellidos = form.cleaned_data['apellidos']
            cliente.ci_nit = form.cleaned_data['ci_nit']
            cliente.telefono = form.cleaned_data['telefono']
            cliente.email = form.cleaned_data.get('email', '')
            cliente.direccion = form.cleaned_data.get('direccion', '')
            cliente.estado = 'activo'
            cliente.save()

            if metodo_pago == 'qr':
                if request.user.is_staff or request.user.is_superuser:
                    estado_inicial = 'pagado'
                else:
                    estado_inicial = 'pendiente'
            else:
                estado_inicial = 'pagado'

            venta = Venta.objects.create(
                cliente=cliente,
                usuario=request.user,
                numero_factura=generar_numero_factura(),
                metodo_pago=metodo_pago_original,
                subtotal=total,
                descuento=Decimal('0.00'),
                total=total,
                estado_pago=estado_inicial,
            )

            for item in items:
                producto = item['producto']
                cantidad = item['cantidad']

                DetalleVenta.objects.create(
                    venta=venta,
                    producto=producto,
                    cantidad=cantidad,
                    precio_unitario=producto.precio,
                    subtotal=item['subtotal']
                )

                producto.stock -= cantidad
                producto.save()

            request.session['carrito'] = {}
            request.session.modified = True

            if metodo_pago == 'qr' and not (request.user.is_staff or request.user.is_superuser):
                messages.success(
                    request,
                    'Tu compra fue registrada y el pago quedó pendiente de confirmación por el administrador.'
                )
                return redirect('catalogo_cliente')

            messages.success(request, 'Compra registrada correctamente.')
            return redirect('factura_view', pk=venta.pk)
    else:
        datos_iniciales = {}

        try:
            cliente = Cliente.objects.get(user=request.user)
            datos_iniciales = {
                'nombres': cliente.nombres,
                'apellidos': cliente.apellidos,
                'ci_nit': cliente.ci_nit,
                'telefono': cliente.telefono,
                'email': cliente.email,
                'direccion': cliente.direccion,
            }
        except Cliente.DoesNotExist:
            if request.user.email:
                datos_iniciales['email'] = request.user.email

        form = CheckoutForm(initial=datos_iniciales)

    return render(request, 'tienda/checkout.html', {
        'form': form,
        'items': items,
        'total': total,
    })


@login_required
def factura_view(request, pk):
    venta = get_object_or_404(
        Venta.objects.select_related('cliente', 'usuario').prefetch_related('detalles__producto'),
        pk=pk
    )

    if venta.estado_pago != 'pagado':
        messages.warning(
            request,
            'La factura aún no está disponible porque el pago sigue pendiente de confirmación.'
        )
        return redirect('catalogo_cliente')

    perfil = getattr(request.user, 'perfil', None)
    es_equipo_interno = request.user.is_staff and getattr(perfil, 'rol', '') != 'cliente'

    return render(request, 'tienda/factura.html', {
        'venta': venta,
        'numero_literal': numero_a_texto_basico(venta.total),
        'volver_url': reverse('ventas_list') if es_equipo_interno else reverse('catalogo_cliente'),
        'volver_texto': 'Volver a ventas' if es_equipo_interno else 'Volver al catalogo',
    })


@login_required
@user_passes_test(es_staff_o_superuser)
def productos_list(request):
    q = request.GET.get('q', '').strip()

    productos = (
        Producto.objects
        .prefetch_related('imagenes_extra')
        .all()
        .order_by('-id')
    )

    if q:
        productos = productos.filter(
            Q(codigo__icontains=q) |
            Q(nombre__icontains=q) |
            Q(marca__icontains=q) |
            Q(modelo__icontains=q)
        )

    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return render(request, 'tienda/partials/productos_grid.html', {
            'productos': productos
        })

    return render(request, 'tienda/productos_list.html', {
        'productos': productos,
        'q': q,
    })


@login_required
@user_passes_test(es_staff_o_superuser)
def producto_detail(request, pk):
    producto = get_object_or_404(
        Producto.objects.prefetch_related('imagenes_extra'),
        pk=pk
    )

    return render(request, 'tienda/producto_detail.html', {
        'producto': producto
    })


@login_required
@user_passes_test(solo_superuser)
@transaction.atomic
def producto_create(request):
    modo = (request.POST.get('modo') or request.GET.get('modo') or 'compra').strip().lower()
    if modo not in {'compra', 'manual'}:
        modo = 'compra'

    detalles_compra = obtener_detalles_compra_para_catalogo()
    detalle_actual = None
    detalle_actual_id = request.POST.get('detalle_compra_id') or request.GET.get('detalle_compra_id') or ''

    if detalle_actual_id:
        detalle_actual = detalles_compra.filter(pk=detalle_actual_id).first()

    if modo == 'compra':
        if request.method == 'POST':
            if detalle_actual is None:
                form = ProductoCatalogoForm(request.POST)
                messages.error(request, 'Debes seleccionar un producto base desde compras proveedor.')
            else:
                detalle_producto_original_id = detalle_actual.producto_id
                producto_base = construir_producto_desde_detalle(detalle_actual)
                form = ProductoCatalogoForm(request.POST, request.FILES, instance=producto_base)

                if form.is_valid():
                    producto = form.save(commit=False)
                    producto.costo_referencia = detalle_actual.costo_unitario
                    producto.save()

                    if detalle_actual.producto_id != producto.id:
                        detalle_actual.producto = producto
                        detalle_actual.save(update_fields=['producto'])

                    if detalle_producto_original_id != producto.id:
                        sincronizar_stock_desde_detalle_si_corresponde(
                            detalle_actual,
                            producto,
                            request.user,
                        )

                    imagenes = request.FILES.getlist('imagenes_extra')
                    for img in imagenes:
                        if img:
                            ProductoImagen.objects.create(
                                producto=producto,
                                imagen=img
                            )

                    messages.success(request, 'Producto completado correctamente desde compras proveedor.')
                    return redirect('producto_detail', pk=producto.pk)
        else:
            initial = {'activo': True}
            if detalle_actual:
                if detalle_actual.producto_id:
                    form = ProductoCatalogoForm(instance=detalle_actual.producto)
                else:
                    initial.update({
                        'descripcion': detalle_actual.descripcion_base,
                        'precio': detalle_actual.precio_venta_sugerido or detalle_actual.costo_unitario,
                    })
                    form = ProductoCatalogoForm(initial=initial)
            else:
                form = ProductoCatalogoForm(initial=initial)
    else:
        if request.method == 'POST':
            form = ProductoForm(request.POST, request.FILES)

            if form.is_valid():
                producto = form.save()

                imagenes = request.FILES.getlist('imagenes_extra')
                for img in imagenes:
                    if img:
                        ProductoImagen.objects.create(
                            producto=producto,
                            imagen=img
                        )

                messages.success(request, 'Producto creado correctamente.')
                return redirect('productos_list')
        else:
            form = ProductoForm()

    return render(request, 'tienda/producto_form.html', {
        'form': form,
        'titulo': 'Nuevo producto',
        'modo': modo,
        'detalles_compra': detalles_compra,
        'detalle_actual': detalle_actual,
    })


@login_required
@user_passes_test(solo_superuser)
@transaction.atomic
def producto_update(request, pk):
    producto = get_object_or_404(
        Producto.objects.prefetch_related('imagenes_extra'),
        pk=pk
    )
    imagenes_eliminar_ids = []

    if request.method == 'POST':
        imagenes_eliminar_ids = request.POST.getlist('imagenes_eliminar')
        form = ProductoForm(request.POST, request.FILES, instance=producto)

        if form.is_valid():
            producto = form.save()

            if imagenes_eliminar_ids:
                ProductoImagen.objects.filter(
                    producto=producto,
                    id__in=imagenes_eliminar_ids,
                ).delete()

            imagenes = request.FILES.getlist('imagenes_extra')
            for img in imagenes:
                if img:
                    ProductoImagen.objects.create(
                        producto=producto,
                        imagen=img
                    )

            messages.success(request, 'Producto actualizado correctamente.')
            return redirect('productos_list')
    else:
        form = ProductoForm(instance=producto)

    return render(request, 'tienda/producto_form.html', {
        'form': form,
        'titulo': 'Editar producto',
        'producto': producto,
        'modo': 'manual',
        'detalles_compra': [],
        'detalle_actual': None,
        'imagenes_eliminar_ids': imagenes_eliminar_ids,
    })


@login_required
@user_passes_test(solo_superuser)
@transaction.atomic
def producto_delete(request, pk):
    producto = get_object_or_404(Producto, pk=pk)

    if request.method == 'POST':
        try:
            if DetalleVenta.objects.filter(producto=producto).exists():
                raise ProtectedError('Producto relacionado con ventas.', producto)

            if ReclamoProveedor.objects.filter(producto=producto).exists():
                raise ProtectedError('Producto relacionado con reclamos.', producto)

            if DevolucionProveedor.objects.filter(producto=producto).exists():
                raise ProtectedError('Producto relacionado con devoluciones.', producto)

            MovimientoInventario.objects.filter(producto=producto).delete()
            producto.delete()
            messages.success(request, 'Producto eliminado correctamente.')
        except ProtectedError:
            messages.error(
                request,
                'No se puede eliminar este producto porque ya esta relacionado con ventas, reclamos o devoluciones.'
            )
        return redirect('productos_list')

    return render(request, 'tienda/producto_confirm_delete.html', {
        'producto': producto
    })


@login_required
@user_passes_test(es_staff_o_superuser)
def clientes_list(request):
    q = request.GET.get('q', '').strip()

    clientes = Cliente.objects.all().order_by('id')

    if q:
        clientes = clientes.filter(
            Q(nombres__icontains=q) |
            Q(apellidos__icontains=q) |
            Q(ci_nit__icontains=q) |
            Q(telefono__icontains=q) |
            Q(email__icontains=q)
        )

    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return render(request, 'tienda/partials/clientes_table.html', {
            'clientes': clientes
        })

    return render(request, 'tienda/clientes_list.html', {
        'clientes': clientes,
        'q': q,
    })


@login_required
@user_passes_test(solo_superuser)
def cliente_create(request):
    if request.method == 'POST':
        form = ClienteForm(request.POST)

        if form.is_valid():
            form.save()
            messages.success(request, 'Cliente creado correctamente.')
            return redirect('clientes_list')
    else:
        form = ClienteForm()

    return render(request, 'tienda/cliente_form.html', {
        'form': form,
        'titulo': 'Nuevo cliente',
    })


@login_required
@user_passes_test(solo_superuser)
def cliente_update(request, pk):
    cliente = get_object_or_404(Cliente, pk=pk)

    if request.method == 'POST':
        form = ClienteForm(request.POST, instance=cliente)

        if form.is_valid():
            form.save()
            messages.success(request, 'Cliente actualizado correctamente.')
            return redirect('clientes_list')
    else:
        form = ClienteForm(instance=cliente)

    return render(request, 'tienda/cliente_form.html', {
        'form': form,
        'titulo': 'Editar cliente',
        'cliente': cliente,
    })


@login_required
@user_passes_test(solo_superuser)
def cliente_delete(request, pk):
    cliente = get_object_or_404(Cliente, pk=pk)

    if request.method == 'POST':
        try:
            cliente.delete()
            messages.success(request, 'Cliente eliminado correctamente.')
        except ProtectedError:
            messages.error(
                request,
                'No se puede eliminar este cliente porque ya está relacionado con ventas registradas. '
                'Puedes editar sus datos, pero no borrarlo.'
            )
        return redirect('clientes_list')

    return render(request, 'tienda/cliente_confirm_delete.html', {
        'cliente': cliente
    })


@login_required
@user_passes_test(es_staff_o_superuser)
def ventas_list(request):
    q = request.GET.get('q', '').strip()

    ventas = (
        Venta.objects
        .select_related('cliente', 'usuario')
        .all()
        .order_by('-id')
    )

    if q:
        ventas = ventas.filter(
            Q(numero_factura__icontains=q) |
            Q(cliente__nombres__icontains=q) |
            Q(cliente__apellidos__icontains=q) |
            Q(cliente__ci_nit__icontains=q) |
            Q(usuario__username__icontains=q) |
            Q(metodo_pago__icontains=q) |
            Q(estado_pago__icontains=q)
        )

    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return render(request, 'tienda/partials/ventas_table.html', {
            'ventas': ventas
        })

    return render(request, 'tienda/ventas_list.html', {
        'ventas': ventas,
        'q': q,
    })


@login_required
@user_passes_test(es_staff_o_superuser)
def venta_detail(request, pk):
    venta = get_object_or_404(
        Venta.objects.select_related('cliente', 'usuario').prefetch_related('detalles__producto'),
        pk=pk
    )

    return render(request, 'tienda/venta_detail.html', {
        'venta': venta
    })


@login_required
@user_passes_test(solo_superuser)
def pagos_pendientes(request):
    ventas = (
        Venta.objects
        .select_related('cliente', 'usuario')
        .filter(estado_pago='pendiente')
        .order_by('-id')
    )

    return render(request, 'tienda/pagos_pendientes.html', {
        'ventas': ventas
    })


@login_required
@user_passes_test(solo_superuser)
def confirmar_pago(request, pk):
    venta = get_object_or_404(Venta, pk=pk)

    if request.method == 'POST':
        venta.estado_pago = 'pagado'
        venta.notificacion_cliente_vista = False
        venta.save()
        messages.success(request, f'Pago de la factura {venta.numero_factura} confirmado correctamente.')

    return redirect('pagos_pendientes')


@login_required
@user_passes_test(solo_superuser)
def rechazar_pago(request, pk):
    venta = get_object_or_404(Venta, pk=pk)

    if request.method == 'POST':
        venta.estado_pago = 'rechazado'
        venta.notificacion_cliente_vista = False
        venta.save()
        messages.warning(request, f'Pago de la factura {venta.numero_factura} fue marcado como rechazado.')

    return redirect('pagos_pendientes')


@login_required
def consultar_notificacion_pago(request):
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

    if not venta:
        return JsonResponse({'hay_notificacion': False})

    return JsonResponse({
        'hay_notificacion': True,
        'venta_id': venta.pk,
        'numero_factura': venta.numero_factura,
        'estado_pago': venta.estado_pago,
        'mensaje': (
            f"Tu compra con factura {venta.numero_factura} fue confirmada correctamente."
            if venta.estado_pago == 'pagado'
            else f"Tu pago de la factura {venta.numero_factura} fue rechazado."
        )
    })


@login_required
def marcar_notificacion_pago_vista(request, pk):
    venta = get_object_or_404(
        Venta,
        pk=pk,
        cliente__user=request.user
    )

    if request.method == 'POST':
        venta.notificacion_cliente_vista = True
        venta.save(update_fields=['notificacion_cliente_vista'])
        return JsonResponse({'ok': True})

    return JsonResponse({'ok': False}, status=400)


# =====================================
# PROVEEDORES
# =====================================

@login_required
@user_passes_test(es_staff_o_superuser)
def proveedores_list(request):
    q = request.GET.get('q', '').strip()

    proveedores = Proveedor.objects.all().order_by('nombre')

    if q:
        proveedores = proveedores.filter(
            Q(nombre__icontains=q) |
            Q(razon_social__icontains=q) |
            Q(nit__icontains=q) |
            Q(contacto__icontains=q) |
            Q(telefono__icontains=q) |
            Q(email__icontains=q)
        )

    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return render(request, 'tienda/partials/proveedores_table.html', {
            'proveedores': proveedores
        })

    return render(request, 'tienda/proveedores_list.html', {
        'proveedores': proveedores,
        'q': q,
    })


@login_required
@user_passes_test(es_staff_o_superuser)
def proveedor_create(request):
    if request.method == 'POST':
        form = ProveedorForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Proveedor creado correctamente.')
            return redirect('proveedores_list')
    else:
        form = ProveedorForm()

    return render(request, 'tienda/proveedor_form.html', {
        'form': form,
        'titulo': 'Nuevo proveedor'
    })


@login_required
@user_passes_test(es_staff_o_superuser)
def proveedor_update(request, pk):
    proveedor = get_object_or_404(Proveedor, pk=pk)

    if request.method == 'POST':
        form = ProveedorForm(request.POST, instance=proveedor)
        if form.is_valid():
            form.save()
            messages.success(request, 'Proveedor actualizado correctamente.')
            return redirect('proveedores_list')
    else:
        form = ProveedorForm(instance=proveedor)

    return render(request, 'tienda/proveedor_form.html', {
        'form': form,
        'titulo': 'Editar proveedor',
        'proveedor': proveedor
    })


@login_required
@user_passes_test(solo_superuser)
def proveedor_delete(request, pk):
    proveedor = get_object_or_404(Proveedor, pk=pk)

    if request.method == 'POST':
        try:
            proveedor.delete()
            messages.success(request, 'Proveedor eliminado correctamente.')
        except ProtectedError:
            messages.error(
                request,
                'No se puede eliminar este proveedor porque ya está relacionado con compras registradas.'
            )
        return redirect('proveedores_list')

    return render(request, 'tienda/proveedor_confirm_delete.html', {
        'proveedor': proveedor
    })


# =====================================
# COMPRAS A PROVEEDOR
# =====================================

@login_required
@user_passes_test(es_staff_o_superuser)
def compras_proveedor_list(request):
    q = request.GET.get('q', '').strip()

    compras = CompraProveedor.objects.select_related('proveedor', 'usuario').all()

    if q:
        compras = compras.filter(
            Q(numero_compra__icontains=q) |
            Q(proveedor__nombre__icontains=q) |
            Q(proveedor__razon_social__icontains=q) |
            Q(usuario__username__icontains=q) |
            Q(estado__icontains=q) |
            Q(metodo_pago__icontains=q)
        )

    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return render(request, 'tienda/partials/compras_proveedor_table.html', {
            'compras': compras
        })

    return render(request, 'tienda/compras_proveedor_list.html', {
        'compras': compras,
        'q': q,
    })


@login_required
@user_passes_test(es_staff_o_superuser)
@transaction.atomic
def compra_proveedor_create(request):
    productos = Producto.objects.filter(activo=True).order_by('nombre')

    if request.method == 'POST':
        form = CompraProveedorForm(request.POST)

        producto_ids = request.POST.getlist('producto[]')
        cantidades = request.POST.getlist('cantidad[]')
        costos = request.POST.getlist('costo_unitario[]')

        if form.is_valid():
            filas = []
            subtotal = Decimal('0.00')

            for producto_id, cantidad_raw, costo_raw in zip(producto_ids, cantidades, costos):
                if not producto_id:
                    continue

                try:
                    cantidad = int(cantidad_raw)
                    costo_unitario = Decimal(costo_raw)
                except (ValueError, InvalidOperation):
                    continue

                if cantidad <= 0 or costo_unitario <= 0:
                    continue

                producto = get_object_or_404(Producto, pk=producto_id)
                sub = Decimal(cantidad) * costo_unitario

                filas.append({
                    'producto': producto,
                    'cantidad': cantidad,
                    'costo_unitario': costo_unitario,
                    'subtotal': sub,
                })

                subtotal += sub

            if not filas:
                messages.error(request, 'Debes agregar al menos un producto válido a la compra.')
                return render(request, 'tienda/compra_proveedor_form.html', {
                    'form': form,
                    'productos': productos,
                })

            compra = form.save(commit=False)
            compra.usuario = request.user
            compra.numero_compra = generar_numero_compra()
            compra.subtotal = subtotal
            compra.total = subtotal - compra.descuento
            if compra.total < 0:
                compra.total = Decimal('0.00')
            compra.save()

            for fila in filas:
                DetalleCompraProveedor.objects.create(
                    compra=compra,
                    producto=fila['producto'],
                    cantidad=fila['cantidad'],
                    costo_unitario=fila['costo_unitario'],
                    subtotal=fila['subtotal'],
                )

            if compra.estado == 'recibida':
                aplicar_stock_compra(compra)

            messages.success(request, 'Compra a proveedor registrada correctamente.')
            return redirect('compra_proveedor_detail', pk=compra.pk)
    else:
        form = CompraProveedorForm(initial={'estado': 'pendiente'})

    return render(request, 'tienda/compra_proveedor_form.html', {
        'form': form,
        'productos': productos,
    })


@login_required
@user_passes_test(es_staff_o_superuser)
def compra_proveedor_detail(request, pk):
    compra = get_object_or_404(
        CompraProveedor.objects.select_related('proveedor', 'usuario').prefetch_related('detalles__producto'),
        pk=pk
    )

    return render(request, 'tienda/compra_proveedor_detail.html', {
        'compra': compra
    })


@login_required
@user_passes_test(es_staff_o_superuser)
@transaction.atomic
def compra_proveedor_marcar_recibida(request, pk):
    compra = get_object_or_404(CompraProveedor, pk=pk)

    if request.method == 'POST':
        if compra.estado == 'recibida' and compra.stock_aplicado:
            messages.info(request, 'Esta compra ya fue marcada como recibida anteriormente.')
            return redirect('compra_proveedor_detail', pk=compra.pk)

        compra.estado = 'recibida'
        compra.save(update_fields=['estado'])
        aplicar_stock_compra(compra)

        messages.success(request, 'Compra marcada como recibida y stock actualizado correctamente.')

    return redirect('compra_proveedor_detail', pk=compra.pk)
