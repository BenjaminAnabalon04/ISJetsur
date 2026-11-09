from django.shortcuts import render, redirect
from django.contrib.auth.hashers import check_password
from django.db.models import Sum
from .models import Usuario
from django.utils import timezone
from datetime import datetime, timedelta,time
from viajes import services
from viajes.models import Reserva, Ticket, Venta, Viaje


def usuarios(request):
    if request.method == 'POST':
        correo_form = request.POST.get('correo')
        password_form = request.POST.get('password')

        try:
            user = Usuario.objects.get(correo=correo_form)
            if check_password(password_form, user.clave_hash):
                request.session.flush()
                request.session['usuario_id'] = user.id_usuario
                request.session['rol'] = user.rol
                request.session['nombre'] = user.nombre
                return redirect('usuarios:dashboard')
            else:
                return render(request, 'usuarios/login.html', {
                    'error': '"Correo o contraseña incorrectos"',
                    'correo': correo_form,
                })

        except Usuario.DoesNotExist:
            return render(request, 'usuarios/login.html', {
                'error': 'El correo no está registrado',
                'correo': correo_form,
            })

    return render(request, 'usuarios/login.html')


def dashboard(request):
    if not request.session.get('usuario_id'):
        return redirect('usuarios:usuarios')
    ahora = timezone.now()
    proximos = list(
        Viaje.objects.filter(estado='programado', salida__gte=ahora)
        .order_by('salida')[:3]
    )
    cupos = services.cupos_por_viaje(proximos)
    for viaje in proximos:
        viaje.cupos = cupos.get(viaje.id_viaje, services.TOTAL_ASIENTOS)
    pendientes_qs = (
        Reserva.objects.filter(estado='pendiente', activa=1)
        .select_related('id_viaje')
        .order_by('fecha_reserva')
    )
    hoy = datetime.now().date()
    inicio = datetime.combine(hoy, time.min)
    fin = inicio + timedelta(days=1)

    ventas_hoy = Venta.objects.filter(fecha__gte=inicio, fecha__lt=fin)
    vendido = ventas_hoy.aggregate(total=Sum('monto'))['total'] or 0

    tickets = []
    for t in (
        Ticket.objects.filter(fecha_emision__gte=inicio, fecha_emision__lt=fin)
        .select_related('id_reserva__id_viaje')
        .order_by('-fecha_emision')[:5]
    ):
        venta = Venta.objects.filter(id_ticket=t).first()
        tickets.append({
            'codigo': t.codigo,
            'asiento': t.id_reserva.numero_asiento,
            'ruta': f'{t.id_reserva.id_viaje.origen} → {t.id_reserva.id_viaje.destino}',
            'monto': venta.monto if venta else 0,
            'fecha': t.fecha_emision,
        })

    return render(request, 'usuarios/dashboard.html', {
        'activo': 'dashboard',
        'proximos_viajes': proximos,
        'reservas': list(pendientes_qs[:5]),
        'tickets': tickets,
        'pendientes': pendientes_qs.count(),
        'vendido_hoy': vendido,
        'ventas_hoy': ventas_hoy.count(),
        'devuelto_hoy': 0,
        'devoluciones_hoy': 0,
        'neto_hoy': vendido,
    })

def logout_view(request):
    request.session.flush()
    return redirect('usuarios:usuarios')
