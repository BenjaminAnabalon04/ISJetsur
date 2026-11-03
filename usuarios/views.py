from django.shortcuts import render, redirect
from django.contrib.auth.hashers import check_password
from .models import Usuario


def usuarios(request):
    if request.method == 'POST':
        correo_form = request.POST.get('correo')
        password_form = request.POST.get('password')

        try:
            user = Usuario.objects.get(correo=correo_form)

            if check_password(password_form, user.clave_hash):
                # Renovamos la sesión para evitar fijación de sesión
                request.session.flush()
                request.session['usuario_id'] = user.id_usuario
                request.session['rol'] = user.rol
                request.session['nombre'] = user.nombre
                return redirect('usuarios:dashboard')
            else:
                return render(request, 'usuarios/login.html', {
                    'error': 'Contraseña incorrecta',
                    'correo': correo_form,
                })

        except Usuario.DoesNotExist:
            return render(request, 'usuarios/login.html', {
                'error': 'El correo no está registrado',
                'correo': correo_form,
            })

    return render(request, 'usuarios/login.html')


def dashboard(request):
    # Sin sesión no se puede entrar al panel
    if not request.session.get('usuario_id'):
        return redirect('usuarios:usuarios')

    # Por ahora solo se renderiza la interfaz: los KPIs y tablas
    # se llenarán cuando exista la capa de datos (services.py).
    return render(request, 'usuarios/dashboard.html', {'activo': 'dashboard'})


def logout_view(request):
    request.session.flush()
    return redirect('usuarios:usuarios')
