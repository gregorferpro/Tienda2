from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import (
    Cliente, DevolucionCliente, DetalleVenta, MovimientoInventario,
    Producto, Venta,
)
from .views import obtener_opciones_cita_devolucion


class DevolucionClienteTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='cliente1',
            password='secret123',
            email='cliente@example.com',
        )
        self.cliente = Cliente.objects.create(
            user=self.user,
            nombres='Cliente',
            apellidos='Demo',
            ci_nit='123456',
            telefono='70000000',
            email='cliente@example.com',
            direccion='Zona central',
            estado='activo',
        )
        self.producto = Producto.objects.create(
            codigo='CEL-001',
            nombre='iPhone Test',
            marca='Apple',
            modelo='15',
            tipo_producto='celular',
            categoria='Celulares',
            descripcion='Equipo de prueba',
            precio=Decimal('8999.00'),
            costo_referencia=Decimal('7000.00'),
            stock=4,
            activo=True,
        )
        self.venta = Venta.objects.create(
            cliente=self.cliente,
            usuario=self.user,
            numero_factura='FAC-0001',
            metodo_pago='EFECTIVO',
            subtotal=Decimal('8999.00'),
            descuento=Decimal('0.00'),
            total=Decimal('8999.00'),
            estado_pago='pagado',
        )
        self.detalle = DetalleVenta.objects.create(
            venta=self.venta,
            producto=self.producto,
            cantidad=1,
            precio_unitario=Decimal('8999.00'),
            subtotal=Decimal('8999.00'),
        )
        self.staff = User.objects.create_user(
            username='staff1',
            password='secret123',
            email='staff@example.com',
            is_staff=True,
        )
        self.staff.perfil.rol = 'staff'
        self.staff.perfil.save(update_fields=['rol'])

    def test_cliente_puede_registrar_devolucion_en_plazo(self):
        self.client.login(username='cliente1', password='secret123')
        fecha_cita = obtener_opciones_cita_devolucion()[0][0]

        response = self.client.post(reverse('mis_devoluciones'), {
            'numero_factura': self.venta.numero_factura,
            'detalle_venta': self.detalle.pk,
            'fecha_cita': fecha_cita,
            'motivo': 'No cumple lo esperado',
            'observaciones_cliente': 'Caja completa',
        })

        self.assertEqual(response.status_code, 302)
        devolucion = DevolucionCliente.objects.get(detalle_venta=self.detalle)
        self.assertEqual(devolucion.venta, self.venta)
        self.assertEqual(devolucion.cliente, self.cliente)
        self.assertTrue(devolucion.codigo_ticket.startswith('DEV-'))

    def test_no_permite_registrar_devolucion_fuera_de_plazo(self):
        Venta.objects.filter(pk=self.venta.pk).update(
            fecha=timezone.now() - timedelta(days=4)
        )
        self.venta.refresh_from_db()
        self.client.login(username='cliente1', password='secret123')
        fecha_cita = obtener_opciones_cita_devolucion()[0][0]

        response = self.client.post(reverse('mis_devoluciones'), {
            'numero_factura': self.venta.numero_factura,
            'detalle_venta': self.detalle.pk,
            'fecha_cita': fecha_cita,
            'motivo': 'Reporte fuera de plazo',
            'observaciones_cliente': '',
        }, follow=True)

        self.assertEqual(response.status_code, 200)
        self.assertFalse(
            DevolucionCliente.objects.filter(detalle_venta=self.detalle).exists()
        )
        self.assertContains(response, 'dentro de los primeros 3 dias')

    def test_aprobar_devolucion_restablece_stock_y_crea_movimiento(self):
        devolucion = DevolucionCliente.objects.create(
            venta=self.venta,
            detalle_venta=self.detalle,
            cliente=self.cliente,
            codigo_ticket='DEV-TEST-001',
            fecha_cita=timezone.localdate(),
            motivo='Falla de fabrica',
            observaciones_cliente='Se apaga solo',
        )
        self.client.login(username='staff1', password='secret123')

        response = self.client.post(reverse('devolucion_cliente_detail', args=[devolucion.pk]), {
            'accion': 'aprobar',
            'confirmar_revision': 'on',
            'observaciones_revision': 'Equipo recibido y validado',
        })

        self.assertEqual(response.status_code, 302)
        devolucion.refresh_from_db()
        self.producto.refresh_from_db()

        self.assertEqual(devolucion.estado, 'aprobada')
        self.assertTrue(devolucion.stock_restaurado)
        self.assertEqual(self.producto.stock, 5)
        self.assertTrue(
            MovimientoInventario.objects.filter(
                producto=self.producto,
                motivo__icontains='DEV-TEST-001',
            ).exists()
        )
