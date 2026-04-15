from django.conf import settings
from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path, re_path
from django.views.static import serve

from cuentas import views as cuentas_views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('crear-admin-render/', cuentas_views.crear_admin_render, name='crear_admin_render'),
    path('configurar-google-render/', cuentas_views.configurar_google_render, name='configurar_google_render'),

    path('', include('cuentas.urls')),
    path('tienda/', include('tienda.urls')),

    path('login/', auth_views.LoginView.as_view(template_name='registration/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('accounts/', include('allauth.urls')),
]

# Servir media también en Render
urlpatterns += [
    re_path(r'^media/(?P<path>.*)$', serve, {'document_root': settings.MEDIA_ROOT}),
]