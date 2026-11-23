from functools import wraps
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from . import services
from .forms import CobroForm, ReservaForm, ViajeForm
from .models import Devolucion, Reserva, Ticket, Venta, Viaje


def sesion_requerida(vista):
    @wraps(vista)
    def envoltura(request, *args, **kwargs):
        if not request.session.get('usuario_id'):
            return redirect('usuarios:usuarios')
        return vista(request, *args, **kwargs)
    return envoltura

def solo_admin(vista):
    @wraps(vista)
    @sesion_requerida
    def envoltura(request, *args, **kwargs):
        if request.session.get('rol') != 'Administrador':
            messages.error(request, 'Solo el administrador puede hacer esto.')
            return redirect('usuarios:dashboard')
        return vista(request, *args, **kwargs)
    return envoltura


@sesion_requerida
def lista(request):
    services.expirar_reservas()
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
    services.expirar_reservas()
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
    services.expirar_reservas()
    reserva = get_object_or_404(
        Reserva.objects.select_related('id_viaje'), pk=id_reserva
    )
    if request.method == 'GET' and reserva.estado == 'expirada':
        messages.error(request, 'La reserva expiró por falta de pago y el asiento fue liberado.')
        return redirect('viajes:asientos', id_viaje=reserva.id_viaje_id)
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
        'vence': services.vence_reserva(reserva),
        'minutos': services.MINUTOS_RESERVA,
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


# ----------------------------------------------------------------------
# Viajes nuevos (administrador)
# ----------------------------------------------------------------------
@solo_admin
def viaje_nuevo(request):
    formulario = ViajeForm(request.POST or None)
    if request.method == 'POST':
        if formulario.is_valid():
            try:
                viaje = services.crear_viaje(**formulario.cleaned_data)
            except services.VentaError as error:
                messages.error(request, str(error))
            else:
                messages.success(request, f'Viaje creado: {viaje.origen} → {viaje.destino}.')
                return redirect('viajes:lista')
        else:
            messages.error(request, 'Revisa los datos: origen, destino, fecha y tarifa.')
    return render(request, 'viajes/viaje_nuevo.html', {
        'activo': 'viajes',
        'datos': request.POST,
    })


# ----------------------------------------------------------------------
# Devoluciones
# ----------------------------------------------------------------------
@sesion_requerida
def devoluciones(request):
    codigo = request.GET.get('codigo', '').strip()
    if codigo:
        return redirect('viajes:devolver', codigo=codigo.upper())

    historial = (
        Devolucion.objects
        .select_related('id_venta__id_ticket__id_reserva__id_viaje')
        .order_by('-fecha')[:30]
    )
    return render(request, 'viajes/devoluciones.html', {
        'activo': 'devoluciones',
        'devoluciones': historial,
    })


@sesion_requerida
def devolver(request, codigo):
    try:
        datos = services.datos_devolucion(codigo)
    except services.VentaError as error:
        messages.error(request, str(error))
        return redirect('viajes:devoluciones')

    if request.method == 'POST':
        try:
            devolucion = services.registrar_devolucion(codigo, request.session['usuario_id'])
        except services.VentaError as error:
            messages.error(request, str(error))
            return redirect('viajes:devoluciones')
        messages.success(
            request,
            f'Devolución registrada: $ {devolucion.monto:.0f} ({devolucion.porcentaje:.0f}%). Asiento liberado.'
        )
        return redirect('viajes:devoluciones')

    return render(request, 'viajes/devolver.html', {'activo': 'devoluciones', **datos})
