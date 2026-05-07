# Cafeteria Backend — Project Definition

Django REST Framework backend for the school cafeteria ordering system. Designed by Jonathan & Andrea.

## Architecture

```
CafeteriaBackend/
├── config/          # Django project settings, URLs, WSGI/ASGI
├── apps/            # Django apps, one per domain concept
│   ├── auth/        # Authentication (Google SSO + in-house)
│   ├── userprofile/ # User profile management
│   ├── products/    # Product catalog
│   ├── categories/  # Product categories
│   ├── allergens/   # Allergen catalog
│   ├── orders/      # Order lifecycle
│   ├── payments/    # Redsys payment gateway
│   ├── inventory/   # Stock management
│   └── deliveryslots/ # Pickup time slots
└── manage.py
```

## Roles

| Role    | Description                                      |
|---------|--------------------------------------------------|
| client  | Regular user. Can browse, order, view own orders |
| staff   | Cafeteria staff. Manages orders and inventory    |
| admin   | Full access. Manages users, products, categories |

## Standard Response Format

```json
{ "status": "00", "data": { ... } }
```

Error format:
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

## App: `auth`

Handles user authentication via Google SSO and in-house email/password. Issues JWT session tokens.

**Endpoints:**

| Method | Route                              | Auth     | Description                        |
|--------|------------------------------------|----------|------------------------------------|
| POST   | /api/auth/google                   | No       | Validate Google token, return JWT  |
| POST   | /api/auth/login                    | No       | In-house login                     |
| POST   | /api/auth/register                 | No       | Register new user                  |
| GET    | /api/user/email-otp                | Required | Send OTP to verify email           |
| POST   | /api/user/email-verification       | Required | Confirm OTP, verify email          |
| POST   | /api/auth/password-recovery        | No       | Start password reset (send OTP)    |
| POST   | /api/auth/password-recovery/confirm| No       | Confirm OTP and set new password   |
| POST   | /api/auth/logout                   | Required | Invalidate session token           |

**Key behaviors:**
- Google SSO: frontend sends Google ID Token → backend validates with Google → creates/retrieves user → returns own JWT
- In-house register: user is created partially → OTP sent to email → account active after verification
- Password recovery always returns success even if email is not found (security: no account enumeration)
- Logout supports token blacklist for stateless JWT revocation

---

## App: `userprofile`

Manages the authenticated user's own profile data. Separate from `auth`: auth handles access, userprofile handles personal data.

**Endpoints:**

| Method | Route                  | Auth     | Roles        | Description                             |
|--------|------------------------|----------|--------------|-----------------------------------------|
| GET    | /api/user/me           | Required | All          | Get own profile                         |
| PATCH  | /api/user/me           | Required | All          | Update name or avatar                   |
| PATCH  | /api/user/me/password  | Required | in-house only| Change password (not available for Google users) |
| PATCH  | /api/user/me/deactivate| Required | All          | Deactivate own account                  |

**User object schema:**

| Field          | Type    | Notes                                |
|----------------|---------|--------------------------------------|
| user_id        | string  | UUID                                 |
| name           | string  |                                      |
| email          | string  | Not editable directly                |
| avatar         | string  | URL or base64                        |
| auth_provider  | string  | `google` or `inhouse`                |
| email_verified | boolean |                                      |
| active         | boolean | false blocks login                   |
| role           | string  | `client`, `staff`, or `admin`        |
| created_at     | string  | ISO 8601                             |

**Key behaviors:**
- Email is not editable via PATCH /api/user/me — requires OTP verification flow
- Google users cannot use the change-password endpoint
- Deactivated accounts keep order history; only admin can reactivate
- Deactivating immediately invalidates the current token

---

## App: `products`

Exposes the cafeteria product catalog. Clients browse it; admins/staff manage it.

**Endpoints:**

| Method | Route               | Auth     | Roles              | Description                     |
|--------|---------------------|----------|--------------------|---------------------------------|
| GET    | /api/products/      | No       | All                | List products (filterable)      |
| GET    | /api/products/{id}/ | No       | All                | Product detail                  |
| POST   | /api/products/      | Required | admin              | Create product                  |
| PATCH  | /api/products/{id}/ | Required | admin/staff/owner  | Update product fields           |
| DELETE | /api/products/{id}/ | Required | admin/staff/owner  | Delete product                  |

**Query params (GET /api/products/):** `?category=1&allergen=1&search=bocadillo`

**Product object schema:**

| Field       | Type    | Notes                                             |
|-------------|---------|---------------------------------------------------|
| id          | string  |                                                   |
| name        | string  |                                                   |
| description | string  |                                                   |
| price       | decimal |                                                   |
| category    | object  | `{ category_id, name }` — never a plain string    |
| allergens   | array   | Array of `{ allergen_id, name, icon }` in GET; array of IDs in POST/PATCH |
| image       | string  | URL                                               |
| available   | boolean | Can be toggled without deleting the product       |
| stock       | integer |                                                   |

**Key behaviors:**
- `category` and `allergens` are foreign-key relations, never free strings
- Logical delete (marking `available: false`) preferred over physical delete to preserve order history
- Stock hits 0 → backend automatically sets `available: false`

---

## App: `categories`

Organizes products into groups (bebidas, bocadillos, dulces…).

**Endpoints:**

| Method | Route                      | Auth     | Roles | Description               |
|--------|----------------------------|----------|-------|---------------------------|
| GET    | /api/categories/           | No       | All   | List active categories    |
| GET    | /api/categories/{id}/      | No       | All   | Category detail           |
| POST   | /api/categories/           | Required | admin | Create category           |
| PATCH  | /api/categories/{id}/      | Required | admin | Update category           |
| DELETE | /api/categories/{id}/      | Required | admin | Delete (no products only) |

**Category object schema:**

| Field         | Type    | Notes                                        |
|---------------|---------|----------------------------------------------|
| category_id   | string  |                                              |
| name          | string  | e.g. "Bebidas"                               |
| image         | string  | URL or base64                                |
| active        | boolean | false → hidden from client catalog and filters |
| product_count | integer | Calculated field                             |

**Key behaviors:**
- Physical delete blocked if category has associated products → HTTP 422 with count
- Deactivating a category hides all its products from the client catalog
- Products reference category by `category_id`, never by name string

---

## App: `allergens`

Manages the allergen catalog associated with products.

**Endpoints:**

| Method | Route                     | Auth     | Roles | Description                   |
|--------|---------------------------|----------|-------|-------------------------------|
| GET    | /api/allergens/           | No       | All   | List all allergens             |
| POST   | /api/allergens/           | Required | admin | Create allergen               |
| PATCH  | /api/allergens/{id}/      | Required | admin | Update allergen               |
| DELETE | /api/allergens/{id}/      | Required | admin | Delete (no products only)     |

**Allergen object schema:**

| Field       | Type   | Notes                       |
|-------------|--------|-----------------------------|
| allergen_id | string |                             |
| name        | string | e.g. "Gluten"               |
| icon        | string | URL or base64               |

**Key behaviors:**
- Physical delete blocked if allergen is associated to any product → HTTP 422 with count
- Updating name/icon propagates automatically to all associated products (FK relation)
- Products send `"allergens": [1, 3, 5]` (array of IDs) on write; receive full objects on read

---

## App: `orders`

Manages the full lifecycle of a purchase: from cart confirmation to pickup.

**Order states:**

| State      | Description                                  |
|------------|----------------------------------------------|
| pending    | Order created, awaiting payment              |
| paid       | Payment confirmed by Redsys (via webhook)    |
| preparing  | Cafeteria is preparing the order             |
| ready      | Order ready for pickup                       |
| collected  | Customer collected the order                 |
| cancelled  | Cancelled (failed payment or manual cancel)  |

**Endpoints:**

| Method | Route              | Auth     | Roles              | Description                          |
|--------|--------------------|----------|--------------------|--------------------------------------|
| POST   | /api/orders/       | Required | client             | Create order from cart               |
| GET    | /api/orders/       | Required | client             | Own order history (paginated)        |
| GET    | /api/orders/{id}/  | Required | client             | Own order detail                     |
| PATCH  | /api/orders/{id}/  | Required | admin/staff/owner  | Advance order state manually         |
| GET    | /api/orders/all/   | Required | admin/staff/owner  | All orders (staff queue management)  |

**Key behaviors:**
- Backend validates stock and availability on order creation
- State `paid` is set exclusively by the Redsys webhook — staff cannot set it manually
- A unique `pickup_code` is generated after payment is confirmed
- `pending` orders do not consume slot capacity — only `paid` or higher states do
- POST body includes `slot_id` and `items: [{ product_id, quantity }]`
- Staff can filter GET /api/orders/all/ by state and pickup time slot

---

## App: `payments`

Integrates with Redsys (Spanish bank TPV virtual) for prepayment. Clients pay before picking up.

**Endpoints:**

| Method | Route                              | Auth          | Description                             |
|--------|------------------------------------|---------------|-----------------------------------------|
| POST   | /api/payments/                     | Required (client) | Generate signed Redsys parameters    |
| POST   | /api/payments/redsys/notification/ | None (HMAC)   | Redsys webhook receiver                 |
| GET    | /api/payments/{order_id}/          | Required (client) | Poll payment status (fallback)       |

**Key behaviors:**
- POST /api/payments/ returns `Ds_MerchantParameters`, `Ds_Signature`, `Ds_SignatureVersion` for frontend TPV redirect
- Webhook authenticates via HMAC_SHA256 signature — NOT a session token
- Redsys response codes `0000–0099` → payment successful → order set to `paid` + pickup code generated
- Any other code → payment failed → order set to `cancelled`
- Frontend polls GET /api/payments/{order_id}/ after redirect back from Redsys to confirm result
- Webhook URL must be registered in the Redsys merchant panel

---

## App: `inventory`

Operational stock management for staff. Separate from the public product catalog.

**Endpoints:**

| Method | Route                        | Auth     | Roles             | Description                          |
|--------|------------------------------|----------|-------------------|--------------------------------------|
| GET    | /api/inventory/              | Required | admin/staff/owner | Full inventory list                  |
| GET    | /api/inventory/{product_id}/ | Required | admin/staff/owner | Single product stock detail          |
| PATCH  | /api/inventory/{product_id}/ | Required | admin/staff/owner | Update stock, threshold, availability|
| GET    | /api/inventory/alerts/       | Required | admin/staff/owner | Products below low_stock_threshold   |

**Query params (GET /api/inventory/):** `?available=false&category=bebidas&low_stock=true`

**Inventory item schema:**

| Field               | Type    | Notes                                          |
|---------------------|---------|------------------------------------------------|
| product_id          | string  |                                                |
| name                | string  |                                                |
| category            | string  |                                                |
| stock               | integer |                                                |
| low_stock_threshold | integer | Alert triggers when stock < threshold          |
| available           | boolean |                                                |
| last_updated        | string  | ISO 8601 (detail only)                         |

**Key behaviors:**
- Unlike public catalog, inventory shows ALL products including unavailable ones
- Stock reaches 0 → backend automatically sets `available: false`
- Stock decrements automatically when Redsys confirms payment
- Alerts endpoint (`/api/inventory/alerts/`) for proactive restock management

---

## App: `deliveryslots`

Manages weekly pickup time slot templates configured by the admin.

**Endpoints:**

| Method | Route                          | Auth     | Roles             | Description                           |
|--------|--------------------------------|----------|-------------------|---------------------------------------|
| GET    | /api/slots/available           | No       | All               | Available slots for a date            |
| GET    | /api/slots/                    | Required | admin/staff/owner | Full slot template (incl. inactive)   |
| POST   | /api/slots/                    | Required | admin             | Create slot                           |
| PATCH  | /api/slots/{slot_id}/          | Required | admin/staff/owner | Update capacity or active status      |
| DELETE | /api/slots/{slot_id}/          | Required | admin             | Delete (only if no assigned orders)   |
| GET    | /api/slots/{slot_id}/orders/   | Required | admin/staff/owner | Orders assigned to a slot on a date   |

**Query params:**
- GET /api/slots/available: `?date=2025-04-28` (default: today)
- GET /api/slots/{slot_id}/orders/: `?date=2025-04-28`

**Slot object schema:**

| Field     | Type    | Notes                                                  |
|-----------|---------|--------------------------------------------------------|
| slot_id   | string  |                                                        |
| label     | string  | Human-readable, e.g. "10:00 - 10:15"                  |
| start_time| string  | HH:MM                                                  |
| end_time  | string  | HH:MM                                                  |
| capacity  | integer | Max orders allowed in this slot                        |
| remaining | integer | Calculated: `capacity - COUNT(paid orders for slot+date)` — NOT stored |
| active    | boolean | false → hidden from client                             |

**Key behaviors:**
- `remaining` is always calculated at query time, never stored — avoids sync issues
- Only `paid` (or higher) orders count against slot capacity; `pending` orders do not
- Deleting a slot is blocked if it has assigned orders → use PATCH to deactivate instead
- Deactivating a slot does not affect already-assigned orders
- Order creation validates: slot must be active, date must not be past, remaining > 0

---

## Admin: User Management

Handled via the `auth` / `userprofile` apps but exposed under `/api/admin/`.

| Method | Route                          | Auth     | Roles | Description               |
|--------|--------------------------------|----------|-------|---------------------------|
| GET    | /api/admin/users               | Required | admin | List and search all users |
| PATCH  | /api/admin/users/{user_id}/role| Required | admin | Change user role          |

**Query params (GET /api/admin/users):** `?search=jonathan&page=2`

**Key behaviors:**
- Staff cannot change their own role or others' roles — only admin/owner
- Response includes pagination metadata: `{ total, page, last_page }`

---

## URL Registration Convention

Add each app under `config/urls.py` following the existing pattern:

```python
path('api/allergens/', include('apps.allergens.urls')),
path('api/products/', include('apps.products.urls')),
path('api/categories/', include('apps.categories.urls')),
path('api/orders/', include('apps.orders.urls')),
path('api/payments/', include('apps.payments.urls')),
path('api/inventory/', include('apps.inventory.urls')),
path('api/slots/', include('apps.deliveryslots.urls')),
path('api/auth/', include('apps.auth.urls')),
path('api/user/', include('apps.userprofile.urls')),
path('api/admin/', include('apps.userprofile.urls')),  # admin user mgmt
```

Register each app in `INSTALLED_APPS` inside `config/settings.py`:

```python
'apps.allergens',
'apps.auth',
'apps.categories',
'apps.deliveryslots',
'apps.inventory',
'apps.orders',
'apps.payments',
'apps.products',
'apps.userprofile',
```
