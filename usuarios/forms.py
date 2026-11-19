from django import forms
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError

from .models import Usuario


class CrearUsuarioForm(forms.Form):
    ROLES = [
        ('Cajero', 'Cajero'),
        ('Administrador', 'Administrador'),
    ]

    nombre = forms.CharField(
        label='Nombre completo',
        min_length=3,
        max_length=100,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Ej: Ana Pérez',
            'autocomplete': 'off',
        }),
    )

    correo = forms.EmailField(
        label='Correo electrónico',
        max_length=150,
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'ana@jetsur.com',
            'autocomplete': 'off',
        }),
    )

    rol = forms.ChoiceField(
        label='Rol',
        choices=ROLES,
        widget=forms.Select(attrs={'class': 'form-control select-control'}),
    )

    password = forms.CharField(
        label='Contraseña',
        min_length=8,
        max_length=128,
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'id': 'id_password',
            'placeholder': 'Mínimo 8 caracteres',
            'autocomplete': 'new-password',
        }),
    )

    password2 = forms.CharField(
        label='Confirmar contraseña',
        min_length=8,
        max_length=128,
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'id': 'id_password2',
            'placeholder': 'Repite la contraseña',
            'autocomplete': 'new-password',
        }),
    )

    def clean_correo(self):
        correo = self.cleaned_data['correo'].strip().lower()

        if Usuario.objects.filter(correo__iexact=correo).exists():
            raise ValidationError('Ya existe un usuario con este correo.')

        return correo

    def clean_password(self):
        password = self.cleaned_data['password']

        try:
            validate_password(password)
        except ValidationError as error:
            raise ValidationError(error.messages)

        return password

    def clean(self):
        datos = super().clean()
        password = datos.get('password')
        password2 = datos.get('password2')

        if password and password2 and password != password2:
            self.add_error('password2', 'Las contraseñas no coinciden.')

        return datos