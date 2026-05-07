# Cafeteria Backend — Project Definition

Django REST Framework backend for the school cafeteria ordering system. Designed by Jonathan & Andrea.

**Stack:** Django 6, Django REST Framework 3.17, SQLite (dev)

---

## Architecture

```
CafeteriaBackend/
├── config/            # Django project settings, URLs, WSGI/ASGI
├── apps/              # One Django app per domain concept
│   ├── userauth/      # Authentication (Google SSO + in-house)
│   ├── userprofile/   # User profile management
│   ├── products/      # Product catalog
│   ├── categories/    # Product categories
│   ├── allergens/     # Allergen catalog
│   ├── orders/        # Order lifecycle
│   ├── payments/      # Redsys payment gateway
│   ├── inventory/     # Stock management
│   └── deliveryslots/ # Pickup time slots
└── manage.py
```

Each app contains: `models.py`, `serializers.py`, `views.py`, `urls.py`, `admin.py`.

> **Note:** The authentication app was renamed from `apps/auth` to `apps/userauth` to avoid shadowing Django's built-in `django.contrib.auth` module.

---

## Roles

| Role   | Description                                      |
|--------|--------------------------------------------------|
| client | Regular user. Can browse, order, view own orders |
| staff  | Cafeteria staff. Manages orders and inventory    |
| admin  | Full access. Manages users, products, categories |

Role is stored on the user model as a `CharField` with choices.

---

## Standard Response Format

All endpoints wrap their payload in a consistent envelope. Use a shared DRF renderer or override `finalize_response` in a base `APIView`.

Success:
```json
{ "status": "00", "data": { ... } }
{ "status": "00", "msg": "...", "data": { ... } }
```

Error:
```json
{ "status": "string", "msg": "string", "errors": [] }
```

| HTTP | status | Meaning                  |
|------|--------|--------------------------|
| 200  | 00     | Success                  |
| 201  | 00     | Created                  |
| 401  | 02     | Token expired            |
| 401  | 03     | Invalid credentials      |
| 403  | 04     | Insufficient permissions |
| 404  | 05     | Resource not found       |
| 422  | 06     | Validation error         |
| 502  | 07     | Payment gateway error    |
| 500  | 99     | Internal server error    |

---

## DRF Workflows

These are the standard patterns to follow when implementing any endpoint in this project.

### File layout per app

Every app exposes the same four files that agents work on:

```
apps/<app>/
├── models.py       # Django ORM models
├── serializers.py  # DRF serializers (validation + representation)
├── views.py        # DRF views or viewsets
└── urls.py         # URL routing for the app
```

### Choosing the right DRF class

| Situation | Use |
|-----------|-----|
| Standard CRUD on a single model | `ModelViewSet` + `DefaultRouter` |
| CRUD but some actions need custom logic | `ModelViewSet` with overridden methods (`perform_create`, `perform_update`, `get_queryset`) |
| Non-CRUD endpoint (e.g. webhook, login) | `APIView` |
| Read-only public endpoint | `ReadOnlyModelViewSet` or `ListAPIView` / `RetrieveAPIView` |
| Action on a related sub-resource (e.g. `/slots/{id}/orders/`) | `@action(detail=True, ...)` on a `ModelViewSet` |

### URL routing

Use `DefaultRouter` for viewsets, explicit `path()` for standalone `APIView`s:

```python
# apps/<app>/urls.py
from rest_framework.routers import DefaultRouter
from .views import MyViewSet

router = DefaultRouter()
router.register(r'', MyViewSet, basename='my-resource')
urlpatterns = router.urls
```

For `APIView`:
```python
from django.urls import path
from .views import MyView

urlpatterns = [
    path('', MyView.as_view()),
    path('<int:pk>/', MyView.as_view()),
]
```

Register in `config/urls.py` (current state — no trailing slashes on prefixes, matching the team's convention):
```python
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/userauth', include('apps.userauth.urls')),
    path('api/userprofile', include('apps.userprofile.urls')),
    path('api/products', include('apps.products.urls')),
    path('api/categories', include('apps.categories.urls')),
    path('api/allergens', include('apps.allergens.urls')),
    path('api/orders', include('apps.orders.urls')),
    path('api/payments', include('apps.payments.urls')),
    path('api/inventory', include('apps.inventory.urls')),
    path('api/deliveryslots', include('apps.deliveryslots.urls')),
]
```

### Authentication

Use `rest_framework_simplejwt` (install separately). Configure globally in `settings.py`:

```python
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
}
```

Endpoints that are public (no auth) override at the view level:
```python
permission_classes = [AllowAny]
```

### Permission classes

Create reusable permission classes in `config/permissions.py`:

```python
from rest_framework.permissions import BasePermission

class IsAdmin(BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role == 'admin'

class IsStaffOrAdmin(BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role in ('staff', 'admin')

class IsClientOrAbove(BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role in ('client', 'staff', 'admin')
```

Apply per view:
```python
permission_classes = [IsStaffOrAdmin]
```

For viewsets where different actions need different permissions, use `get_permissions()`:
```python
def get_permissions(self):
    if self.action in ('list', 'retrieve'):
        return [AllowAny()]
    return [IsAdmin()]
```

### Serializers

**Read vs. write serializers:** When GET and POST/PATCH need different field shapes (e.g. `allergens` returns objects but accepts IDs), define two serializers:

```python
class AllergenSerializer(serializers.ModelSerializer):
    class Meta:
        model = Allergen
        fields = ['allergen_id', 'name', 'icon']

class ProductReadSerializer(serializers.ModelSerializer):
    category = CategorySerializer(read_only=True)
    allergens = AllergenSerializer(many=True, read_only=True)
    class Meta:
        model = Product
        fields = '__all__'

class ProductWriteSerializer(serializers.ModelSerializer):
    allergens = serializers.PrimaryKeyRelatedField(
        many=True, queryset=Allergen.objects.all()
    )
    class Meta:
        model = Product
        fields = ['name', 'description', 'price', 'category', 'allergens', 'image', 'available', 'stock']
```

Select the right serializer in the viewset:
```python
def get_serializer_class(self):
    if self.request.method in ('POST', 'PATCH', 'PUT'):
        return ProductWriteSerializer
    return ProductReadSerializer
```

**Partial updates:** For PATCH, always pass `partial=True` to the serializer:
```python
serializer = ProductWriteSerializer(instance, data=request.data, partial=True)
```
DRF's `ModelViewSet.partial_update()` does this automatically when mapped to PATCH.

### Response envelope

Wrap all responses in the standard envelope. Override `finalize_response` in a base class or use a custom renderer. Simplest approach — a utility function:

```python
# config/responses.py
from rest_framework.response import Response

def success(data=None, msg=None, status_code=200, created=False):
    body = {'status': '00'}
    if msg:
        body['msg'] = msg
    if data is not None:
        body['data'] = data
    return Response(body, status=201 if created else status_code)

def error(status_code, internal_status, msg, errors=None):
    return Response(
        {'status': internal_status, 'msg': msg, 'errors': errors or []},
        status=status_code,
    )
```

Use these in every view instead of returning raw `Response`.

### Validation errors (422)

DRF raises `ValidationError` with HTTP 400 by default. Override the exception handler globally to return 422 and wrap in the envelope:

```python
# config/exceptions.py
from rest_framework.views import exception_handler
from rest_framework.response import Response

def custom_exception_handler(exc, context):
    response = exception_handler(exc, context)
    if response is not None and response.status_code == 400:
        return Response(
            {'status': '06', 'msg': 'Los datos de entrada no son válidos.', 'errors': response.data},
            status=422,
        )
    return response
```

Register in `settings.py`:
```python
REST_FRAMEWORK = {
    ...
    'EXCEPTION_HANDLER': 'config.exceptions.custom_exception_handler',
}
```

### Queryset filtering

For list endpoints that support query params, filter inside `get_queryset()` on the viewset:

```python
def get_queryset(self):
    qs = Product.objects.all()
    category = self.request.query_params.get('category')
    if category:
        qs = qs.filter(category_id=category)
    allergen = self.request.query_params.get('allergen')
    if allergen:
        qs = qs.filter(allergens__id=allergen)
    search = self.request.query_params.get('search')
    if search:
        qs = qs.filter(name__icontains=search)
    return qs
```

### Pagination

Configure globally in `settings.py`:
```python
REST_FRAMEWORK = {
    ...
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 20,
}
```

The paginator wraps the list response automatically. For endpoints that must not paginate (e.g. allergens, categories), set `pagination_class = None` on the view.

### Calculated / annotated fields

Fields like `remaining` (slots) and `product_count` (categories) are never stored. Compute them with `annotate()` in `get_queryset()` and expose via a `SerializerMethodField`:

```python
# In viewset
from django.db.models import Count, Q

def get_queryset(self):
    return DeliverySlot.objects.annotate(
        remaining=F('capacity') - Count(
            'orders', filter=Q(orders__state__in=['paid', 'preparing', 'ready', 'collected'])
        )
    )

# In serializer
remaining = serializers.IntegerField(read_only=True)
```

### Business logic placement

Keep views thin. Put non-trivial logic in the model or a dedicated service function in `apps/<app>/services.py`:

- Stock decrement after payment → `apps/inventory/services.py`
- Pickup code generation → `apps/orders/services.py`
- Redsys signature validation → `apps/payments/services.py`

Call services from `perform_create` / `perform_update` in the viewset, or directly in the `APIView.post()` method.

---

## App: `userauth`

Django app: `apps/userauth` — URL prefix: `/api/userauth`

Handles user authentication via Google SSO and in-house email/password. Issues JWT session tokens.

**Current `urls.py` state** (placeholder view active, rest commented out):
```python
path('', views.probando),                               # placeholder
# path('google/', views.google_login)
# path('login/', views.login_in_house)
# path('register/', views.register_in_house)
# path('logout/', views.logout)
# path('password-recovery/', views.password_recovery)
# path('password-recovery/confirm/', views.confirm_recovery)
```

**Endpoints:**

| Method | Route                                        | Auth     | DRF class | Description                       |
|--------|----------------------------------------------|----------|-----------|-----------------------------------|
| POST   | /api/userauth/google/                        | No       | APIView   | Validate Google token, return JWT |
| POST   | /api/userauth/login/                         | No       | APIView   | In-house login                    |
| POST   | /api/userauth/register/                      | No       | APIView   | Register new user                 |
| POST   | /api/userauth/logout/                        | Required | APIView   | Invalidate session token          |
| POST   | /api/userauth/password-recovery/             | No       | APIView   | Start password reset (send OTP)   |
| POST   | /api/userauth/password-recovery/confirm/     | No       | APIView   | Confirm OTP, set new password     |

**Key behaviors:**
- Google SSO: frontend sends Google ID Token → backend validates with Google API → creates/retrieves user → returns own JWT + refresh token
- In-house register: user created with `is_active=False` → OTP sent to email → `is_active=True` after verification
- Password recovery always returns HTTP 200 even if email not found (no account enumeration)
- Logout adds token to a blacklist (use `rest_framework_simplejwt.token_blacklist`)

---

## App: `userprofile`

Django app: `apps/userprofile` — URL prefix: `/api/userprofile`

Manages the authenticated user's own profile data. Separate from `userauth`: auth handles access, userprofile handles personal data.

**Current `urls.py` state** (placeholder view active, rest commented out):
```python
path('', views.probando),                               # placeholder
# path('me/', views.my_profile)
# path('me/password/', views.change_password)
# path('me/deactivate/', views.deactivate_account)
# path('email-otp/', views.send_otp)
# path('email-verification/', views.verify_email)
# path('admin/users/', views.list_users)
# path('admin/users/<str:user_id>/role/', views.change_user_role)
```

**Endpoints:**

| Method | Route                                     | Auth     | DRF class   | Roles         | Description                     |
|--------|-------------------------------------------|----------|-------------|---------------|---------------------------------|
| GET    | /api/userprofile/me/                      | Required | APIView     | All           | Get own profile                 |
| PATCH  | /api/userprofile/me/                      | Required | APIView     | All           | Update name or avatar           |
| PATCH  | /api/userprofile/me/password/             | Required | APIView     | in-house only | Change password                 |
| PATCH  | /api/userprofile/me/deactivate/           | Required | APIView     | All           | Deactivate own account          |
| GET    | /api/userprofile/email-otp/               | Required | APIView     | All           | Send OTP to registered email    |
| POST   | /api/userprofile/email-verification/      | Required | APIView     | All           | Confirm OTP, verify email       |
| GET    | /api/userprofile/admin/users/             | Required | ListAPIView | admin         | List and search all users       |
| PATCH  | /api/userprofile/admin/users/{id}/role/   | Required | APIView     | admin         | Change user role                |

**User object schema:**

| Field          | Type    | Notes                             |
|----------------|---------|-----------------------------------|
| user_id        | string  | UUID                              |
| name           | string  |                                   |
| email          | string  | Not editable directly             |
| avatar         | string  | URL or base64                     |
| auth_provider  | string  | `google` or `inhouse`             |
| email_verified | boolean |                                   |
| active         | boolean | false blocks login                |
| role           | string  | `client`, `staff`, or `admin`     |
| created_at     | string  | ISO 8601                          |

**Key behaviors:**
- Email is not editable via PATCH /api/user/me — requires OTP verification flow from `auth`
- Google users (`auth_provider == 'google'`) cannot use the change-password endpoint → return 422 status `06`
- Deactivated accounts keep order history; only admin can reactivate
- Deactivating immediately invalidates the current token
- Admin user list supports `?search=` (filter by name/email) and `?page=` pagination

---

## App: `products`

Django app: `apps/products` — URL prefix: `/api/products`

Exposes the cafeteria product catalog.

**Current `urls.py` state:**
```python
path('', views.product_catalog),      # GET list / POST create
# path('<str:id>/', views.product_detail)  # GET detail / PATCH update / DELETE
```

**Endpoints:**

| Method | Route               | Auth     | DRF class      | Roles             | Description              |
|--------|---------------------|----------|----------------|-------------------|--------------------------|
| GET    | /api/products/      | No       | ModelViewSet   | All               | List products            |
| GET    | /api/products/{id}/ | No       | ModelViewSet   | All               | Product detail           |
| POST   | /api/products/      | Required | ModelViewSet   | admin             | Create product           |
| PATCH  | /api/products/{id}/ | Required | ModelViewSet   | admin/staff/owner | Update product fields    |
| DELETE | /api/products/{id}/ | Required | ModelViewSet   | admin/staff/owner | Delete product           |

**Query params (GET /api/products/):** `?category=1&allergen=1&search=bocadillo`

**Product object schema:**

| Field       | Type    | Notes                                                              |
|-------------|---------|-------------------------------------------------------------------|
| id          | string  |                                                                   |
| name        | string  |                                                                   |
| description | string  |                                                                   |
| price       | decimal |                                                                   |
| category    | object  | `{ category_id, name }` in GET; `category_id` integer in POST/PATCH |
| allergens   | array   | Array of `{ allergen_id, name, icon }` in GET; array of IDs in POST/PATCH |
| image       | string  | URL                                                               |
| available   | boolean |                                                                   |
| stock       | integer |                                                                   |

**Key behaviors:**
- Use `ProductReadSerializer` for GET and `ProductWriteSerializer` for POST/PATCH (see DRF Workflows above)
- `category` and `allergens` are FK/M2M relations — never free strings
- Logical delete preferred: mark `available: false` instead of deleting, to preserve order history
- `perform_create` / `perform_update`: if `stock == 0`, set `available = False` before saving

---

## App: `categories`

Django app: `apps/categories` — URL prefix: `/api/categories`

Organizes products into groups (bebidas, bocadillos, dulces…).

**Current `urls.py` state:**
```python
path('', views.list_categories),           # GET list
# path('<int:id>/', views.category_detail)      # GET detail
# path('create/', views.create_category)        # POST
# path('<int:id>/update/', views.update_category) # PATCH
# path('<int:id>/delete/', views.delete_category) # DELETE
```

**Endpoints:**

| Method | Route                       | Auth     | DRF class    | Roles | Description               |
|--------|-----------------------------|----------|--------------|-------|---------------------------|
| GET    | /api/categories/            | No       | ModelViewSet | All   | List active categories    |
| GET    | /api/categories/{id}/       | No       | ModelViewSet | All   | Category detail           |
| POST   | /api/categories/            | Required | ModelViewSet | admin | Create category           |
| PATCH  | /api/categories/{id}/       | Required | ModelViewSet | admin | Update category           |
| DELETE | /api/categories/{id}/       | Required | ModelViewSet | admin | Delete (no products only) |

**Category object schema:**

| Field         | Type    | Notes                                          |
|---------------|---------|------------------------------------------------|
| category_id   | integer |                                                |
| name          | string  | e.g. "Bebidas"                                 |
| image         | string  | URL or base64                                  |
| active        | boolean | false → hidden from client catalog and filters |
| product_count | integer | Annotated field — not stored                   |

**Key behaviors:**
- `get_queryset` annotates with `product_count = Count('products')`
- Public GET filters to `active=True` only; admin/staff GET includes all
- `perform_destroy`: if `product_count > 0`, raise `ValidationError` with count → HTTP 422
- Deactivating a category (`active=False`) hides all its products from the public catalog

---

## App: `allergens`

Django app: `apps/allergens` — URL prefix: `/api/allergens`

Manages the allergen catalog. Simple CRUD, minimal business logic.

**Current `urls.py` state:**
```python
path('', views.main),                          # GET list
# path('create/', views.create_allergen)            # POST
# path('<int:id>/', views.update_allergen)           # PATCH
# path('<int:id>/delete/', views.delete_allergen)    # DELETE
```

**Endpoints:**

| Method | Route                    | Auth     | DRF class    | Roles | Description               |
|--------|--------------------------|----------|--------------|-------|---------------------------|
| GET    | /api/allergens/          | No       | ModelViewSet | All   | List all allergens        |
| POST   | /api/allergens/          | Required | ModelViewSet | admin | Create allergen           |
| PATCH  | /api/allergens/{id}/     | Required | ModelViewSet | admin | Update allergen           |
| DELETE | /api/allergens/{id}/     | Required | ModelViewSet | admin | Delete (no products only) |

**Allergen object schema:**

| Field       | Type    | Notes         |
|-------------|---------|---------------|
| allergen_id | integer |               |
| name        | string  | e.g. "Gluten" |
| icon        | string  | URL or base64 |

**Key behaviors:**
- `perform_destroy`: if allergen has associated products (`product_set.exists()`), raise `ValidationError` with count
- No pagination needed — the full list is always returned (used by frontend to build filter UI)
- Set `pagination_class = None` on this viewset

---

## App: `orders`

Django app: `apps/orders` — URL prefix: `/api/orders`

Manages the full purchase lifecycle.

**Order states (use `TextChoices`):**

| State     | Description                                |
|-----------|--------------------------------------------|
| pending   | Created, awaiting payment                  |
| paid      | Confirmed by Redsys webhook only           |
| preparing | Cafeteria is preparing                     |
| ready     | Ready for pickup                           |
| collected | Customer collected                         |
| cancelled | Payment failed or manually cancelled       |

**Current `urls.py` state:**
```python
path('', views.manage_orders),         # POST create / GET client history
# path('all/', views.all_orders)            # GET staff queue
# path('<str:id>/', views.order_detail)     # GET detail / PATCH update state
```

**Endpoints:**

| Method | Route              | Auth     | DRF class       | Roles             | Description                   |
|--------|--------------------|----------|-----------------|-------------------|-------------------------------|
| POST   | /api/orders/       | Required | APIView         | client            | Create order from cart        |
| GET    | /api/orders/       | Required | ListAPIView     | client            | Own order history (paginated) |
| GET    | /api/orders/{id}/  | Required | RetrieveAPIView | client            | Own order detail              |
| PATCH  | /api/orders/{id}/  | Required | APIView         | admin/staff/owner | Advance order state manually  |
| GET    | /api/orders/all/   | Required | ListAPIView     | admin/staff/owner | All orders (staff queue)      |

**Key behaviors:**
- `POST /api/orders/`: validate all products `available=True` and `stock >= quantity`; create order in `pending`; decrement stock on payment confirmation (not here)
- `state=paid` is set exclusively in the Redsys webhook — any PATCH attempt to set `paid` returns 403
- `pickup_code` is generated (unique short alphanumeric) in `apps/orders/services.py` when state transitions to `paid`
- `pending` orders do not count against slot capacity
- Staff can filter `GET /api/orders/all/` with `?state=paid&slot_id=3`
- Clients can only see their own orders — filter `get_queryset` by `request.user`

---

## App: `payments`

Django app: `apps/payments` — URL prefix: `/api/payments`

Integrates with Redsys TPV virtual. All payment is prepaid.

**Current `urls.py` state:**
```python
path('', views.initiate_payment),                   # POST initiate
# path('redsys/notification/', views.redsys_webhook)    # POST webhook
# path('<str:order_id>/', views.payment_status)          # GET status fallback
```

**Endpoints:**

| Method | Route                               | Auth              | DRF class | Description                    |
|--------|-------------------------------------|-------------------|-----------|--------------------------------|
| POST   | /api/payments/                      | Required (client) | APIView   | Generate Redsys signed params  |
| POST   | /api/payments/redsys/notification/  | None (HMAC)       | APIView   | Redsys webhook receiver        |
| GET    | /api/payments/{order_id}/           | Required (client) | APIView   | Poll payment status (fallback) |

**Webhook flow (POST /api/payments/redsys/notification/):**
1. Receive `Ds_MerchantParameters`, `Ds_Signature`, `Ds_SignatureVersion` from Redsys
2. Validate HMAC_SHA256 signature in `apps/payments/services.py`
3. Decode `Ds_MerchantParameters` (base64 → JSON)
4. Check `Ds_Response` code: `0000–0099` → success; anything else → failure
5. Success: set order to `paid`, generate `pickup_code`, decrement stock for each item
6. Failure: set order to `cancelled`
7. Always return HTTP 200 with empty body (`{}`) — Redsys expects this

**Key behaviors:**
- Webhook has `permission_classes = [AllowAny]`; security is the HMAC signature check
- `POST /api/payments/`: verify order is in `pending` state and belongs to `request.user`
- `GET /api/payments/{order_id}/`: return current `payment_state` and `paid_at`; client uses this for polling after Redsys redirect

---

## App: `inventory`

Django app: `apps/inventory` — URL prefix: `/api/inventory`

Operational stock view for staff. Extends product data with stock/availability details.

**Current `urls.py` state:**
```python
path('', views.full_inventory),                         # GET list
# path('<str:product_id>/', views.inventory_detail)          # GET detail
# path('<str:product_id>/update/', views.update_stock)        # PATCH
# path('alerts/', views.stock_alerts)                        # GET alerts
```

**Endpoints:**

| Method | Route                         | Auth     | DRF class       | Roles             | Description                   |
|--------|-------------------------------|----------|-----------------|-------------------|-------------------------------|
| GET    | /api/inventory/               | Required | ListAPIView     | admin/staff/owner | Full inventory                |
| GET    | /api/inventory/{product_id}/  | Required | RetrieveAPIView | admin/staff/owner | Single product stock detail   |
| PATCH  | /api/inventory/{product_id}/  | Required | APIView         | admin/staff/owner | Update stock/threshold/avail. |
| GET    | /api/inventory/alerts/        | Required | ListAPIView     | admin/staff/owner | Products below threshold      |

**Query params (GET /api/inventory/):** `?available=false&category=bebidas&low_stock=true`

**Inventory item schema:**

| Field               | Type    | Notes                                 |
|---------------------|---------|---------------------------------------|
| product_id          | string  |                                       |
| name                | string  |                                       |
| category            | string  |                                       |
| stock               | integer |                                       |
| low_stock_threshold | integer | Alert when `stock < threshold`        |
| available           | boolean |                                       |
| last_updated        | string  | ISO 8601 (detail endpoint only)       |

**Key behaviors:**
- Inventory reads from the `Product` model — no separate `Inventory` model needed unless requirements grow
- `PATCH /api/inventory/{product_id}/`: if `stock` updated to 0, automatically set `available=False`
- `GET /api/inventory/alerts/`: filter `stock__lt=F('low_stock_threshold')`
- `GET /api/inventory/?low_stock=true`: same filter applied inline in `get_queryset`
- Unlike public catalog, inventory shows all products regardless of `available`

---

## App: `deliveryslots`

Django app: `apps/deliveryslots` — URL prefix: `/api/deliveryslots`

Weekly pickup time slot template.

**Current `urls.py` state:**
```python
# path('available/', views.available_slots)       # GET public — commented out pending implementation
path('', views.slot_template),                  # GET staff template
# path('create/', views.create_slot)                # POST
# path('<int:id>/', views.update_slot)               # PATCH
# path('<int:id>/delete/', views.delete_slot)        # DELETE
# path('<int:id>/orders/', views.slot_orders)        # GET orders per slot
```

**Endpoints:**

| Method | Route                             | Auth     | DRF class    | Roles             | Description                         |
|--------|-----------------------------------|----------|--------------|-------------------|-------------------------------------|
| GET    | /api/deliveryslots/available/     | No       | APIView      | All               | Available slots for a date          |
| GET    | /api/deliveryslots/               | Required | ModelViewSet | admin/staff/owner | Full slot template (incl. inactive) |
| POST   | /api/deliveryslots/               | Required | ModelViewSet | admin             | Create slot                         |
| PATCH  | /api/deliveryslots/{id}/          | Required | ModelViewSet | admin/staff/owner | Update capacity or active status    |
| DELETE | /api/deliveryslots/{id}/          | Required | ModelViewSet | admin             | Delete (no orders only)             |
| GET    | /api/deliveryslots/{id}/orders/   | Required | @action      | admin/staff/owner | Orders in this slot on a date       |

**Slot object schema:**

| Field      | Type    | Notes                                                             |
|------------|---------|-------------------------------------------------------------------|
| slot_id    | integer |                                                                   |
| label      | string  | e.g. "10:00 - 10:15"                                             |
| start_time | string  | HH:MM                                                             |
| end_time   | string  | HH:MM                                                             |
| capacity   | integer | Max paid orders per date                                          |
| remaining  | integer | `capacity - COUNT(paid+ orders for slot+date)` — calculated only  |
| active     | boolean | false → hidden from client                                        |

**Key behaviors:**
- `GET /api/slots/available`: annotate `remaining` using `Count` with `filter=Q(orders__state__in=['paid','preparing','ready','collected'])` for the requested date; return only slots where `active=True` and `remaining > 0`
- `remaining` is never stored — always computed at query time
- `perform_destroy`: block if any orders are assigned to the slot (`order_set.exists()`)
- `@action(detail=True, url_path='orders')`: returns orders filtered by `?date=` and belonging to that slot

---

## INSTALLED_APPS Registration

Current state in `config/settings.py`:

```python
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework',
    'apps.allergens',
    'apps.userauth',
    'apps.categories',
    'apps.deliveryslots',
    'apps.inventory',
    'apps.orders',
    'apps.payments',
    'apps.products',
    'apps.userprofile',
]
```

When JWT auth is configured, also add:
```python
    'rest_framework_simplejwt',
    'rest_framework_simplejwt.token_blacklist',
```
