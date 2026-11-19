from django.db import models


class Usuario(models.Model):
    ESTADO_ACTIVA = 'activa'
    ESTADO_BLOQUEADA = 'bloqueada'

    id_usuario = models.AutoField(primary_key=True)
    nombre = models.CharField(max_length=100)
    correo = models.CharField(unique=True, max_length=150)
    clave_hash = models.CharField(max_length=255)
    rol = models.CharField(max_length=13)
    estado = models.CharField(max_length=10, default=ESTADO_ACTIVA)

    class Meta:
        managed = False
        db_table = 'usuario'

    @property
    def esta_bloqueada(self):
        return self.estado == self.ESTADO_BLOQUEADA

    class Meta:
        managed = False
        db_table = 'usuario'
