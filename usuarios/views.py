from django.shortcuts import render

def usuarios(request):
    return render(request, 'usuarios/login.html')