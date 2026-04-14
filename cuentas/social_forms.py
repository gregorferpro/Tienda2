from django import forms
from allauth.socialaccount.forms import SignupForm as SocialSignupForm

from .models import Perfil


class RegistroGoogleForm(SocialSignupForm):
    first_name = forms.CharField(
        label='Nombre completo',
        max_length=150,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Ingresa tu nombre completo'
        })
    )

    def save(self, request):
        user = super().save(request)
        user.first_name = self.cleaned_data['first_name']
        user.save()

        perfil, _ = Perfil.objects.get_or_create(user=user)
        perfil.rol = 'cliente'
        perfil.save()

        return user