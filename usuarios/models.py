from django.db import models


class Usuario(models.Model):
    id_usuario = models.AutoField(primary_key=True)
    nombre = models.CharField(max_length=100)
    correo = models.CharField(unique=True, max_length=150)
    clave_hash = models.CharField(max_length=255)
    rol = models.CharField(max_length=13)

    class Meta:
        managed = False
        db_table = 'usuario'
