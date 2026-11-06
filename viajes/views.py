from functools import wraps
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from . import services
from .forms import CobroForm, ReservaForm
from .models import Reserva, Ticket, Venta, Viaje


def sesion_requerida(vista):
    @wraps(vista)
    def envoltura(request, *args, **kwargs):
        if not request.session.get('usuario_id'):
            return redirect('usuarios:usuarios')
        return vista(request, *args, **kwargs)
    return envoltura


@sesion_requerida
@sesion_requerida
def lista(request):
    origen = request.GET.get('origen', 'Santiago').strip()
    destino = request.GET.get('destino', 'Chillán').strip()
    fecha = request.GET.get('fecha', '').strip()
    viajes = services.buscar_viajes(origen, destino, fecha)
    cupos = services.cupos_por_viaje(viajes)
    for viaje in viajes:
        viaje.cupos = cupos.get(viaje.id_viaje, services.TOTAL_ASIENTOS)
    origenes = list(
        Viaje.objects.order_by('origen').values_list('origen', flat=True).distinct()
    )
    destinos = list(
        Viaje.objects.order_by('destino').values_list('destino', flat=True).distinct()
    )
    return render(request, 'viajes/lista.html', {
        'activo': 'viajes',
        'viajes': viajes,
        'origen': origen,
        'destino': destino,
        'fecha': fecha,
        'origenes': origenes,
        'destinos': destinos,
    })
@sesion_requerida
def asientos(request, id_viaje):
    viaje = get_object_or_404(Viaje, pk=id_viaje)
    ocupados = services.asientos_ocupados(viaje)
    filas = [
        list(range(inicio, min(inicio + 4, services.TOTAL_ASIENTOS + 1)))
        for inicio in range(1, services.TOTAL_ASIENTOS + 1, 4)
    ]
    vendible = viaje.estado == 'programado' and viaje.salida > timezone.now()
    return render(request, 'viajes/asientos.html', {
        'activo': 'viajes',
        'viaje': viaje,
        'ocupados': ocupados,
        'filas': filas,
        'vendible': vendible,
    })


@sesion_requerida
def reservar(request, id_viaje):
    if request.method != 'POST':
        return redirect('viajes:asientos', id_viaje=id_viaje)

    formulario = ReservaForm(request.POST)
    if not formulario.is_valid():
        messages.error(request, 'Revisa los datos: asiento, RUT, nombre y teléfono.')
        return redirect('viajes:asientos', id_viaje=id_viaje)
    try:
        reserva = services.crear_reserva(
            id_viaje=id_viaje,
            numero_asiento=formulario.cleaned_data['numero_asiento'],
            nombre=formulario.cleaned_data['nombre_pasajero'],
            rut=formulario.cleaned_data['rut_pasajero'],
            telefono=formulario.cleaned_data['telefono'],
            id_usuario=request.session['usuario_id'],
        )
    except services.VentaError as error:
        messages.error(request, str(error))
        return redirect('viajes:asientos', id_viaje=id_viaje)

    messages.success(request, f'Reserva #{reserva.id_reserva} creada. Falta el pago.')
    return redirect('viajes:cobrar', id_reserva=reserva.id_reserva)


@sesion_requerida
def cobrar(request, id_reserva):
    reserva = get_object_or_404(
        Reserva.objects.select_related('id_viaje'), pk=id_reserva
    )
    if reserva.estado == 'confirmada':
        ticket = Ticket.objects.filter(id_reserva=reserva).first()
        if ticket:
            return redirect('viajes:ticket', codigo=ticket.codigo)

    if request.method == 'POST':
        formulario = CobroForm(request.POST)
        if not formulario.is_valid():
            messages.error(request, 'Elige un medio de pago.')
            return redirect('viajes:cobrar', id_reserva=reserva.id_reserva)

        try:
            ticket = services.cobrar_reserva(
                id_reserva=reserva.id_reserva,
                medio=formulario.cleaned_data['medio'],
                id_usuario=request.session['usuario_id'],
            )
        except services.VentaError as error:
            messages.error(request, str(error))
            return redirect('viajes:cobrar', id_reserva=reserva.id_reserva)

        return redirect('viajes:ticket', codigo=ticket.codigo)

    return render(request, 'viajes/cobrar.html', {
        'activo': 'viajes',
        'reserva': reserva,
        'viaje': reserva.id_viaje,
    })


@sesion_requerida
def ticket(request, codigo):
    boleto = get_object_or_404(
        Ticket.objects.select_related('id_reserva__id_viaje'), codigo=codigo
    )
    venta = Venta.objects.filter(id_ticket=boleto).first()

    return render(request, 'viajes/ticket.html', {
        'ticket': boleto,
        'reserva': boleto.id_reserva,
        'viaje': boleto.id_reserva.id_viaje,
        'venta': venta,
    })
@sesion_requerida
def cancelar(request, id_reserva):
    if request.method != 'POST':
        return redirect('viajes:lista')

    reserva = get_object_or_404(Reserva, pk=id_reserva)
    id_viaje = reserva.id_viaje_id

    try:
        services.cancelar_reserva(id_reserva)
    except services.VentaError as error:
        messages.error(request, str(error))
        return redirect('viajes:cobrar', id_reserva=id_reserva)

    messages.success(
        request,
        f'Reserva #{id_reserva} cancelada. El asiento quedó libre.'
    )
    return redirect('viajes:asientos', id_viaje=id_viaje)