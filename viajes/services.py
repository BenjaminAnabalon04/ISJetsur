import uuid

from django.db import IntegrityError, connection, transaction
from django.db.models import Count
from django.utils import timezone
from django.utils.dateparse import parse_date

from datetime import timedelta
from decimal import Decimal, ROUND_HALF_UP

from .models import Devolucion, Reserva, Ticket, Venta, Viaje

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
# Expiración automática de reservas pendientes
# ----------------------------------------------------------------------
# TIEMPO SUPUESTO: confirmar con el profesor cuántos minutos corresponde.
MINUTOS_RESERVA = 10


def vence_reserva(reserva):
    return reserva.fecha_reserva + timedelta(minutes=MINUTOS_RESERVA)


def expirar_reservas():
    """Libera los asientos de reservas pendientes que pasaron el tiempo límite."""
    limite = timezone.now() - timedelta(minutes=MINUTOS_RESERVA)
    return (
        Reserva.objects
        .filter(estado='pendiente', activa=1, fecha_reserva__lt=limite)
        .update(estado='expirada', activa=None)
    )


def marcar_viajes_salidos():
    """Marca como 'finalizado' los viajes programados cuya salida ya pasó."""
    return (
        Viaje.objects
        .filter(estado='programado', salida__lt=timezone.now())
        .update(estado='finalizado')
    )


# ----------------------------------------------------------------------
# Reserva
# ----------------------------------------------------------------------
def crear_reserva(id_viaje, numero_asiento, nombre,rut, telefono, id_usuario):
    expirar_reservas()
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

    expirar_reservas()

    with transaction.atomic():
        reserva = (
            Reserva.objects
            .select_for_update()
            .select_related('id_viaje')
            .get(pk=id_reserva)
        )

        if reserva.estado == 'expirada':
            raise VentaError('La reserva expiró por falta de pago y el asiento fue liberado.')
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


# ----------------------------------------------------------------------
# Viajes nuevos (solo administrador)
# ----------------------------------------------------------------------
def crear_viaje(origen, destino, salida, tarifa):
    origen = (origen or '').strip().title()
    destino = (destino or '').strip().title()

    if origen.lower() == destino.lower():
        raise VentaError('El origen y el destino no pueden ser iguales.')
    if salida <= timezone.now():
        raise VentaError('La fecha de salida debe ser futura.')
    if tarifa <= 0:
        raise VentaError('La tarifa debe ser mayor a 0.')
    if Viaje.objects.filter(origen=origen, destino=destino, salida=salida).exists():
        raise VentaError('Ya existe un viaje con ese origen, destino y salida.')

    with transaction.atomic():
        viaje = Viaje.objects.create(
            origen=origen, destino=destino, salida=salida,
            tarifa=tarifa, estado='programado',
        )
        crear_asientos(viaje.id_viaje)   # los 30 asientos del viaje
        return viaje


# ----------------------------------------------------------------------
# Devoluciones
# ----------------------------------------------------------------------
# Se devuelve el 85 % del monto si se avisa con al menos 2 horas de
# anticipación; con menos tiempo no corresponde devolución.
HORAS_MINIMAS_DEVOLUCION = 2
PORCENTAJE_DEVOLUCION = Decimal('85')


def porcentaje_devolucion(salida):
    """85 % si faltan 2 horas o más para la salida; 0 % si falta menos."""
    horas = (salida - timezone.now()) / timedelta(hours=1)
    if horas >= HORAS_MINIMAS_DEVOLUCION:
        return PORCENTAJE_DEVOLUCION
    return Decimal('0')


def datos_devolucion(codigo):
    """Todo lo necesario para mostrar/confirmar la devolución de un ticket."""
    ticket = (
        Ticket.objects.select_related('id_reserva__id_viaje')
        .filter(codigo=codigo.strip().upper()).first()
    )
    if not ticket:
        raise VentaError('No existe un ticket con ese código.')

    venta = Venta.objects.filter(id_ticket=ticket).first()
    if not venta:
        raise VentaError('Este ticket no tiene una venta asociada.')
    if Devolucion.objects.filter(id_venta=venta).exists():
        raise VentaError('Este ticket ya fue devuelto.')

    reserva = ticket.id_reserva
    viaje = reserva.id_viaje
    if reserva.estado != 'confirmada':
        raise VentaError('Solo se pueden devolver reservas confirmadas.')
    if viaje.salida <= timezone.now():
        raise VentaError('El viaje ya salió: no se puede devolver.')

    porcentaje = porcentaje_devolucion(viaje.salida)
    if porcentaje <= 0:
        raise VentaError('Faltan menos de 2 horas para la salida: no corresponde devolución.')

    monto = (venta.monto * porcentaje / 100).quantize(Decimal('1'), ROUND_HALF_UP)
    return {'ticket': ticket, 'venta': venta, 'reserva': reserva, 'viaje': viaje,
            'porcentaje': porcentaje, 'monto': monto}


def registrar_devolucion(codigo, id_usuario):
    with transaction.atomic():
        datos = datos_devolucion(codigo)
        reserva = Reserva.objects.select_for_update().get(pk=datos['reserva'].pk)
        if reserva.estado != 'confirmada':
            raise VentaError('Solo se pueden devolver reservas confirmadas.')

        try:
            devolucion = Devolucion.objects.create(
                monto=datos['monto'],
                porcentaje=datos['porcentaje'],
                medio=datos['venta'].medio,
                id_venta=datos['venta'],
                id_usuario_id=id_usuario,
            )
        except IntegrityError:
            raise VentaError('Este ticket ya fue devuelto.')

        reserva.estado = 'cancelada'
        reserva.activa = None            # libera el asiento
        reserva.save(update_fields=['estado', 'activa'])
        return devolucion

def viajes_para_cambio(reserva):
    """Viajes programados, futuros y de igual tarifa (incluye el actual)."""
    return list(
        Viaje.objects.filter(
            estado='programado',
            salida__gt=timezone.now(),
            tarifa=reserva.id_viaje.tarifa,
        ).order_by('salida')
    )


def cambiar_reserva(id_reserva, id_viaje_nuevo, numero_asiento):

    expirar_reservas()

    if numero_asiento < 1 or numero_asiento > TOTAL_ASIENTOS:
        raise VentaError('El asiento debe estar entre 1 y 30.')

    try:
        with transaction.atomic():
            reserva = (
                Reserva.objects
                .select_for_update()
                .select_related('id_viaje')
                .get(pk=id_reserva)
            )
            if reserva.estado not in ('pendiente', 'confirmada'):
                raise VentaError('Solo se pueden cambiar reservas pendientes o confirmadas.')

            actual = reserva.id_viaje
            if actual.salida <= timezone.now():
                raise VentaError('El viaje original ya salió: no se puede cambiar.')

            try:
                nuevo = Viaje.objects.select_for_update().get(pk=id_viaje_nuevo)
            except Viaje.DoesNotExist:
                raise VentaError('El viaje elegido no existe.')

            if nuevo.estado != 'programado' or nuevo.salida <= timezone.now():
                raise VentaError('El viaje elegido no está disponible para la venta.')
            if nuevo.tarifa != actual.tarifa:
                raise VentaError('Solo se puede cambiar a un viaje de igual valor.')
            if nuevo.pk == actual.pk and numero_asiento == reserva.numero_asiento:
                raise VentaError('Elige un asiento o un viaje distinto al actual.')

            ocupado = Reserva.objects.filter(
                id_viaje=nuevo, numero_asiento=numero_asiento, activa=1
            ).exists()
            if ocupado:
                raise VentaError('Ese asiento ya está ocupado. Se conservó la reserva original.')

            reserva.id_viaje = nuevo
            reserva.numero_asiento = numero_asiento
            reserva.save(update_fields=['id_viaje', 'numero_asiento'])
            return reserva
    except IntegrityError:
  
        raise VentaError('Ese asiento ya está ocupado. Se conservó la reserva original.')