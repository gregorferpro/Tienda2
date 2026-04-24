from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from .forms import (
    ProveedorForm, CompraProveedorForm,
    ReclamoProveedorForm, DevolucionProveedorForm
)
from .models import (
    Producto, Proveedor, CompraProveedor, DetalleCompraProveedor,
    ReclamoProveedor, DevolucionProveedor, MovimientoInventario
)
from .producto_utils import get_or_create_product_from_purchase_detail


def es_staff_o_superuser(user):
    return user.is_authenticated and (
        user.is_staff or user.is_superuser or (hasattr(user, 'perfil') and getattr(user.perfil, 'rol', None) == 'superuser')
    )


def solo_superuser(user):
    return user.is_authenticated and user.is_superuser


def generar_codigo_producto():
    return f'PRD-{timezone.now().strftime("%Y%m%d%H%M%S%f")}'


def registrar_movimiento_inventario(producto, cantidad, tipo_movimiento, motivo, usuario, compra=None, devolucion=None):
    stock_anterior = producto.stock

    if tipo_movimiento == 'entrada':
        producto.stock += cantidad
    else:
        if cantidad > producto.stock:
            raise ValueError(f'No hay stock suficiente para {producto.nombre}.')
        producto.stock -= cantidad

    producto.save()

    MovimientoInventario.objects.create(
        producto=producto,
        compra=compra,
        devolucion=devolucion,
        cantidad=cantidad,
        tipo_movimiento=tipo_movimiento,
        motivo=motivo,
        stock_anterior=stock_anterior,
        stock_nuevo=producto.stock,
        usuario=usuario,
    )


def compra_tiene_stock_aplicado(compra):
    if compra.stock_aplicado:
        return True

    return MovimientoInventario.objects.filter(
        compra=compra,
        tipo_movimiento='entrada',
    ).exists()


def aplicar_stock_compra(compra, usuario):
    for detalle in compra.detalles.all():
        producto = detalle.producto

        if producto is None:
            producto = get_or_create_product_from_purchase_detail(
                detalle,
                generar_codigo_producto,
            )

        if detalle.producto_id != producto.id:
            detalle.producto = producto
            detalle.save(update_fields=['producto'])

        producto.costo_referencia = detalle.costo_unitario
        producto.save(update_fields=['costo_referencia'])

        registrar_movimiento_inventario(
            producto=producto,
            cantidad=detalle.cantidad,
            tipo_movimiento='entrada',
            motivo=f'Entrada por compra proveedor #{compra.id}',
            usuario=usuario,
            compra=compra,
        )


@login_required
@user_passes_test(es_staff_o_superuser)
def proveedores_list(request):
    q = request.GET.get('q', '').strip()

    proveedores = Proveedor.objects.all().order_by('nombre')

    if q:
        proveedores = proveedores.filter(
            Q(nombre__icontains=q) |
            Q(razon_social__icontains=q) |
            Q(nombre_comercial__icontains=q) |
            Q(telefono__icontains=q) |
            Q(nit__icontains=q)
        )

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
            nit = form.cleaned_data.get('nit', '').strip()
            telefono = form.cleaned_data.get('telefono', '').strip()
            nombre = form.cleaned_data.get('nombre', '').strip()

            posible_dup = Proveedor.objects.filter(
                Q(nombre__iexact=nombre) |
                (Q(nit__iexact=nit) & ~Q(nit='')) |
                (Q(telefono__iexact=telefono) & ~Q(telefono=''))
            ).exists()

            if posible_dup:
                messages.warning(request, 'Advertencia: existe un proveedor con datos similares. Verifica duplicidad.')

            form.save()
            messages.success(request, 'Proveedor registrado correctamente.')
            return redirect('proveedores_list')
    else:
        form = ProveedorForm()

    return render(request, 'tienda/proveedor_form.html', {
        'form': form,
        'titulo': 'Nuevo proveedor',
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
        'proveedor': proveedor,
    })


@login_required
@user_passes_test(solo_superuser)
def proveedor_toggle_estado(request, pk):
    proveedor = get_object_or_404(Proveedor, pk=pk)
    proveedor.estado = 'inactivo' if proveedor.estado == 'activo' else 'activo'
    proveedor.save(update_fields=['estado'])
    messages.success(request, f'Proveedor ahora está {proveedor.estado}.')
    return redirect('proveedores_list')


@login_required
@user_passes_test(es_staff_o_superuser)
def compras_proveedor_list(request):
    q = request.GET.get('q', '').strip()

    compras = CompraProveedor.objects.select_related('proveedor', 'usuario').all()

    if q:
        compras = compras.filter(
            Q(proveedor__nombre__icontains=q) |
            Q(numero_documento__icontains=q) |
            Q(referencia_libre__icontains=q) |
            Q(usuario__username__icontains=q) |
            Q(estado__icontains=q)
        )

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

        producto_ids = request.POST.getlist('producto_id[]')
        producto_codigos = request.POST.getlist('producto_codigo[]')
        producto_nombres = request.POST.getlist('producto_nombre[]')
        producto_marcas = request.POST.getlist('producto_marca[]')
        producto_modelos = request.POST.getlist('producto_modelo[]')
        tipos = request.POST.getlist('tipo_producto[]')
        categorias = request.POST.getlist('categoria[]')
        descripciones = request.POST.getlist('descripcion_base[]')
        precios_sugeridos = request.POST.getlist('precio_venta_sugerido[]')
        cantidades = request.POST.getlist('cantidad[]')
        costos = request.POST.getlist('costo_unitario[]')

        if form.is_valid():
            compra = form.save(commit=False)
            compra.usuario = request.user
            compra.subtotal = Decimal('0.00')
            compra.total = Decimal('0.00')
            compra.save()

            filas_validas = 0
            subtotal = Decimal('0.00')

            for i in range(len(cantidades)):
                producto_ref = None
                if i < len(producto_ids) and producto_ids[i]:
                    producto_ref = get_object_or_404(Producto, pk=producto_ids[i])

                codigo = producto_codigos[i].strip() if i < len(producto_codigos) else ''
                nombre = producto_nombres[i].strip() if i < len(producto_nombres) else ''
                marca = producto_marcas[i].strip() if i < len(producto_marcas) else ''
                modelo = producto_modelos[i].strip() if i < len(producto_modelos) else ''
                tipo_producto = tipos[i] if i < len(tipos) else 'otro'
                categoria = categorias[i].strip() if i < len(categorias) else ''
                descripcion_base = descripciones[i].strip() if i < len(descripciones) else ''

                try:
                    precio_venta_sugerido = Decimal(precios_sugeridos[i] or '0')
                    cantidad = int(cantidades[i] or '0')
                    costo_unitario = Decimal(costos[i] or '0')
                except (InvalidOperation, ValueError):
                    continue

                if cantidad <= 0 or costo_unitario <= 0:
                    continue

                if not producto_ref and not nombre:
                    continue

                if producto_ref:
                    codigo = producto_ref.codigo
                    nombre = producto_ref.nombre
                    marca = producto_ref.marca
                    modelo = producto_ref.modelo
                    tipo_producto = producto_ref.tipo_producto
                    categoria = producto_ref.categoria

                detalle = DetalleCompraProveedor.objects.create(
                    compra=compra,
                    producto=producto_ref,
                    producto_codigo=codigo,
                    producto_nombre=nombre,
                    producto_marca=marca,
                    producto_modelo=modelo,
                    tipo_producto=tipo_producto or 'otro',
                    categoria=categoria,
                    descripcion_base=descripcion_base,
                    precio_venta_sugerido=precio_venta_sugerido,
                    cantidad=cantidad,
                    costo_unitario=costo_unitario,
                    subtotal=Decimal(cantidad) * costo_unitario,
                )

                subtotal += detalle.subtotal
                filas_validas += 1

            if filas_validas == 0:
                compra.delete()
                messages.error(request, 'Debes ingresar al menos un ítem válido.')
                return render(request, 'tienda/compra_proveedor_form.html', {
                    'form': form,
                    'productos': productos,
                })

            compra.subtotal = subtotal
            compra.total = subtotal - compra.descuento
            if compra.total < 0:
                compra.total = Decimal('0.00')
            compra.save(update_fields=['subtotal', 'total'])

            messages.success(request, 'Compra registrada correctamente.')
            return redirect('compra_proveedor_detail', pk=compra.pk)
    else:
        form = CompraProveedorForm(initial={
            'fecha_compra': timezone.now().date(),
            'estado': 'borrador',
        })

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
        'compra': compra,
        'puede_aplicar_stock': not compra_tiene_stock_aplicado(compra),
    })


@login_required
@user_passes_test(es_staff_o_superuser)
@transaction.atomic
def compra_proveedor_confirmar(request, pk):
    compra = get_object_or_404(
        CompraProveedor.objects.prefetch_related('detalles__producto'),
        pk=pk
    )

    stock_ya_aplicado = compra_tiene_stock_aplicado(compra)

    if stock_ya_aplicado:
        if compra.estado != 'confirmada':
            compra.estado = 'confirmada'
            compra.stock_aplicado = True
            compra.save(update_fields=['estado', 'stock_aplicado'])
            messages.info(request, 'La compra ya tenia movimientos de stock y fue sincronizada con el estado confirmado.')
            return redirect('compra_proveedor_detail', pk=compra.pk)

        if not compra.stock_aplicado:
            compra.stock_aplicado = True
            compra.save(update_fields=['stock_aplicado'])
        messages.info(request, 'Esta compra ya fue confirmada y el stock ya estaba aplicado.')
        return redirect('compra_proveedor_detail', pk=compra.pk)

    if request.method == 'POST':
        aplicar_stock_compra(compra, request.user)
        compra.estado = 'confirmada'
        compra.stock_aplicado = True
        compra.save(update_fields=['estado', 'stock_aplicado'])

        messages.success(request, 'Compra confirmada y stock actualizado correctamente.')

    return redirect('compra_proveedor_detail', pk=compra.pk)


@login_required
@user_passes_test(es_staff_o_superuser)
def reclamos_proveedor_list(request):
    q = request.GET.get('q', '').strip()

    reclamos = ReclamoProveedor.objects.select_related('proveedor', 'compra', 'producto', 'usuario').all()

    if q:
        reclamos = reclamos.filter(
            Q(proveedor__nombre__icontains=q) |
            Q(producto__nombre__icontains=q) |
            Q(motivo__icontains=q) |
            Q(estado__icontains=q)
        )

    return render(request, 'tienda/reclamos_proveedor_list.html', {
        'reclamos': reclamos,
        'q': q,
    })


@login_required
@user_passes_test(es_staff_o_superuser)
def reclamo_proveedor_create(request):
    if request.method == 'POST':
        form = ReclamoProveedorForm(request.POST)
        if form.is_valid():
            reclamo = form.save(commit=False)
            reclamo.usuario = request.user

            # Validación de trazabilidad
            compra = reclamo.compra
            proveedor = reclamo.proveedor
            producto = reclamo.producto

            if compra.proveedor_id != proveedor.id:
                messages.error(request, 'La compra seleccionada no pertenece al proveedor elegido.')
            elif not compra.detalles.filter(producto=producto).exists():
                messages.error(request, 'El producto seleccionado no pertenece a la compra origen.')
            else:
                reclamo.save()
                messages.success(request, 'Reclamo registrado correctamente.')
                return redirect('reclamo_proveedor_detail', pk=reclamo.pk)
    else:
        form = ReclamoProveedorForm(initial={'fecha_reclamo': timezone.now().date()})

    return render(request, 'tienda/reclamo_proveedor_form.html', {
        'form': form,
        'titulo': 'Nuevo reclamo a proveedor',
    })


@login_required
@user_passes_test(es_staff_o_superuser)
def reclamo_proveedor_detail(request, pk):
    reclamo = get_object_or_404(
        ReclamoProveedor.objects.select_related('proveedor', 'compra', 'producto', 'usuario'),
        pk=pk
    )

    return render(request, 'tienda/reclamo_proveedor_detail.html', {
        'reclamo': reclamo,
    })


@login_required
@user_passes_test(es_staff_o_superuser)
@transaction.atomic
def devolucion_proveedor_create(request, reclamo_pk):
    reclamo = get_object_or_404(
        ReclamoProveedor.objects.select_related('proveedor', 'compra', 'producto'),
        pk=reclamo_pk
    )

    if hasattr(reclamo, 'devolucion'):
        messages.info(request, 'Este reclamo ya tiene una devolución registrada.')
        return redirect('reclamo_proveedor_detail', pk=reclamo.pk)

    if request.method == 'POST':
        form = DevolucionProveedorForm(request.POST)
        if form.is_valid():
            devolucion = form.save(commit=False)
            devolucion.reclamo = reclamo
            devolucion.proveedor = reclamo.proveedor
            devolucion.compra = reclamo.compra
            devolucion.producto = reclamo.producto
            devolucion.cantidad = reclamo.cantidad
            devolucion.usuario = request.user
            devolucion.save()

            registrar_movimiento_inventario(
                producto=devolucion.producto,
                cantidad=devolucion.cantidad,
                tipo_movimiento='salida',
                motivo=f'Devolución a proveedor por reclamo #{reclamo.id}',
                usuario=request.user,
                devolucion=devolucion,
            )

            reclamo.estado = 'devuelto'
            reclamo.save(update_fields=['estado'])

            messages.success(request, 'Devolución registrada y stock descontado correctamente.')
            return redirect('reclamo_proveedor_detail', pk=reclamo.pk)
    else:
        form = DevolucionProveedorForm(initial={
            'fecha_devolucion': timezone.now().date(),
            'estado': 'registrada',
            'motivo': reclamo.motivo,
        })

    return render(request, 'tienda/devolucion_proveedor_form.html', {
        'form': form,
        'reclamo': reclamo,
    })
