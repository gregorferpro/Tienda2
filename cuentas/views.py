from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.models import User
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render

from .forms import UsuarioForm
from .models import Perfil


def solo_superuser(user):
    return user.is_authenticated and (
        user.is_superuser
        or (hasattr(user, 'perfil') and user.perfil.rol == 'superuser')
    )


def home_redirect(request):
    if request.user.is_authenticated:
        if hasattr(request.user, 'perfil') and request.user.perfil.rol == 'cliente':
            return redirect('catalogo_cliente')
        return redirect('dashboard')
    return redirect('login')


@login_required
def dashboard(request):
    if hasattr(request.user, 'perfil') and request.user.perfil.rol == 'cliente':
        return redirect('catalogo_cliente')
    return render(request, 'cuentas/dashboard.html')


@login_required
@user_passes_test(solo_superuser)
def usuarios_list(request):
    q = request.GET.get('q', '').strip()
    usuarios = User.objects.select_related('perfil').all().order_by('id')

    if q:
        usuarios = usuarios.filter(
            Q(first_name__icontains=q) |
            Q(username__icontains=q) |
            Q(email__icontains=q) |
            Q(perfil__rol__icontains=q)
        )

    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return render(request, 'cuentas/partials/usuarios_table.html', {'usuarios': usuarios})

    return render(request, 'cuentas/usuarios_list.html', {'usuarios': usuarios, 'q': q})


@login_required
@user_passes_test(solo_superuser)
def usuario_create(request):
    if request.method == 'POST':
        form = UsuarioForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            rol = form.cleaned_data['rol']

            user.is_staff = rol in ['superuser', 'staff']
            user.is_superuser = rol == 'superuser'
            user.save()

            perfil, _ = Perfil.objects.get_or_create(user=user)
            perfil.rol = rol
            perfil.save()

            messages.success(request, 'Usuario creado correctamente.')
            return redirect('usuarios_list')
    else:
        form = UsuarioForm()

    return render(request, 'cuentas/usuario_form.html', {
        'form': form,
        'titulo': 'Nuevo usuario'
    })


@login_required
@user_passes_test(solo_superuser)
def usuario_update(request, pk):
    usuario = get_object_or_404(User, pk=pk)

    if request.method == 'POST':
        form = UsuarioForm(request.POST, instance=usuario)
        if form.is_valid():
            user = form.save(commit=False)
            rol = form.cleaned_data['rol']

            user.is_staff = rol in ['superuser', 'staff']
            user.is_superuser = rol == 'superuser'
            user.save()

            perfil, _ = Perfil.objects.get_or_create(user=user)
            perfil.rol = rol
            perfil.save()

            messages.success(request, 'Usuario actualizado correctamente.')
            return redirect('usuarios_list')
    else:
        form = UsuarioForm(instance=usuario)

    return render(request, 'cuentas/usuario_form.html', {
        'form': form,
        'titulo': 'Editar usuario'
    })


@login_required
@user_passes_test(solo_superuser)
def usuario_delete(request, pk):
    usuario = get_object_or_404(User, pk=pk)

    if request.method == 'POST':
        usuario.delete()
        messages.success(request, 'Usuario eliminado correctamente.')
        return redirect('usuarios_list')

    return render(request, 'cuentas/usuario_confirm_delete.html', {'usuario': usuario})

from django.http import HttpResponse
from django.contrib.auth.models import User


def crear_admin_render(request):
    username = "admin"
    email = "gregorbarrios07@gmail.com"
    password = "Admin12345678"

    if not User.objects.filter(username=username).exists():
        User.objects.create_superuser(username=username, email=email, password=password)
        return HttpResponse("Superusuario creado correctamente.")

    return HttpResponse("El superusuario ya existe.")