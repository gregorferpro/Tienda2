from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db import transaction
from django.db.models import Q
from django.db.models.deletion import ProtectedError
from django.shortcuts import get_object_or_404, redirect, render

from .forms import ProductoForm, ClienteForm, CheckoutForm
from .models import Producto, ProductoImagen, Cliente, Venta, DetalleVenta


def generar_numero_factura():
    from django.utils import timezone
    return timezone.now().strftime('%Y%m%d%H%M%S')


def numero_a_texto_basico(numero):
    return f'{numero:.2f} bolivianos'


def es_staff_o_superuser(user):
    return user.is_authenticated and (
        user.is_superuser
        or user.is_staff
        or (hasattr(user, 'perfil') and user.perfil.rol in ['superuser', 'staff'])
    )


def solo_superuser(user):
    return user.is_authenticated and (
        user.is_superuser
        or (hasattr(user, 'perfil') and user.perfil.rol == 'superuser')
    )


def obtener_carrito(request):
    return request.session.setdefault('carrito', {})


# =========================
# CATÁLOGO PÚBLICO CLIENTE
# =========================

def catalogo_cliente(request):
    q = request.GET.get('q', '').strip()
    productos = Producto.objects.filter(activo=True).order_by('-id')

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
    producto = get_object_or_404(Producto, pk=pk, activo=True)
    return render(request, 'tienda/detalle_producto_cliente.html', {
        'producto': producto
    })


# =========================
# CARRITO Y CHECKOUT
# =========================

@login_required
def agregar_carrito(request, pk):
    producto = get_object_or_404(Producto, pk=pk, activo=True)
    carrito = obtener_carrito(request)

    item = carrito.get(str(pk), {'cantidad': 0})

    if item['cantidad'] < producto.stock:
        item['cantidad'] += 1
        carrito[str(pk)] = item
        request.session.modified = True
        messages.success(request, 'Producto agregado al carrito.')
    else:
        messages.warning(request, 'No hay suficiente stock disponible.')

    return redirect('carrito')


@login_required
def quitar_carrito(request, pk):
    carrito = obtener_carrito(request)

    if str(pk) in carrito:
        del carrito[str(pk)]
        request.session.modified = True
        messages.success(request, 'Producto quitado del carrito.')

    return redirect('carrito')


@login_required
def carrito(request):
    carrito_data = obtener_carrito(request)
    items = []
    total = Decimal('0.00')

    for pk, data in carrito_data.items():
        producto = get_object_or_404(Producto, pk=int(pk), activo=True)
        subtotal = producto.precio * data['cantidad']
        total += subtotal

        items.append({
            'producto': producto,
            'cantidad': data['cantidad'],
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
        producto = get_object_or_404(Producto, pk=int(pk), activo=True)
        subtotal = producto.precio * data['cantidad']
        total += subtotal

        items.append({
            'producto': producto,
            'cantidad': data['cantidad'],
            'subtotal': subtotal,
        })

    if request.method == 'POST':
        form = CheckoutForm(request.POST)

        if form.is_valid():
            cliente = Cliente.objects.create(
                user=request.user,
                nombres=form.cleaned_data['nombres'],
                apellidos=form.cleaned_data['apellidos'],
                ci_nit=form.cleaned_data['ci_nit'],
                telefono=form.cleaned_data['telefono'],
                email=form.cleaned_data.get('email', ''),
                direccion=form.cleaned_data.get('direccion', ''),
                estado='activo'
            )

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
                    messages.error(request, f'Stock insuficiente para {producto.nombre}')
                    return redirect('carrito')

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
        form = CheckoutForm()

    return render(request, 'tienda/checkout.html', {
        'form': form,
        'items': items,
        'total': total,
    })


@login_required
def factura_view(request, pk):
    venta = get_object_or_404(
        Venta.objects.prefetch_related('detalles__producto'),
        pk=pk
    )
    return render(request, 'tienda/factura.html', {
        'venta': venta,
        'numero_literal': numero_a_texto_basico(venta.total)
    })


# =========================
# PANEL ADMINISTRATIVO
# =========================

@login_required
@user_passes_test(es_staff_o_superuser)
def productos_list(request):
    q = request.GET.get('q', '').strip()
    productos = Producto.objects.all().order_by('-id')

    if q:
        productos = productos.filter(
            Q(codigo__icontains=q) |
            Q(nombre__icontains=q) |
            Q(marca__icontains=q) |
            Q(modelo__icontains=q)
        )

    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return render(request, 'tienda/partials/productos_grid.html', {'productos': productos})

    return render(request, 'tienda/productos_list.html', {
        'productos': productos,
        'q': q,
    })


@login_required
@user_passes_test(es_staff_o_superuser)
def producto_detail(request, pk):
    producto = get_object_or_404(Producto, pk=pk)
    return render(request, 'tienda/producto_detail.html', {'producto': producto})


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
        'titulo': 'Nuevo producto'
    })


@login_required
@user_passes_test(solo_superuser)
def producto_update(request, pk):
    producto = get_object_or_404(Producto, pk=pk)

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
        'producto': producto
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

    return render(request, 'tienda/producto_confirm_delete.html', {'producto': producto})


@login_required
@user_passes_test(es_staff_o_superuser)
def clientes_list(request):
    q = request.GET.get('q', '').strip()
    clientes = Cliente.objects.all().order_by('id')

    if q:
        clientes = clientes.filter(
            Q(nombres__icontains=q) |
            Q(apellidos__icontains=q) |
            Q(telefono__icontains=q) |
            Q(ci_nit__icontains=q)
        )

    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return render(request, 'tienda/partials/clientes_table.html', {'clientes': clientes})

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

    return render(request, 'tienda/cliente_confirm_delete.html', {'cliente': cliente})


@login_required
@user_passes_test(lambda u: u.is_superuser or (hasattr(u, 'perfil') and u.perfil.rol in ['superuser', 'staff']))
def ventas_list(request):
    q = request.GET.get('q', '').strip()

    ventas = Venta.objects.select_related('cliente', 'usuario').all().order_by('-id')

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
        'q': q
    })


@login_required
@user_passes_test(lambda u: u.is_superuser or (hasattr(u, 'perfil') and u.perfil.rol in ['superuser', 'staff']))
def venta_detail(request, pk):
    venta = get_object_or_404(
        Venta.objects.select_related('cliente', 'usuario').prefetch_related('detalles__producto'),
        pk=pk
    )
    return render(request, 'tienda/venta_detail.html', {'venta': venta})


from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect
from .models import Producto


@login_required
def agregar_carrito(request, pk):
    producto = get_object_or_404(Producto, pk=pk, activo=True)
    carrito = obtener_carrito(request)

    item = carrito.get(str(pk), {'cantidad': 0})

    if item['cantidad'] < producto.stock:
        item['cantidad'] += 1
        carrito[str(pk)] = item
        request.session.modified = True
        messages.success(request, 'Producto agregado al carrito.')
    else:
        messages.warning(request, 'No hay suficiente stock disponible.')

    return redirect('carrito')