from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db import transaction
from django.db.models import Q
from django.db.models.deletion import ProtectedError
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from .forms import CheckoutForm, ClienteForm, ProductoForm
from .models import Cliente, DetalleVenta, Producto, ProductoImagen, Venta


def generar_numero_factura():
    return timezone.now().strftime('%Y%m%d%H%M%S')


def numero_a_texto_basico(numero):
    return f'{numero:.2f} bolivianos'


def es_staff_o_superuser(user):
    if not user.is_authenticated:
        return False

    if user.is_superuser or user.is_staff:
        return True

    if hasattr(user, 'perfil'):
        return user.perfil.rol in ['superuser', 'staff']

    return False


def solo_superuser(user):
    if not user.is_authenticated:
        return False

    if user.is_superuser:
        return True

    if hasattr(user, 'perfil'):
        return user.perfil.rol == 'superuser'

    return False


def obtener_carrito(request):
    carrito = request.session.get('carrito')
    if carrito is None:
        carrito = {}
        request.session['carrito'] = carrito
    return carrito


def catalogo_cliente(request):
    q = request.GET.get('q', '').strip()

    productos = (
        Producto.objects
        .filter(activo=True)
        .prefetch_related('imagenes_extra')
        .order_by('-id')
    )

    if q:
        productos = productos.filter(
            Q(nombre__icontains=q) |
            Q(codigo__icontains=q) |
            Q(marca__icontains=q) |
            Q(modelo__icontains=q)
        )

    return render(request, 'tienda/catalogo_cliente.html', {
        'productos': productos,
        'q': q,
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
    producto = get_object_or_404(Producto, pk=pk, activo=True)

    carrito = obtener_carrito(request)
    item = carrito.get(str(pk), {'cantidad': 0})

    if item['cantidad'] < producto.stock:
        item['cantidad'] += 1
        carrito[str(pk)] = item
        request.session['carrito'] = carrito
        request.session.modified = True
        messages.success(request, 'Producto agregado al carrito.')
    else:
        messages.warning(request, 'No hay suficiente stock disponible para este producto.')

    return redirect('carrito')


@login_required
def quitar_carrito(request, pk):
    carrito = obtener_carrito(request)

    if str(pk) in carrito:
        del carrito[str(pk)]
        request.session['carrito'] = carrito
        request.session.modified = True
        messages.success(request, 'Producto quitado del carrito.')

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
        subtotal = producto.precio * cantidad
        total += subtotal

        items.append({
            'producto': producto,
            'cantidad': cantidad,
            'subtotal': subtotal,
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

            if cliente.user == request.user:
                cliente.nombres = form.cleaned_data['nombres']
                cliente.apellidos = form.cleaned_data['apellidos']
                cliente.ci_nit = form.cleaned_data['ci_nit']
                cliente.telefono = form.cleaned_data['telefono']
                cliente.email = form.cleaned_data.get('email', '')
                cliente.direccion = form.cleaned_data.get('direccion', '')
                cliente.estado = 'activo'
                cliente.save()

            venta = Venta.objects.create(
                cliente=cliente,
                usuario=request.user,
                numero_factura=generar_numero_factura(),
                metodo_pago=form.cleaned_data['metodo_pago'],
                subtotal=total,
                descuento=Decimal('0.00'),
                total=total,
            )

            for item in items:
                producto = item['producto']
                cantidad = item['cantidad']

                if producto.stock < cantidad:
                    messages.error(request, f'Stock insuficiente para {producto.nombre}.')
                    raise transaction.TransactionManagementError('Stock insuficiente.')

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

    return render(request, 'tienda/factura.html', {
        'venta': venta,
        'numero_literal': numero_a_texto_basico(venta.total),
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
def producto_create(request):
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
    })


@login_required
@user_passes_test(solo_superuser)
def producto_update(request, pk):
    producto = get_object_or_404(
        Producto.objects.prefetch_related('imagenes_extra'),
        pk=pk
    )

    if request.method == 'POST':
        form = ProductoForm(request.POST, request.FILES, instance=producto)

        if form.is_valid():
            producto = form.save()

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
    })


@login_required
@user_passes_test(solo_superuser)
def producto_delete(request, pk):
    producto = get_object_or_404(Producto, pk=pk)

    if request.method == 'POST':
        try:
            producto.delete()
            messages.success(request, 'Producto eliminado correctamente.')
            return redirect('productos_list')
        except ProtectedError:
            messages.error(
                request,
                'No se puede eliminar este producto porque ya está relacionado con una venta registrada.'
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
            Q(telefono__icontains=q)
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
    })


@login_required
@user_passes_test(solo_superuser)
def cliente_delete(request, pk):
    cliente = get_object_or_404(Cliente, pk=pk)

    if request.method == 'POST':
        cliente.delete()
        messages.success(request, 'Cliente eliminado correctamente.')
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
            Q(usuario__username__icontains=q) |
            Q(metodo_pago__icontains=q)
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