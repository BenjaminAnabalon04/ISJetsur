from django import forms


class ReservaForm(forms.Form):
    numero_asiento = forms.IntegerField(min_value=1, max_value=30)
    nombre_pasajero = forms.CharField(min_length=3, max_length=120)
    rut_pasajero = forms.CharField(min_length=8, max_length=12)
    telefono = forms.CharField(min_length=8, max_length=30)


class CobroForm(forms.Form):
    MEDIOS = [
        ('efectivo', 'Efectivo'),
        ('tarjeta', 'Tarjeta'),
    ]
    medio = forms.ChoiceField(choices=MEDIOS)

class ViajeForm(forms.Form):
    origen = forms.CharField(min_length=3, max_length=80)
    destino = forms.CharField(min_length=3, max_length=80)
    salida = forms.DateTimeField(input_formats=['%Y-%m-%dT%H:%M', '%Y-%m-%d %H:%M'])
    tarifa = forms.DecimalField(min_value=1, max_digits=10, decimal_places=0)
