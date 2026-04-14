from django import forms
from .models import Producto, Cliente

class ProductoForm(forms.ModelForm):
    class Meta:
        model = Producto
        fields = [
            'codigo',
            'nombre',
            'marca',
            'modelo',
            'descripcion',
            'precio',
            'stock',
            'activo',
        ]


class ClienteForm(forms.ModelForm):
    class Meta:
        model = Cliente
        fields = [
            'nombres',
            'apellidos',
            'ci_nit',
            'telefono',
            'email',
            'direccion',
            'estado',
        ]




class ProductoForm(forms.ModelForm):
    class Meta:
        model = Producto
        fields = [
            'codigo',
            'nombre',
            'marca',
            'modelo',
            'descripcion',
            'precio',
            'stock',
            'activo',
        ]


class ClienteForm(forms.ModelForm):
    class Meta:
        model = Cliente
        fields = [
            'nombres',
            'apellidos',
            'ci_nit',
            'telefono',
            'email',
            'direccion',
            'estado',
        ]


class CheckoutForm(forms.Form):
    nombres = forms.CharField(
        max_length=100,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Ingresa tus nombres'
        })
    )
    apellidos = forms.CharField(
        max_length=100,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Ingresa tus apellidos'
        })
    )
    ci_nit = forms.CharField(
        max_length=30,
        label='NIT/CI/CEX',
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Ej. 1234567'
        })
    )
    telefono = forms.CharField(
        max_length=30,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Ej. 70000000'
        })
    )
    email = forms.EmailField(
        required=False,
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'correo@ejemplo.com'
        })
    )
    direccion = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'placeholder': 'Ingresa tu dirección completa',
            'rows': 4
        })
    )
    metodo_pago = forms.ChoiceField(
        choices=[
            ('efectivo', 'Efectivo'),
            ('qr', 'QR')
        ],
        widget=forms.Select(attrs={
            'class': 'form-select'
        })
    )
    confirmar_pago_qr = forms.BooleanField(
        required=False,
        label='Confirmo que realicé el pago por QR',
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input'
        })
    )

    def clean(self):
        cleaned = super().clean()
        metodo_pago = cleaned.get('metodo_pago')
        confirmar_pago_qr = cleaned.get('confirmar_pago_qr')

        if metodo_pago == 'qr' and not confirmar_pago_qr:
            self.add_error('confirmar_pago_qr', 'Debes confirmar el pago por QR.')

        return cleaned