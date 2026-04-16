from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.models import User
from django.contrib.sites.models import Site
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render

from allauth.socialaccount.models import SocialApp

from .forms import UsuarioForm
from .models import Perfil

import os


def solo_superuser(user):
    return user.is_authenticated and (
        user.is_superuser or (hasattr(user, 'perfil') and user.perfil.rol == 'superuser')
    )


def home_redirect(request):
    if request.user.is_authenticated:
        if hasattr(request.user, 'perfil') and request.user.perfil.rol == 'cliente':
            return redirect('catalogo_cliente')
        return redirect('dashboard')
    return redirect('catalogo_cliente')


@login_required
def dashboard(request):
    if hasattr(request.user, 'perfil') and request.user.perfil.rol == 'cliente':
        return redirect('catalogo_cliente')
    return render(request, 'cuentas/dashboard.html')


@login_required
@user_passes_test(solo_superuser)
def usuarios_list(request):
    q = request.GET.get('q', '').strip()

    usuarios = User.objects.all().order_by('id')

    if q:
        usuarios = usuarios.filter(
            Q(first_name__icontains=q) |
            Q(last_name__icontains=q) |
            Q(username__icontains=q) |
            Q(email__icontains=q)
        )

    return render(request, 'cuentas/usuarios_list.html', {
        'usuarios': usuarios,
        'q': q,
    })


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
        'titulo': 'Nuevo usuario',
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
        'titulo': 'Editar usuario',
        'usuario_obj': usuario,
    })


@login_required
@user_passes_test(solo_superuser)
def usuario_delete(request, pk):
    usuario = get_object_or_404(User, pk=pk)

    if request.method == 'POST':
        usuario.delete()
        messages.success(request, 'Usuario eliminado correctamente.')
        return redirect('usuarios_list')

    return render(request, 'cuentas/usuario_confirm_delete.html', {
        'usuario': usuario
    })


def crear_admin_render(request):
    username = os.environ.get('ADMIN_USERNAME', 'admin')
    email = os.environ.get('ADMIN_EMAIL', 'admin@example.com')
    password = os.environ.get('ADMIN_PASSWORD', 'Admin12345678')

    user, _ = User.objects.get_or_create(username=username)
    user.email = email
    user.is_staff = True
    user.is_superuser = True
    user.set_password(password)
    user.save()

    perfil, _ = Perfil.objects.get_or_create(user=user)
    perfil.rol = 'superuser'
    perfil.save()

    return HttpResponse(f'Superusuario listo: {username}')


def configurar_google_render(request):
    client_id = os.environ.get('GOOGLE_CLIENT_ID')
    secret = os.environ.get('GOOGLE_CLIENT_SECRET')

    if not client_id or not secret:
        return HttpResponse('Faltan GOOGLE_CLIENT_ID o GOOGLE_CLIENT_SECRET', status=400)

    site, _ = Site.objects.get_or_create(
        id=1,
        defaults={'domain': 'tienda2-fdi.onrender.com', 'name': 'Tienda2'}
    )
    site.domain = os.environ.get('SITE_DOMAIN', 'tienda2-fdi.onrender.com')
    site.name = 'Tienda2'
    site.save()

    app, _ = SocialApp.objects.get_or_create(provider='google', defaults={'name': 'Google'})
    app.name = 'Google'
    app.client_id = client_id
    app.secret = secret
    app.save()
    app.sites.set([site])

    return HttpResponse('Google configurado correctamente')