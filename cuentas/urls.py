from django.urls import path
from . import views

urlpatterns = [
    path('', views.home_redirect, name='home'),
    path('dashboard/', views.dashboard, name='dashboard'),

    path('usuarios/', views.usuarios_list, name='usuarios_list'),
    path('usuarios/nuevo/', views.usuario_create, name='usuario_create'),
    path('usuarios/<int:pk>/editar/', views.usuario_update, name='usuario_update'),
    path('usuarios/<int:pk>/eliminar/', views.usuario_delete, name='usuario_delete'),

    path('crear-admin-render/', views.crear_admin_render, name='crear_admin_render'),
]