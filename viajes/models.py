from django.db import models


class Viaje(models.Model):
    id_viaje = models.AutoField(primary_key=True)
    origen = models.CharField(max_length=80)
    destino = models.CharField(max_length=80)
    salida = models.DateTimeField()
    tarifa = models.DecimalField(max_digits=10, decimal_places=2)
    estado = models.CharField(max_length=20)

    class Meta:
        managed = False          # la tabla ya existe en Clever Cloud
        db_table = 'viaje'
        ordering = ['salida']

    def __str__(self):
        return f'{self.origen} → {self.destino} · {self.salida:%d/%m/%Y %H:%M}'


class Reserva(models.Model):
    id_reserva = models.AutoField(primary_key=True)
    fecha_reserva = models.DateTimeField(auto_now_add=True)
    id_usuario = models.ForeignKey(
        'usuarios.Usuario', on_delete=models.DO_NOTHING, db_column='id_usuario'
    )
    id_viaje = models.ForeignKey(
        Viaje, on_delete=models.DO_NOTHING, db_column='id_viaje'
    )
    numero_asiento = models.SmallIntegerField()
    rut_pasajero = models.CharField(max_length=12, null=True, blank=True)
    nombre_pasajero = models.CharField(max_length=120, null=True, blank=True)
    telefono = models.CharField(max_length=30, null=True, blank=True)
    estado = models.CharField(max_length=20)      # pendiente | confirmada | cancelada | expirada
    activa = models.BooleanField(null=True)       # 1 = ocupa el asiento, NULL = liberado

    class Meta:
        managed = False
        db_table = 'reserva'

    def __str__(self):
        return f'Reserva #{self.id_reserva} · asiento {self.numero_asiento}'


class Ticket(models.Model):
    id_ticket = models.AutoField(primary_key=True)
    codigo = models.CharField(max_length=40, unique=True)
    fecha_emision = models.DateTimeField(auto_now_add=True)
    id_reserva = models.ForeignKey(
        Reserva, on_delete=models.DO_NOTHING, db_column='id_reserva'
    )

    class Meta:
        managed = False
        db_table = 'ticket'

    def __str__(self):
        return self.codigo


class Venta(models.Model):
    id_venta = models.AutoField(primary_key=True)
    fecha = models.DateTimeField(auto_now_add=True)
    monto = models.DecimalField(max_digits=10, decimal_places=2)
    medio = models.CharField(max_length=20)       # efectivo | tarjeta
    id_ticket = models.ForeignKey(
        Ticket, on_delete=models.DO_NOTHING, db_column='id_ticket'
    )
    id_usuario = models.ForeignKey(
        'usuarios.Usuario', on_delete=models.DO_NOTHING, db_column='id_usuario'
    )

    class Meta:
        managed = False
        db_table = 'venta'

    def __str__(self):
        return f'Venta #{self.id_venta} · {self.monto}'