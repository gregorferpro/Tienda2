from django import forms
from django.contrib.auth.models import User

from .models import Perfil


class UsuarioForm(forms.ModelForm):
    first_name = forms.CharField(label='Nombre completo')
    email = forms.EmailField()
    password = forms.CharField(widget=forms.PasswordInput, required=False)
    rol = forms.ChoiceField(choices=Perfil.ROL_CHOICES)

    class Meta:
        model = User
        fields = ['username', 'first_name', 'email', 'is_active']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        if self.instance and self.instance.pk and hasattr(self.instance, 'perfil'):
            self.fields['rol'].initial = self.instance.perfil.rol

    def save(self, commit=True):
        user = super().save(commit=False)
        password = self.cleaned_data.get('password')

        if password:
            user.set_password(password)

        if commit:
            user.save()
            perfil, _ = Perfil.objects.get_or_create(user=user)
            perfil.rol = self.cleaned_data['rol']
            perfil.save()

        return user


class RegistroManualForm(forms.Form):
    first_name = forms.CharField(
        label='Nombre completo',
        max_length=150,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Ingresa tu nombre completo'
        })
    )

    def signup(self, request, user):
        user.first_name = self.cleaned_data['first_name']
        user.save()

        perfil, _ = Perfil.objects.get_or_create(user=user)
        perfil.rol = 'cliente'
        perfil.save()

        return user