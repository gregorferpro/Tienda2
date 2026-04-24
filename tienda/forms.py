from django import forms
from .models import (
    Cliente, Producto, Proveedor, CompraProveedor,
    ReclamoProveedor, DevolucionProveedor
)


class ProductoForm(forms.ModelForm):
    class Meta:
        model = Producto
        fields = [
            'codigo', 'nombre', 'marca', 'modelo',
            'tipo_producto', 'categoria', 'descripcion',
            'precio', 'costo_referencia', 'stock', 'activo'
        ]
        widgets = {
            'codigo': forms.TextInput(attrs={'class': 'form-control'}),
            'nombre': forms.TextInput(attrs={'class': 'form-control'}),
            'marca': forms.TextInput(attrs={'class': 'form-control'}),
            'modelo': forms.TextInput(attrs={'class': 'form-control'}),
            'tipo_producto': forms.Select(attrs={'class': 'form-control'}),
            'categoria': forms.TextInput(attrs={'class': 'form-control'}),
            'descripcion': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
            'precio': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'costo_referencia': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'stock': forms.NumberInput(attrs={'class': 'form-control'}),
            'activo': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class ProductoCatalogoForm(forms.ModelForm):
    class Meta:
        model = Producto
        fields = ['descripcion', 'precio', 'activo']
        widgets = {
            'descripcion': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
            'precio': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'activo': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class ClienteForm(forms.ModelForm):
    class Meta:
        model = Cliente
        fields = ['nombres', 'apellidos', 'ci_nit', 'telefono', 'email', 'direccion', 'estado']
        widgets = {
            'nombres': forms.TextInput(attrs={'class': 'form-control'}),
            'apellidos': forms.TextInput(attrs={'class': 'form-control'}),
            'ci_nit': forms.TextInput(attrs={'class': 'form-control'}),
            'telefono': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'direccion': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'estado': forms.TextInput(attrs={'class': 'form-control'}),
        }


class CheckoutForm(forms.Form):
    nombres = forms.CharField(widget=forms.TextInput(attrs={'class': 'form-control'}))
    apellidos = forms.CharField(widget=forms.TextInput(attrs={'class': 'form-control'}))
    ci_nit = forms.CharField(widget=forms.TextInput(attrs={'class': 'form-control'}))
    telefono = forms.CharField(widget=forms.TextInput(attrs={'class': 'form-control'}))
    email = forms.EmailField(required=False, widget=forms.EmailInput(attrs={'class': 'form-control'}))
    direccion = forms.CharField(required=False, widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 3}))
    metodo_pago = forms.ChoiceField(
        choices=[('efectivo', 'Efectivo'), ('qr', 'QR')],
        widget=forms.Select(attrs={'class': 'form-control'})
    )


class ProveedorForm(forms.ModelForm):
    class Meta:
        model = Proveedor
        fields = [
            'tipo_proveedor', 'nombre', 'razon_social', 'nombre_comercial',
            'documento_ref', 'nit', 'telefono', 'email',
            'direccion', 'contacto', 'observaciones', 'estado'
        ]
        widgets = {
            'tipo_proveedor': forms.Select(attrs={'class': 'form-control'}),
            'nombre': forms.TextInput(attrs={'class': 'form-control'}),
            'razon_social': forms.TextInput(attrs={'class': 'form-control'}),
            'nombre_comercial': forms.TextInput(attrs={'class': 'form-control'}),
            'documento_ref': forms.TextInput(attrs={'class': 'form-control'}),
            'nit': forms.TextInput(attrs={'class': 'form-control'}),
            'telefono': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'direccion': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'contacto': forms.TextInput(attrs={'class': 'form-control'}),
            'observaciones': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'estado': forms.Select(attrs={'class': 'form-control'}),
        }

    def clean(self):
        cleaned = super().clean()
        nombre = (cleaned.get('nombre') or '').strip()
        razon_social = (cleaned.get('razon_social') or '').strip()
        tipo = cleaned.get('tipo_proveedor')

        if tipo == 'EMPRESA' and not (razon_social or nombre):
            raise forms.ValidationError('Para empresa debes ingresar nombre o razón social.')
        if tipo == 'PERSONA' and not nombre:
            raise forms.ValidationError('Para persona debes ingresar el nombre.')
        return cleaned


class CompraProveedorForm(forms.ModelForm):
    class Meta:
        model = CompraProveedor
        fields = [
            'proveedor', 'fecha_compra', 'tipo_documento',
            'numero_documento', 'referencia_libre',
            'descuento', 'observaciones', 'estado'
        ]
        widgets = {
            'proveedor': forms.Select(attrs={'class': 'form-control'}),
            'fecha_compra': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'tipo_documento': forms.Select(attrs={'class': 'form-control'}),
            'numero_documento': forms.TextInput(attrs={'class': 'form-control'}),
            'referencia_libre': forms.TextInput(attrs={'class': 'form-control'}),
            'descuento': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'observaciones': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'estado': forms.Select(attrs={'class': 'form-control'}),
        }

    def clean_proveedor(self):
        proveedor = self.cleaned_data['proveedor']
        if proveedor.estado == 'inactivo':
            raise forms.ValidationError('No puedes registrar compras con un proveedor inactivo.')
        return proveedor


class ReclamoProveedorForm(forms.ModelForm):
    class Meta:
        model = ReclamoProveedor
        fields = ['proveedor', 'compra', 'producto', 'cantidad', 'motivo', 'observaciones', 'estado', 'fecha_reclamo']
        widgets = {
            'proveedor': forms.Select(attrs={'class': 'form-control'}),
            'compra': forms.Select(attrs={'class': 'form-control'}),
            'producto': forms.Select(attrs={'class': 'form-control'}),
            'cantidad': forms.NumberInput(attrs={'class': 'form-control'}),
            'motivo': forms.TextInput(attrs={'class': 'form-control'}),
            'observaciones': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'estado': forms.Select(attrs={'class': 'form-control'}),
            'fecha_reclamo': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
        }


class DevolucionProveedorForm(forms.ModelForm):
    class Meta:
        model = DevolucionProveedor
        fields = ['motivo', 'estado', 'fecha_devolucion']
        widgets = {
            'motivo': forms.TextInput(attrs={'class': 'form-control'}),
            'estado': forms.Select(attrs={'class': 'form-control'}),
            'fecha_devolucion': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
        }
