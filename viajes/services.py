import uuid

from django.db import IntegrityError, connection, transaction
from django.db.models import Count
from django.utils import timezone
from django.utils.dateparse import parse_date

from .models import Reserva, Ticket, Venta, Viaje

TOTAL_ASIENTOS = 30


class VentaError(Exception):
    """Error de negocio: el mensaje se le muestra tal cual al usuario."""
    pass


# ----------------------------------------------------------------------
# Asientos
# ----------------------------------------------------------------------
def crear_asientos(id_viaje, total=TOTAL_ASIENTOS):
    """Inserta los 30 asientos del viaje con SQL directo."""
    with connection.cursor() as cursor:
        cursor.executemany(
            'INSERT INTO asiento_viaje (id_viaje, numero) VALUES (%s, %s)',
            [(id_viaje, numero) for numero in range(1, total + 1)],
        )


def asientos_ocupados(viaje):
    """Devuelve el conjunto de números de asiento ocupados."""
    return set(
        Reserva.objects
        .filter(id_viaje=viaje, activa=1)
        .values_list('numero_asiento', flat=True)
    )


# ----------------------------------------------------------------------
# Búsqueda
# ----------------------------------------------------------------------
def buscar_viajes(origen=None, destino=None, fecha=None):
    consulta = Viaje.objects.filter(estado='programado', salida__gte=timezone.now())

    if origen:
        consulta = consulta.filter(origen__icontains=origen)
    if destino:
        consulta = consulta.filter(destino__icontains=destino)
    if fecha:
        dia = parse_date(fecha)
        if dia:
            consulta = consulta.filter(salida__date=dia)

    return list(consulta.order_by('salida'))


def cupos_por_viaje(viajes):
    """Una sola consulta para todos los viajes: {id_viaje: cupos_libres}."""
    ids = [viaje.id_viaje for viaje in viajes]
    if not ids:
        return {}

    filas = (
        Reserva.objects
        .filter(id_viaje__in=ids, activa=1)
        .values('id_viaje')
        .annotate(total=Count('id_reserva'))
    )
    ocupados = {fila['id_viaje']: fila['total'] for fila in filas}

    return {
        viaje.id_viaje: TOTAL_ASIENTOS - ocupados.get(viaje.id_viaje, 0)
        for viaje in viajes
    }


# ----------------------------------------------------------------------
# Reserva
# ----------------------------------------------------------------------
def crear_reserva(id_viaje, numero_asiento, nombre,rut, telefono, id_usuario):
    nombre = (nombre or '').strip()
    telefono = (telefono or '').strip()
    rut_formateado = normalizar_rut(rut)
    digitos = sum(1 for caracter in telefono if caracter.isdigit())

    if len(nombre) < 3:
        raise VentaError('Escribe el nombre del pasajero (mínimo 3 letras).')
    if digitos < 8:
        raise VentaError('Escribe un teléfono válido (mínimo 8 dígitos).')
    if numero_asiento < 1 or numero_asiento > TOTAL_ASIENTOS:
        raise VentaError('El asiento debe estar entre 1 y 30.')
    
    try:
        with transaction.atomic():
            # Bloquea el viaje para que dos cajeros no reserven a la vez
            viaje = Viaje.objects.select_for_update().get(pk=id_viaje)
            
            if viaje.estado != 'programado':
                raise VentaError('Este viaje no está disponible para la venta.')
            if viaje.salida <= timezone.now():
                raise VentaError('Este viaje ya salió.')
            

            ya_ocupado = Reserva.objects.filter(
                id_viaje=viaje, numero_asiento=numero_asiento, activa=1
            ).exists()
            if ya_ocupado:
                raise VentaError('Ese asiento ya está ocupado.')

            return Reserva.objects.create(
                id_viaje=viaje,
                id_usuario_id=id_usuario,
                numero_asiento=numero_asiento,
                rut_pasajero=rut_formateado,
                nombre_pasajero=nombre,
                telefono=telefono,
                estado='pendiente',
                activa=1,
            )
    except IntegrityError:
        # El índice único nos salvó de una doble venta
        raise VentaError('Ese asiento ya está ocupado.')


# ----------------------------------------------------------------------
# Cobro
# ----------------------------------------------------------------------
def generar_codigo():
    return 'JTS-' + uuid.uuid4().hex[:6].upper()


def cobrar_reserva(id_reserva, medio, id_usuario):
    if medio not in ('efectivo', 'tarjeta'):
        raise VentaError('Medio de pago no válido.')

    with transaction.atomic():
        reserva = (
            Reserva.objects
            .select_for_update()
            .select_related('id_viaje')
            .get(pk=id_reserva)
        )

        if reserva.estado != 'pendiente':
            raise VentaError('Esta reserva ya fue cobrada o cancelada.')

        ya_vendida = Venta.objects.filter(id_ticket__id_reserva=reserva).exists()
        if ya_vendida:
            raise VentaError('Esta reserva ya tiene una venta registrada.')

        codigo = generar_codigo()
        while Ticket.objects.filter(codigo=codigo).exists():
            codigo = generar_codigo()

        ticket = Ticket.objects.create(codigo=codigo, id_reserva=reserva)

        Venta.objects.create(
            monto=reserva.id_viaje.tarifa,
            medio=medio,
            id_ticket=ticket,
            id_usuario_id=id_usuario,
        )

        reserva.estado = 'confirmada'
        reserva.save(update_fields=['estado'])

        return ticket
def normalizar_rut(rut):
    limpio = (
        (rut or '')
        .replace('.', '')
        .replace('-', '')
        .replace(' ', '')
        .strip()
        .upper()
    )

    if len(limpio) < 8:
        raise VentaError('El RUT está incompleto.')
    if len(limpio) > 9:
        raise VentaError(
            'El RUT tiene demasiados dígitos. Ejemplo válido: 12.345.678-5.'
        )

    cuerpo, dv = limpio[:-1], limpio[-1]

    if not cuerpo.isdigit():
        raise VentaError('El RUT debe tener solo números antes del guion.')
    if not dv.isdigit() and dv != 'K':
        raise VentaError('El dígito verificador del RUT no es válido.')

    suma, multiplo = 0, 2
    for digito in reversed(cuerpo):
        suma += int(digito) * multiplo
        multiplo = 2 if multiplo == 7 else multiplo + 1

    resto = suma % 11
    calculado = 11 - resto
    if calculado == 11:
        esperado = '0'
    elif calculado == 10:
        esperado = 'K'
    else:
        esperado = str(calculado)

    if dv != esperado:
        raise VentaError('El RUT no es válido. Revisa el dígito verificador.')

    return f'{int(cuerpo):,}'.replace(',', '.') + '-' + dv

def cancelar_reserva(id_reserva):
    with transaction.atomic():
        reserva = Reserva.objects.select_for_update().get(pk=id_reserva)

        if reserva.estado != 'pendiente':
            raise VentaError('Solo se pueden cancelar reservas pendientes.')

        reserva.estado = 'cancelada'
        reserva.activa = None
        reserva.save(update_fields=['estado', 'activa'])

        return reserva