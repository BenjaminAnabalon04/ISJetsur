from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _


class PasswordSeguraValidator:
    """
    Exige mínimo 8 caracteres, una mayúscula, una minúscula,
    un número y un símbolo.
    """

    SIMBOLOS = set("!@#$%^&*()_+-=[]{};':\",.<>/?\\|`~")

    def validate(self, password, user=None):
        errores = []

        if len(password) < 8:
            errores.append(_('La contraseña debe tener al menos 8 caracteres.'))

        if not any(caracter.isupper() for caracter in password):
            errores.append(_('Debe incluir al menos una letra mayúscula.'))

        if not any(caracter.islower() for caracter in password):
            errores.append(_('Debe incluir al menos una letra minúscula.'))

        if not any(caracter.isdigit() for caracter in password):
            errores.append(_('Debe incluir al menos un número.'))

        if not any(caracter in self.SIMBOLOS for caracter in password):
            errores.append(
                _('Debe incluir al menos un símbolo, por ejemplo: ! @ # $ %')
            )

        if errores:
            raise ValidationError(errores)

    def get_help_text(self):
        return _(
            'Mínimo 8 caracteres, con al menos una mayúscula, una minúscula, '
            'un número y un símbolo.'
        )