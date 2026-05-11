import uuid
from decimal import Decimal

from django.test import TestCase
from rest_framework.test import APIClient

from apps.userauth.models import CafeteriaUser
from apps.products.models import Product
from apps.deliveryslots.models import DeliverySlot
from .models import Order, OrderItem
from .services import generate_pickup_code, create_order, confirm_order_payment, cancel_order

BASE = '/api/orders'


def make_user(email='user@test.com', role='client', **kwargs):
    return CafeteriaUser.objects.create_user(
        email=email, name='Test User', password='pass1234', role=role, **kwargs
    )


def make_product(name='Bocadillo', price='2.50', available=True, stock=10):
    return Product.objects.create(
        name=name,
        description='desc',
        price=Decimal(price),
        available=available,
        stock=stock,
        prepare_required=False,
    )


def make_slot(active=True):
    from datetime import time
    return DeliverySlot.objects.create(
        start_time=time(10, 0),
        end_time=time(10, 15),
        capacity=50,
        active=active,
    )


def auth_client(user):
    from rest_framework_simplejwt.tokens import RefreshToken
    client = APIClient()
    token = str(RefreshToken.for_user(user).access_token)
    client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
    return client


class OrderModelTest(TestCase):
    def test_can_transition_paid_to_preparing(self):
        order = Order(state=Order.State.PAID)
        self.assertTrue(order.can_transition_to(Order.State.PREPARING))

    def test_can_transition_paid_to_collected(self):
        order = Order(state=Order.State.PAID)
        self.assertTrue(order.can_transition_to(Order.State.COLLECTED))

    def test_cannot_transition_paid_to_ready(self):
        order = Order(state=Order.State.PAID)
        self.assertFalse(order.can_transition_to(Order.State.READY))

    def test_can_transition_preparing_to_ready(self):
        order = Order(state=Order.State.PREPARING)
        self.assertTrue(order.can_transition_to(Order.State.READY))

    def test_can_transition_preparing_to_collected(self):
        order = Order(state=Order.State.PREPARING)
        self.assertTrue(order.can_transition_to(Order.State.COLLECTED))

    def test_can_transition_ready_to_collected(self):
        order = Order(state=Order.State.READY)
        self.assertTrue(order.can_transition_to(Order.State.COLLECTED))

    def test_cannot_transition_pending(self):
        order = Order(state=Order.State.PENDING)
        self.assertFalse(order.can_transition_to(Order.State.PAID))

    def test_cannot_transition_cancelled(self):
        order = Order(state=Order.State.CANCELLED)
        self.assertFalse(order.can_transition_to(Order.State.PAID))


class ServicesTest(TestCase):
    def setUp(self):
        self.user = make_user()
        self.slot = make_slot()
        self.product = make_product()

    def test_generate_pickup_code_is_unique(self):
        codes = {generate_pickup_code() for _ in range(20)}
        self.assertEqual(len(codes), 20)

    def test_create_order(self):
        order = create_order(
            client=self.user,
            slot=self.slot,
            items_data=[{'product_id': self.product.id, 'quantity': 2}],
        )
        self.assertEqual(order.state, Order.State.PENDING)
        self.assertEqual(order.total, Decimal('5.00'))
        self.assertEqual(order.items.count(), 1)
        item = order.items.first()
        self.assertEqual(item.quantity, 2)
        self.assertEqual(item.unit_price, Decimal('2.50'))

    def test_confirm_order_payment(self):
        order = create_order(
            client=self.user,
            slot=self.slot,
            items_data=[{'product_id': self.product.id, 'quantity': 3}],
        )
        confirm_order_payment(order)
        order.refresh_from_db()
        self.assertEqual(order.state, Order.State.PAID)
        self.assertTrue(order.pickup_code)
        self.assertIsNotNone(order.paid_at)
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 7)

    def test_confirm_order_payment_sets_unavailable_when_stock_zero(self):
        product = make_product(stock=2)
        order = create_order(
            client=self.user,
            slot=self.slot,
            items_data=[{'product_id': product.id, 'quantity': 2}],
        )
        confirm_order_payment(order)
        product.refresh_from_db()
        self.assertEqual(product.stock, 0)
        self.assertFalse(product.available)

    def test_cancel_order(self):
        order = create_order(
            client=self.user,
            slot=self.slot,
            items_data=[{'product_id': self.product.id, 'quantity': 1}],
        )
        cancel_order(order)
        order.refresh_from_db()
        self.assertEqual(order.state, Order.State.CANCELLED)


class OrderCreateViewTest(TestCase):
    def setUp(self):
        self.client_user = make_user()
        self.api = auth_client(self.client_user)
        self.slot = make_slot()
        self.product = make_product()

    _SENTINEL = object()

    def _payload(self, slot_id=None, items=_SENTINEL):
        return {
            'slot_id': str(slot_id or self.slot.id),
            'items': [{'product_id': str(self.product.id), 'quantity': 1}] if items is self._SENTINEL else items,
        }

    def test_create_order_success(self):
        res = self.api.post(f'{BASE}/', self._payload(), format='json')
        self.assertEqual(res.status_code, 201)
        self.assertEqual(res.data['status'], '00')
        self.assertIn('data', res.data)

    def test_create_order_unauthenticated(self):
        res = APIClient().post(f'{BASE}/', self._payload(), format='json')
        self.assertEqual(res.status_code, 401)

    def test_create_order_invalid_slot(self):
        payload = self._payload(slot_id=uuid.uuid4())
        res = self.api.post(f'{BASE}/', payload, format='json')
        self.assertEqual(res.status_code, 422)

    def test_create_order_inactive_slot(self):
        slot = make_slot(active=False)
        res = self.api.post(f'{BASE}/', self._payload(slot_id=slot.id), format='json')
        self.assertEqual(res.status_code, 422)

    def test_create_order_unavailable_product(self):
        product = make_product(available=False)
        payload = self._payload(items=[{'product_id': str(product.id), 'quantity': 1}])
        res = self.api.post(f'{BASE}/', payload, format='json')
        self.assertEqual(res.status_code, 422)

    def test_create_order_insufficient_stock(self):
        product = make_product(stock=2)
        payload = self._payload(items=[{'product_id': str(product.id), 'quantity': 5}])
        res = self.api.post(f'{BASE}/', payload, format='json')
        self.assertEqual(res.status_code, 422)

    def test_create_order_duplicate_products(self):
        payload = self._payload(items=[
            {'product_id': str(self.product.id), 'quantity': 1},
            {'product_id': str(self.product.id), 'quantity': 2},
        ])
        res = self.api.post(f'{BASE}/', payload, format='json')
        self.assertEqual(res.status_code, 422)

    def test_create_order_empty_items(self):
        payload = self._payload(items=[])
        res = self.api.post(f'{BASE}/', payload, format='json')
        self.assertEqual(res.status_code, 422)


class OrderListViewTest(TestCase):
    def setUp(self):
        self.client_user = make_user()
        self.other_user = make_user(email='other@test.com')
        self.api = auth_client(self.client_user)
        self.slot = make_slot()
        self.product = make_product()

    def test_list_only_own_orders(self):
        create_order(self.client_user, self.slot, [{'product_id': self.product.id, 'quantity': 1}])
        create_order(self.other_user, self.slot, [{'product_id': self.product.id, 'quantity': 1}])
        res = self.api.get(f'{BASE}/')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(res.data['data']), 1)

    def test_list_unauthenticated(self):
        res = APIClient().get(f'{BASE}/')
        self.assertEqual(res.status_code, 401)


class OrderDetailViewTest(TestCase):
    def setUp(self):
        self.client_user = make_user()
        self.other_user = make_user(email='other@test.com')
        self.staff_user = make_user(email='staff@test.com', role='staff')
        self.slot = make_slot()
        self.product = make_product()
        self.order = create_order(
            self.client_user, self.slot,
            [{'product_id': self.product.id, 'quantity': 1}]
        )

    def test_owner_can_retrieve(self):
        api = auth_client(self.client_user)
        res = api.get(f'{BASE}/{self.order.id}/')
        self.assertEqual(res.status_code, 200)

    def test_other_client_cannot_retrieve(self):
        api = auth_client(self.other_user)
        res = api.get(f'{BASE}/{self.order.id}/')
        self.assertEqual(res.status_code, 403)

    def test_staff_can_retrieve(self):
        api = auth_client(self.staff_user)
        res = api.get(f'{BASE}/{self.order.id}/')
        self.assertEqual(res.status_code, 200)

    def test_not_found(self):
        api = auth_client(self.client_user)
        res = api.get(f'{BASE}/{uuid.uuid4()}/')
        self.assertEqual(res.status_code, 404)


class OrderStateUpdateViewTest(TestCase):
    def setUp(self):
        self.client_user = make_user()
        self.staff_user = make_user(email='staff@test.com', role='staff')
        self.slot = make_slot()
        self.product = make_product()
        self.order = create_order(
            self.client_user, self.slot,
            [{'product_id': self.product.id, 'quantity': 1}]
        )
        # Move to paid so transitions are valid
        confirm_order_payment(self.order)

    def test_staff_can_advance_state(self):
        api = auth_client(self.staff_user)
        res = api.patch(f'{BASE}/{self.order.id}/', {'state': 'preparing'}, format='json')
        self.assertEqual(res.status_code, 200)
        self.order.refresh_from_db()
        self.assertEqual(self.order.state, Order.State.PREPARING)

    def test_client_cannot_update_state(self):
        api = auth_client(self.client_user)
        res = api.patch(f'{BASE}/{self.order.id}/', {'state': 'preparing'}, format='json')
        self.assertEqual(res.status_code, 403)

    def test_invalid_transition(self):
        api = auth_client(self.staff_user)
        res = api.patch(f'{BASE}/{self.order.id}/', {'state': 'ready'}, format='json')
        self.assertEqual(res.status_code, 422)

    def test_cannot_set_paid_via_patch(self):
        order = create_order(
            self.client_user, self.slot,
            [{'product_id': self.product.id, 'quantity': 1}]
        )
        api = auth_client(self.staff_user)
        res = api.patch(f'{BASE}/{order.id}/', {'state': 'paid'}, format='json')
        # pending has no valid transitions, so 422
        self.assertEqual(res.status_code, 422)


class AllOrdersViewTest(TestCase):
    def setUp(self):
        self.client_user = make_user()
        self.staff_user = make_user(email='staff@test.com', role='staff')
        self.slot = make_slot()
        self.product = make_product()

    def test_staff_can_list_all(self):
        create_order(self.client_user, self.slot, [{'product_id': self.product.id, 'quantity': 1}])
        api = auth_client(self.staff_user)
        res = api.get(f'{BASE}/all/')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(res.data['data']), 1)

    def test_client_cannot_access(self):
        api = auth_client(self.client_user)
        res = api.get(f'{BASE}/all/')
        self.assertEqual(res.status_code, 403)

    def test_filter_by_state(self):
        order = create_order(self.client_user, self.slot, [{'product_id': self.product.id, 'quantity': 1}])
        confirm_order_payment(order)
        api = auth_client(self.staff_user)
        res = api.get(f'{BASE}/all/?state=paid')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(res.data['data']), 1)
        res2 = api.get(f'{BASE}/all/?state=pending')
        self.assertEqual(len(res2.data['data']), 0)

    def test_filter_by_slot(self):
        slot2 = make_slot()
        create_order(self.client_user, self.slot, [{'product_id': self.product.id, 'quantity': 1}])
        create_order(self.client_user, slot2, [{'product_id': self.product.id, 'quantity': 1}])
        api = auth_client(self.staff_user)
        res = api.get(f'{BASE}/all/?slot_id={self.slot.id}')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(res.data['data']), 1)
