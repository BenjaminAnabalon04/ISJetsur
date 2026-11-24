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


class EditarUsuarioForm(forms.Form):
    ROLES = CrearUsuarioForm.ROLES

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

    # En edición la contraseña es opcional: en blanco conserva la actual.
    password = forms.CharField(
        label='Nueva contraseña',
        required=False,
        min_length=8,
        max_length=128,
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'id': 'id_password',
            'placeholder': 'Déjala en blanco para conservar la actual',
            'autocomplete': 'new-password',
        }),
    )

    password2 = forms.CharField(
        label='Confirmar nueva contraseña',
        required=False,
        min_length=8,
        max_length=128,
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'id': 'id_password2',
            'placeholder': 'Repite la nueva contraseña',
            'autocomplete': 'new-password',
        }),
    )

    def __init__(self, *args, usuario=None, bloquear_rol=False, **kwargs):
        self.usuario = usuario
        self.bloquear_rol = bloquear_rol
        super().__init__(*args, **kwargs)

        # Con el campo deshabilitado Django usa el valor inicial e ignora
        # lo que llegue por POST.
        if bloquear_rol and usuario is not None:
            self.fields['rol'].disabled = True
            self.initial['rol'] = usuario.rol

    def clean_correo(self):
        correo = self.cleaned_data['correo'].strip().lower()

        existentes = Usuario.objects.filter(correo__iexact=correo)
        if self.usuario is not None:
            existentes = existentes.exclude(pk=self.usuario.pk)

        if existentes.exists():
            raise ValidationError('Ya existe un usuario con este correo.')

        return correo

    def clean_password(self):
        password = self.cleaned_data.get('password')

        if password:
            try:
                validate_password(password)
            except ValidationError as error:
                raise ValidationError(error.messages)

        return password

    def clean(self):
        datos = super().clean()
        password = datos.get('password')
        password2 = datos.get('password2')

        if password and password != password2:
            self.add_error('password2', 'Las contraseñas no coinciden.')

        return datos