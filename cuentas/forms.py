from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User

from .models import Perfil


class RegistroManualForm(UserCreationForm):
    first_name = forms.CharField(
        label='Nombres',
        max_length=150,
        required=True,
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    last_name = forms.CharField(
        label='Apellidos',
        max_length=150,
        required=True,
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    email = forms.EmailField(
        label='Correo electrónico',
        required=True,
        widget=forms.EmailInput(attrs={'class': 'form-control'})
    )
    telefono = forms.CharField(
        label='Teléfono',
        max_length=30,
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )

    password1 = forms.CharField(
        label='Contraseña',
        widget=forms.PasswordInput(attrs={'class': 'form-control'})
    )
    password2 = forms.CharField(
        label='Confirmar contraseña',
        widget=forms.PasswordInput(attrs={'class': 'form-control'})
    )

    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'username', 'email', 'telefono', 'password1', 'password2']
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-control'}),
        }

    def clean_email(self):
        email = self.cleaned_data['email'].strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError('Ya existe un usuario con este correo.')
        return email

    def save(self, request=None):
        user = super().save(commit=False)
        user.first_name = self.cleaned_data['first_name']
        user.last_name = self.cleaned_data['last_name']
        user.email = self.cleaned_data['email']
        user.is_staff = False
        user.is_superuser = False
        user.save()
        return user

    def signup(self, request, user):
        perfil, _ = Perfil.objects.get_or_create(user=user)
        perfil.rol = 'cliente'
        perfil.telefono = self.cleaned_data.get('telefono', '')
        perfil.save()


class UsuarioForm(forms.ModelForm):
    password1 = forms.CharField(
        label='Contraseña',
        required=False,
        widget=forms.PasswordInput(attrs={'class': 'form-control'})
    )
    password2 = forms.CharField(
        label='Confirmar contraseña',
        required=False,
        widget=forms.PasswordInput(attrs={'class': 'form-control'})
    )
    rol = forms.ChoiceField(
        choices=Perfil.ROL_CHOICES,
        widget=forms.Select(attrs={'class': 'form-control'})
    )

    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'username', 'email']
        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
            'username': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        if self.instance and self.instance.pk:
            if hasattr(self.instance, 'perfil'):
                self.fields['rol'].initial = self.instance.perfil.rol
            elif self.instance.is_superuser:
                self.fields['rol'].initial = 'superuser'
            elif self.instance.is_staff:
                self.fields['rol'].initial = 'staff'
            else:
                self.fields['rol'].initial = 'cliente'
        else:
            self.fields['password1'].required = True
            self.fields['password2'].required = True
            self.fields['rol'].initial = 'cliente'

    def clean_username(self):
        username = self.cleaned_data['username'].strip()
        qs = User.objects.filter(username__iexact=username)
        if self.instance and self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError('Ya existe un usuario con ese nombre.')
        return username

    def clean_email(self):
        email = self.cleaned_data['email'].strip().lower()
        qs = User.objects.filter(email__iexact=email)
        if self.instance and self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError('Ya existe un usuario con ese correo.')
        return email

    def clean(self):
        cleaned_data = super().clean()
        password1 = cleaned_data.get('password1')
        password2 = cleaned_data.get('password2')

        if not self.instance.pk:
            if not password1 or not password2:
                raise forms.ValidationError('Debes ingresar y confirmar la contraseña.')

        if password1 or password2:
            if password1 != password2:
                raise forms.ValidationError('Las contraseñas no coinciden.')

        return cleaned_data

    def save(self, commit=True):
        user = super().save(commit=False)

        password1 = self.cleaned_data.get('password1')
        if password1:
            user.set_password(password1)

        rol = self.cleaned_data.get('rol', 'cliente')
        user.is_staff = rol in ['superuser', 'staff']
        user.is_superuser = rol == 'superuser'

        if commit:
            user.save()
            perfil, _ = Perfil.objects.get_or_create(user=user)
            perfil.rol = rol
            perfil.save()

        return user