from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.models import User
from django.contrib.auth.views import LoginView
from django.contrib.sites.models import Site
from django.db.models import Q
from django.db.models.deletion import ProtectedError
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from allauth.socialaccount.models import SocialApp

from .forms import UsuarioForm
from .models import Perfil

import os


def solo_superuser(user):
    return user.is_authenticated and (
        user.is_superuser or (hasattr(user, 'perfil') and user.perfil.rol == 'superuser')
    )


def destino_inicio_usuario(user):
    if hasattr(user, 'perfil') and user.perfil.rol == 'cliente':
        return 'catalogo_cliente'
    return 'dashboard'


def home_redirect(request):
    if request.user.is_authenticated:
        return redirect(destino_inicio_usuario(request.user))
    return redirect('catalogo_cliente')


class CustomLoginView(LoginView):
    template_name = 'registration/login.html'

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect(destino_inicio_usuario(request.user))
        return super().dispatch(request, *args, **kwargs)

    def get_success_url(self):
        redirect_url = self.get_redirect_url()
        if redirect_url:
            return redirect_url
        return reverse(destino_inicio_usuario(self.request.user))


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

    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return render(request, 'cuentas/partials/usuarios_table.html', {
            'usuarios': usuarios
        })

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
            form.save()
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
            form.save()
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
        try:
            usuario.delete()
            messages.success(request, 'Usuario eliminado correctamente.')
        except ProtectedError:
            messages.error(
                request,
                'No se puede eliminar este usuario porque ya está relacionado con ventas registradas. '
                'Puedes dejarlo inactivo o cambiar sus permisos, pero no borrarlo.'
            )
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
