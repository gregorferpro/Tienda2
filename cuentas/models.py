from django.db import models
from django.contrib.auth.models import User


class Perfil(models.Model):
    ROL_CHOICES = (
        ('superuser', 'Superuser'),
        ('staff', 'Staff'),
        ('cliente', 'Cliente'),
    )

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='perfil')
    rol = models.CharField(max_length=20, choices=ROL_CHOICES, default='cliente')
    telefono = models.CharField(max_length=30, blank=True)
    ci_nit = models.CharField(max_length=30, blank=True)
    direccion = models.TextField(blank=True)

    def __str__(self):
        return f'{self.user.username} - {self.rol}'