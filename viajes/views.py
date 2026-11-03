from django.shortcuts import render, redirect


def lista(request):
    # El panel es interno: exige sesión iniciada
    if not request.session.get('usuario_id'):
        return redirect('usuarios:usuarios')

    # Maqueta: todavía no se consulta la base de datos.
    # Cuando exista la capa de datos, aquí se cargarán los viajes
    # según origen, destino, fecha y filtros.
    viajes = []

    return render(request, 'viajes/lista.html', {
        'activo': 'viajes',
        'viajes': viajes,
    })
