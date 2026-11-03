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
                request.session['usuario_id'] = user.id_usuario
                request.session['rol'] = user.rol
                if user.rol.lower() == 'administrador':
                    return redirect('Cambiar ruta dashboard') 
                else:
                    return redirect('Cambiar ruta dashboard') 
            else:
                return render(request, 'usuarios/login.html', {'error': 'Contraseña incorrecta', 'correo': correo_form})
        
        except Usuario.DoesNotExist:
            return render(request, 'usuarios/login.html', {'error': 'El correo no está registrado', 'correo': correo_form})

    return render(request, 'usuarios/login.html')