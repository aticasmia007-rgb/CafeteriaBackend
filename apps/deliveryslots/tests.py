import datetime

from django.test import TestCase
from rest_framework.test import APIClient

from apps.userauth.models import CafeteriaUser
from apps.products.models import Product
from apps.orders.models import Order
from apps.orders.services import create_order, confirm_order_payment
from .models import DeliverySlot

BASE = '/api/deliveryslots'


def make_user(email='user@test.com', role='client', **kwargs):
    return CafeteriaUser.objects.create_user(
        email=email, name='Test User', password='pass1234', role=role, **kwargs
    )


def make_slot(start_time=None, end_time=None, capacity=10, active=True):
    return DeliverySlot.objects.create(
        start_time=start_time or datetime.time(10, 0),
        end_time=end_time or datetime.time(10, 15),
        capacity=capacity,
        active=active,
    )


def make_product(stock=10):
    from decimal import Decimal
    return Product.objects.create(
        name='Bocadillo', description='desc',
        price=Decimal('2.50'), available=True, stock=stock, prepare_required=False,
    )


def auth_client(user):
    from rest_framework_simplejwt.tokens import RefreshToken
    client = APIClient()
    token = str(RefreshToken.for_user(user).access_token)
    client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
    return client


class DeliverySlotModelTest(TestCase):
    def test_str_label(self):
        slot = make_slot(datetime.time(9, 0), datetime.time(9, 15))
        self.assertEqual(str(slot), '09:00–09:15')


class AvailableSlotsViewTest(TestCase):
    def setUp(self):
        self.slot = make_slot(capacity=2)
        self.product = make_product()
        self.client_user = make_user()

    def test_returns_active_slots(self):
        res = APIClient().get(f'{BASE}/available/')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(res.data['data']), 1)

    def test_inactive_slot_excluded(self):
        make_slot(active=False)
        res = APIClient().get(f'{BASE}/available/')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(res.data['data']), 1)

    def test_full_slot_excluded(self):
        for i in range(2):
            user = make_user(email=f'u{i}@test.com')
            order = create_order(user, self.slot, [{'product_id': self.product.id, 'quantity': 1}])
            confirm_order_payment(order)
        res = APIClient().get(f'{BASE}/available/')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(res.data['data']), 0)

    def test_remaining_counts_only_active_states(self):
        user = make_user(email='pending@test.com')
        create_order(user, self.slot, [{'product_id': self.product.id, 'quantity': 1}])
        res = APIClient().get(f'{BASE}/available/')
        data = res.data['data']
        self.assertEqual(data[0]['remaining'], 2)

    def test_remaining_decrements_after_payment(self):
        user = make_user(email='paid@test.com')
        order = create_order(user, self.slot, [{'product_id': self.product.id, 'quantity': 1}])
        confirm_order_payment(order)
        res = APIClient().get(f'{BASE}/available/')
        data = res.data['data']
        self.assertEqual(data[0]['remaining'], 1)

    def test_date_included_in_response(self):
        res = APIClient().get(f'{BASE}/available/')
        self.assertIn('date', res.data['data'][0])

    def test_invalid_date_format(self):
        res = APIClient().get(f'{BASE}/available/?date=not-a-date')
        self.assertEqual(res.status_code, 422)

    def test_no_auth_required(self):
        res = APIClient().get(f'{BASE}/available/')
        self.assertEqual(res.status_code, 200)


class SlotTemplateViewTest(TestCase):
    def setUp(self):
        self.staff = make_user(email='staff@test.com', role='staff')
        self.client_user = make_user()
        make_slot(active=True)
        make_slot(active=False)

    def test_staff_sees_all_slots(self):
        api = auth_client(self.staff)
        res = api.get(f'{BASE}/')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(res.data['data']), 2)

    def test_client_forbidden(self):
        api = auth_client(self.client_user)
        res = api.get(f'{BASE}/')
        self.assertEqual(res.status_code, 403)

    def test_unauthenticated_forbidden(self):
        res = APIClient().get(f'{BASE}/')
        self.assertEqual(res.status_code, 401)


class SlotCreateViewTest(TestCase):
    def setUp(self):
        self.admin = make_user(email='admin@test.com', role='admin')
        self.staff = make_user(email='staff@test.com', role='staff')

    def _payload(self):
        return {'start_time': '11:00', 'end_time': '11:15', 'capacity': 20}

    def test_admin_can_create(self):
        api = auth_client(self.admin)
        res = api.post(f'{BASE}/', self._payload(), format='json')
        self.assertEqual(res.status_code, 201)
        self.assertIn('slot_id', res.data['data'])

    def test_staff_cannot_create(self):
        api = auth_client(self.staff)
        res = api.post(f'{BASE}/', self._payload(), format='json')
        self.assertEqual(res.status_code, 403)

    def test_missing_fields_returns_422(self):
        api = auth_client(self.admin)
        res = api.post(f'{BASE}/', {'start_time': '11:00'}, format='json')
        self.assertEqual(res.status_code, 422)


class SlotUpdateViewTest(TestCase):
    def setUp(self):
        self.admin = make_user(email='admin@test.com', role='admin')
        self.staff = make_user(email='staff@test.com', role='staff')
        self.slot = make_slot()

    def test_staff_can_update_capacity(self):
        api = auth_client(self.staff)
        res = api.patch(f'{BASE}/{self.slot.id}/', {'capacity': 5}, format='json')
        self.assertEqual(res.status_code, 200)
        self.slot.refresh_from_db()
        self.assertEqual(self.slot.capacity, 5)

    def test_staff_can_deactivate(self):
        api = auth_client(self.staff)
        res = api.patch(f'{BASE}/{self.slot.id}/', {'active': False}, format='json')
        self.assertEqual(res.status_code, 200)
        self.slot.refresh_from_db()
        self.assertFalse(self.slot.active)


class SlotDeleteViewTest(TestCase):
    def setUp(self):
        self.admin = make_user(email='admin@test.com', role='admin')
        self.staff = make_user(email='staff@test.com', role='staff')
        self.slot = make_slot()

    def test_admin_can_delete_empty_slot(self):
        api = auth_client(self.admin)
        res = api.delete(f'{BASE}/{self.slot.id}/')
        self.assertEqual(res.status_code, 200)
        self.assertFalse(DeliverySlot.objects.filter(id=self.slot.id).exists())

    def test_cannot_delete_slot_with_orders(self):
        product = make_product()
        user = make_user(email='c@test.com')
        create_order(user, self.slot, [{'product_id': product.id, 'quantity': 1}])
        api = auth_client(self.admin)
        res = api.delete(f'{BASE}/{self.slot.id}/')
        self.assertEqual(res.status_code, 422)

    def test_staff_cannot_delete(self):
        api = auth_client(self.staff)
        res = api.delete(f'{BASE}/{self.slot.id}/')
        self.assertEqual(res.status_code, 403)


class SlotOrdersViewTest(TestCase):
    def setUp(self):
        self.staff = make_user(email='staff@test.com', role='staff')
        self.client_user = make_user()
        self.slot = make_slot()
        self.product = make_product()
        today = datetime.date.today().isoformat()
        self.today = today

    def test_returns_active_orders_for_slot(self):
        order = create_order(self.client_user, self.slot, [{'product_id': self.product.id, 'quantity': 1}])
        confirm_order_payment(order)
        api = auth_client(self.staff)
        res = api.get(f'{BASE}/{self.slot.id}/orders/?date={self.today}')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data['data']['orders_count'], 1)

    def test_pending_orders_excluded(self):
        create_order(self.client_user, self.slot, [{'product_id': self.product.id, 'quantity': 1}])
        api = auth_client(self.staff)
        res = api.get(f'{BASE}/{self.slot.id}/orders/?date={self.today}')
        self.assertEqual(res.data['data']['orders_count'], 0)

    def test_requires_date_param(self):
        api = auth_client(self.staff)
        res = api.get(f'{BASE}/{self.slot.id}/orders/')
        self.assertEqual(res.status_code, 422)

    def test_client_cannot_access(self):
        api = auth_client(self.client_user)
        res = api.get(f'{BASE}/{self.slot.id}/orders/?date={self.today}')
        self.assertEqual(res.status_code, 403)
