from functools import wraps
from datetime import datetime, timedelta, time

from django.contrib import messages
from django.contrib.auth.hashers import check_password, make_password
from django.db.models import Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from viajes import services
from viajes.models import Devolucion, Reserva, Ticket, Venta, Viaje

from .forms import CrearUsuarioForm
from .models import Usuario

INTENTOS_MAXIMOS = 3


def usuarios(request):
    if request.method == 'POST':
        correo_form = request.POST.get('correo', '').strip()
        password_form = request.POST.get('password', '')
        error_generico = 'Correo o contraseña incorrectos'

        try:
            user = Usuario.objects.get(correo__iexact=correo_form)
        except Usuario.DoesNotExist:
            return render(request, 'usuarios/login.html', {
                'error': error_generico,
                'correo': correo_form,
            })

        if user.estado == Usuario.ESTADO_BLOQUEADA:
            return render(request, 'usuarios/login.html', {
                'error': 'Tu cuenta está bloqueada. Contacta a un administrador.',
                'correo': correo_form,
            })

        clave_intentos = f'intentos_{user.id_usuario}'
        intentos = request.session.get(clave_intentos, 0)

        # Si la cuenta fue desbloqueada, descartamos un contador viejo de la sesión.
        if intentos >= INTENTOS_MAXIMOS:
            intentos = 0

        if check_password(password_form, user.clave_hash):
            request.session.flush()
            request.session['usuario_id'] = user.id_usuario
            request.session['rol'] = user.rol
            request.session['nombre'] = user.nombre
            return redirect('usuarios:dashboard')

        intentos += 1
        request.session[clave_intentos] = intentos

        if intentos >= INTENTOS_MAXIMOS:
            user.estado = Usuario.ESTADO_BLOQUEADA
            user.save(update_fields=['estado'])
            request.session[clave_intentos] = 0

            return render(request, 'usuarios/login.html', {
                'error': 'Tu cuenta está bloqueada. Contacta a un administrador.',
                'correo': correo_form,
            })

        return render(request, 'usuarios/login.html', {
            'error': error_generico,
            'correo': correo_form,
        })

    return render(request, 'usuarios/login.html')


def admin_requerido(vista):
    @wraps(vista)
    def envoltura(request, *args, **kwargs):
        if not request.session.get('usuario_id'):
            return redirect('usuarios:usuarios')

        if request.session.get('rol') != 'Administrador':
            messages.error(request, 'No tienes permisos para acceder a esta sección.')
            return redirect('usuarios:dashboard')

        return vista(request, *args, **kwargs)

    return envoltura


@admin_requerido
def lista_usuarios(request):
    usuarios_lista = Usuario.objects.all().order_by('nombre')

    return render(request, 'usuarios/lista_usuarios.html', {
        'activo': 'usuarios',
        'usuarios_lista': usuarios_lista,
    })


@admin_requerido
def crear_usuario(request):
    if request.method == 'POST':
        formulario = CrearUsuarioForm(request.POST)

        if formulario.is_valid():
            Usuario.objects.create(
                nombre=formulario.cleaned_data['nombre'].strip(),
                correo=formulario.cleaned_data['correo'],
                clave_hash=make_password(formulario.cleaned_data['password']),
                rol=formulario.cleaned_data['rol'],
                estado=Usuario.ESTADO_ACTIVA,
            )
            messages.success(
                request,
                f"Usuario {formulario.cleaned_data['nombre']} creado correctamente.",
            )
            return redirect('usuarios:lista_usuarios')

        messages.error(request, 'Revisa los datos del formulario.')

    else:
        formulario = CrearUsuarioForm()

    return render(request, 'usuarios/crear_usuario.html', {
        'activo': 'usuarios',
        'formulario': formulario,
    })


@admin_requerido
def desbloquear_usuario(request, id_usuario):
    if request.method != 'POST':
        return redirect('usuarios:lista_usuarios')

    usuario = get_object_or_404(Usuario, pk=id_usuario)
    usuario.estado = Usuario.ESTADO_ACTIVA
    usuario.save(update_fields=['estado'])

    messages.success(request, f'Usuario {usuario.nombre} desbloqueado.')
    return redirect('usuarios:lista_usuarios')


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
    devs_hoy = Devolucion.objects.filter(fecha__gte=inicio, fecha__lt=fin)
    devuelto = devs_hoy.aggregate(total=Sum('monto'))['total'] or 0
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
        'devuelto_hoy': devuelto,
        'devoluciones_hoy': devs_hoy.count(),
        'neto_hoy': vendido - devuelto,
    })


def logout_view(request):
    request.session.flush()
    return redirect('usuarios:usuarios')