# Service by SSRM

Nepal-first hospitality ERP SaaS. Replaces POS, HMS, HRMS, inventory, internal comms, and analytics for restaurants and hotels. Multi-tenant, analytics-first, built for Nepal's hospitality context.

---

## Tech Stack

- **Backend**: FastAPI (Python)
- **Database**: PostgreSQL on Supabase
- **Frontend**: Next.js (not started)
- **Auth**: JWT (access + refresh tokens), single active session per user
- **Email**: SMTP via Python smtplib
- **Dates**: AD/BS dual-date support via `nepali-datetime`

---

## Architecture

### Multi-tenancy
One schema per tenant. Global `core` schema holds platform-level data. Each business gets a fully isolated private schema provisioned on registration.

- `core.tenants` — business registry
- `core.users` — platform-level auth
- `core.features` — shared feature registry (50 features)
- `core.refresh_tokens` — JWT refresh token store (single active session enforced)
- `core.reset_tokens` — password reset token store
- `tenant_{slug}.*` — all operational tables per business (74 tables)

### Tenant provisioning
When a business registers, `core.provision_tenant(schema_name)` creates 74 tables in their private schema including outlets, roles, menu, inventory, floor, orders, billing, hotel, customers, HR, expenses, comms, and analytics. A default outlet and its billing settings are auto-created on registration.

### Outlets
Every tenant has one or more outlets (restaurant, bar, cafe, hotel, banquet, other). The first outlet is marked `is_default`. Menu, inventory, floor, orders, and billing are all scoped per outlet.

### BS/AD dual dates
All date fields on bills, purchase orders, and hotel reservations return a companion `_bs` field with the Bikram Sambat equivalent (e.g. `created_at` and `created_at_bs`).

---

## Project Structure

```
Service By SSRM/
├── README.md
├── migration.sql
└── backend/
    ├── pytest.ini
    ├── requirements.txt
    ├── .env
    ├── .env.example
    └── app/
        ├── main.py
        ├── api/v1/endpoints/
        │   ├── auth.py
        │   ├── users.py
        │   ├── roles.py
        │   ├── tenants.py
        │   ├── menu.py
        │   ├── ingredients.py
        │   ├── floor.py
        │   ├── orders.py
        │   ├── kot.py
        │   ├── billing.py
        │   ├── inventory.py
        │   ├── outlets.py
        │   └── hotel.py
        ├── core/
        │   ├── config.py
        │   ├── security.py
        │   ├── dependencies.py
        │   └── database.py
        ├── schemas/
        │   ├── auth.py
        │   ├── user.py
        │   ├── tenant.py
        │   ├── role.py
        │   ├── menu.py
        │   ├── ingredient.py
        │   ├── floor.py
        │   ├── order.py
        │   ├── kot.py
        │   ├── billing.py
        │   ├── inventory.py
        │   ├── outlet.py
        │   └── hotel.py
        ├── services/
        │   ├── auth_service.py
        │   ├── tenant_service.py
        │   ├── user_service.py
        │   ├── role_service.py
        │   ├── menu_service.py
        │   ├── ingredient_service.py
        │   ├── floor_service.py
        │   ├── order_service.py
        │   ├── kot_service.py
        │   ├── billing_service.py
        │   ├── inventory_service.py
        │   ├── outlet_service.py
        │   └── hotel_service.py
        └── utils/
            ├── password.py
            ├── email.py
            └── nepali_date.py

        └── tests/
            ├── conftest.py
            ├── auth/
            ├── menu/
            ├── roles/
            ├── security/
            ├── tenants/
            ├── users/
            ├── floor/
            ├── orders/
            ├── billing/
            ├── inventory/
            └── hotel/
```

## API Endpoints

### Auth
| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| POST | `/api/v1/auth/register` | None | Register new business + admin (auto-creates default outlet) |
| POST | `/api/v1/auth/login` | None | Login with email, password, tenant_slug (revokes prior sessions) |
| POST | `/api/v1/auth/refresh` | None | Refresh access token |
| POST | `/api/v1/auth/logout` | Bearer | Revoke refresh token |
| POST | `/api/v1/auth/change-password` | Bearer | Change password (clears must_change_password) |
| POST | `/api/v1/auth/forgot-password` | None | Request password reset email |
| POST | `/api/v1/auth/reset-password` | None | Reset password with token |
| GET | `/api/v1/auth/me` | Bearer | Get current user info |

### Users
| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| POST | `/api/v1/users` | Admin | Create staff account |
| GET | `/api/v1/users` | Admin | List all staff |
| GET | `/api/v1/users/me` | Bearer | Get own profile |
| PATCH | `/api/v1/users/{id}` | Admin | Update staff profile |
| PATCH | `/api/v1/users/{id}/deactivate` | Admin | Deactivate staff |
| PATCH | `/api/v1/users/{id}/reactivate` | Admin | Reactivate staff |
| POST | `/api/v1/users/assign-role` | Admin | Assign role template to user |
| POST | `/api/v1/users/permissions` | Admin | Set permission override |
| GET | `/api/v1/users/{id}/permissions` | Admin | Get user permissions |

### Roles
| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | `/api/v1/roles/features` | Bearer | List all platform features (50) |
| POST | `/api/v1/roles` | Admin | Create role template with permissions |
| GET | `/api/v1/roles` | Admin | List role templates |
| GET | `/api/v1/roles/{id}` | Admin | Get role with permissions |
| PATCH | `/api/v1/roles/{id}` | Admin | Update role |
| DELETE | `/api/v1/roles/{id}` | Admin | Delete role |

> Role permission storage (`role_permissions`, `user_permission_overrides`) is fully built but not yet enforced at the API layer — see "What Is Next".

### Tenants
| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | `/api/v1/tenants/me` | Admin | Get tenant profile |
| POST | `/api/v1/tenants/me/complete-onboarding` | Admin | Mark onboarding complete |

### Outlets
| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| POST | `/api/v1/outlets` | Admin | Create outlet |
| GET | `/api/v1/outlets` | Bearer | List outlets |
| GET | `/api/v1/outlets/{id}` | Bearer | Get outlet |
| PATCH | `/api/v1/outlets/{id}` | Admin | Update outlet (name, kitchen mode, active status) |

### Menu
| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| POST | `/api/v1/menu/categories` | Admin | Create category |
| GET | `/api/v1/menu/categories` | Bearer | List categories |
| PATCH | `/api/v1/menu/categories/{id}` | Admin | Update category |
| DELETE | `/api/v1/menu/categories/{id}` | Admin | Delete category (blocks if items exist) |
| POST | `/api/v1/menu/items` | Admin | Create menu item |
| GET | `/api/v1/menu/items` | Bearer | List items (optional ?category_id filter) |
| GET | `/api/v1/menu/items/{id}` | Bearer | Get single item |
| PATCH | `/api/v1/menu/items/{id}` | Admin | Update item |
| DELETE | `/api/v1/menu/items/{id}` | Admin | Delete item |

### Ingredients
| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| POST | `/api/v1/ingredients` | Admin | Create ingredient (with category: food/beverage/housekeeping/minibar/amenity/banquet/maintenance/other) |
| GET | `/api/v1/ingredients` | Bearer | List ingredients |
| GET | `/api/v1/ingredients/{id}` | Bearer | Get ingredient |
| PATCH | `/api/v1/ingredients/{id}` | Admin | Update ingredient |
| DELETE | `/api/v1/ingredients/{id}` | Admin | Delete (blocks if linked to items) |
| POST | `/api/v1/menu/items/{id}/ingredients` | Admin | Link ingredient to menu item |
| GET | `/api/v1/menu/items/{id}/ingredients` | Bearer | List item ingredients |
| PATCH | `/api/v1/menu/items/{id}/ingredients/{ingr_id}` | Admin | Update quantity used |
| DELETE | `/api/v1/menu/items/{id}/ingredients/{ingr_id}` | Admin | Remove ingredient from item |

### Floor
| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| POST | `/api/v1/floor/sections` | Admin | Create section |
| GET | `/api/v1/floor/sections` | Bearer | List sections |
| PATCH | `/api/v1/floor/sections/{id}` | Admin | Update section |
| DELETE | `/api/v1/floor/sections/{id}` | Admin | Delete section (blocks if tables exist) |
| POST | `/api/v1/floor/tables` | Admin | Create table |
| GET | `/api/v1/floor/tables` | Bearer | List tables (optional ?section_id filter) |
| GET | `/api/v1/floor/tables/{id}` | Bearer | Get single table |
| PATCH | `/api/v1/floor/tables/{id}` | Bearer | Update table status/section/capacity |
| DELETE | `/api/v1/floor/tables/{id}` | Admin | Delete table (blocks if occupied) |

### Orders & KOT
| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| POST | `/api/v1/orders` | Bearer | Create order (dine_in/takeaway/room_service) |
| GET | `/api/v1/orders` | Bearer | List orders (optional ?status filter) |
| GET | `/api/v1/orders/{id}` | Bearer | Get single order |
| PATCH | `/api/v1/orders/{id}/status` | Bearer | Update order status |
| POST | `/api/v1/orders/{id}/items` | Bearer | Add item to order |
| GET | `/api/v1/orders/{id}/items` | Bearer | List order items |
| PATCH | `/api/v1/orders/{id}/items/{item_id}/status` | Bearer | Update item status (deducts stock on served) |
| DELETE | `/api/v1/orders/{id}/items/{item_id}` | Bearer | Cancel order item |
| POST | `/api/v1/orders/{id}/kot` | Bearer | Generate KOTs (food/drinks split) |
| GET | `/api/v1/kots/pending` | Bearer | List pending KOTs |
| PATCH | `/api/v1/kots/{id}/assign` | Bearer | Assign KOT to chef |
| PATCH | `/api/v1/kots/{id}/print` | Bearer | Mark KOT printed |
| GET | `/api/v1/kots/{id}/html` | Bearer | Get printable KOT HTML |

### Billing
| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | `/api/v1/billing/settings` | Bearer | Get billing settings (VAT, service charge, QR) |
| PATCH | `/api/v1/billing/settings` | Admin | Update billing settings |
| POST | `/api/v1/billing/bills` | Bearer | Generate bill from order |
| GET | `/api/v1/billing/bills` | Bearer | List bills (optional ?status filter), includes `created_at_bs` |
| GET | `/api/v1/billing/bills/{id}` | Bearer | Get bill |
| POST | `/api/v1/billing/bills/{id}/discount` | Bearer | Apply bill/category/item discount |
| POST | `/api/v1/billing/bills/{id}/payment` | Bearer | Process payment (cash/card/esewa/khalti/fonepay/credit_account/room_charge) |
| POST | `/api/v1/billing/bills/{id}/void` | Bearer | Void an unpaid bill |
| GET | `/api/v1/billing/bills/{id}/html` | Bearer | Printable bill HTML with VAT/PAN |
| POST | `/api/v1/billing/credit-accounts` | Bearer | Create credit account (individual/corporate) |
| GET | `/api/v1/billing/credit-accounts` | Bearer | List credit accounts |
| GET | `/api/v1/billing/credit-accounts/{id}` | Bearer | Get credit account |
| PATCH | `/api/v1/billing/credit-accounts/{id}` | Bearer | Update credit account |
| POST | `/api/v1/billing/credit-accounts/{id}/settle` | Bearer | Settle outstanding balance |
| GET | `/api/v1/billing/credit-accounts/{id}/statement` | Bearer | Printable statement HTML |

**Payment method `room_charge`** posts the bill total to the linked hotel reservation's guest folio and sets bill status to `room_charge_posted`.

**Customer visit tracking** — when a bill is marked `paid` or `room_charge_posted` and has a `customer_id`, `total_visits` and `total_spent` on the customer record are updated automatically.

### Inventory
| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| POST | `/api/v1/inventory/suppliers` | Admin | Create supplier |
| GET | `/api/v1/inventory/suppliers` | Bearer | List suppliers |
| GET | `/api/v1/inventory/suppliers/{id}` | Bearer | Get supplier |
| PATCH | `/api/v1/inventory/suppliers/{id}` | Admin | Update supplier |
| POST | `/api/v1/inventory/stock/add` | Bearer | Add stock (creates batch, updates cost) |
| POST | `/api/v1/inventory/stock/adjust` | Bearer | Manually adjust stock with reason |
| GET | `/api/v1/inventory/stock/adjustments` | Bearer | List stock adjustments |
| GET | `/api/v1/inventory/stock/reorder-alerts` | Bearer | List ingredients at/below reorder level |
| POST | `/api/v1/inventory/purchase-orders` | Bearer | Create PO (auto-numbered `PO-YYYY-NNN`) |
| GET | `/api/v1/inventory/purchase-orders` | Bearer | List POs (optional ?status filter), includes `created_at_bs` |
| GET | `/api/v1/inventory/purchase-orders/{id}` | Bearer | Get PO with items |
| PATCH | `/api/v1/inventory/purchase-orders/{id}/status` | Bearer | Transition PO status |
| POST | `/api/v1/inventory/purchase-orders/{id}/items` | Bearer | Add item to draft PO |
| POST | `/api/v1/inventory/purchase-orders/{id}/receive` | Bearer | Receive items, update stock |

### Hotel
| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| POST | `/api/v1/hotel/room-types` | Admin | Create room type |
| GET | `/api/v1/hotel/room-types` | Bearer | List room types (optional ?active_only) |
| GET | `/api/v1/hotel/room-types/{id}` | Bearer | Get room type |
| PATCH | `/api/v1/hotel/room-types/{id}` | Admin | Update room type |
| DELETE | `/api/v1/hotel/room-types/{id}` | Admin | Delete (blocks if rooms exist) |
| GET | `/api/v1/hotel/room-types/{id}/share-card` | Bearer | Shareable room card with availability |
| POST | `/api/v1/hotel/room-types/{id}/pricing-rules` | Admin | Add seasonal/day pricing rule |
| GET | `/api/v1/hotel/room-types/{id}/pricing-rules` | Bearer | List pricing rules |
| DELETE | `/api/v1/hotel/pricing-rules/{id}` | Admin | Delete pricing rule |
| POST | `/api/v1/hotel/rooms` | Admin | Create room |
| GET | `/api/v1/hotel/rooms` | Bearer | List rooms (optional ?room_type_id, ?status) |
| GET | `/api/v1/hotel/rooms/availability` | Bearer | Check availability by date range/occupancy |
| GET | `/api/v1/hotel/rooms/{id}` | Bearer | Get room |
| PATCH | `/api/v1/hotel/rooms/{id}` | Admin | Update room (status, type, floor) |
| DELETE | `/api/v1/hotel/rooms/{id}` | Admin | Delete room (blocks if reserved/active) |
| POST | `/api/v1/hotel/guests` | Bearer | Create guest profile |
| GET | `/api/v1/hotel/guests` | Bearer | List/search guests |
| GET | `/api/v1/hotel/guests/{id}` | Bearer | Get guest |
| PATCH | `/api/v1/hotel/guests/{id}` | Bearer | Update guest |
| POST | `/api/v1/hotel/reservations` | Bearer | Create reservation (AD+BS dates returned) |
| GET | `/api/v1/hotel/reservations` | Bearer | List reservations (optional ?status, ?guest_id) |
| GET | `/api/v1/hotel/reservations/{id}` | Bearer | Get reservation |
| PATCH | `/api/v1/hotel/reservations/{id}` | Bearer | Update reservation |
| POST | `/api/v1/hotel/reservations/{id}/cancel` | Bearer | Cancel confirmed reservation |
| POST | `/api/v1/hotel/reservations/{id}/check-in` | Bearer | Check in (creates initial folio entry) |
| POST | `/api/v1/hotel/reservations/{id}/check-out` | Bearer | Check out (totals folio, frees room) |
| GET | `/api/v1/hotel/reservations/{id}/folio` | Bearer | Get guest folio with running total |
| POST | `/api/v1/hotel/reservations/{id}/folio/charges` | Bearer | Add charge to folio |

---

## Database Setup

The full migration is in `migration.sql`. Run the entire file in Supabase SQL Editor to reset and rebuild the database from scratch. The migration drops all schemas (including test tenant schemas) before recreating, then provisions two test tenants.

**Key decisions baked into the migration:**
- `core.users` has `is_admin`, `is_super_admin`, `must_change_password` columns
- `core.tenants` has `pan_number`, `vat_registered`, `vat_number`, `calendar_preference` (BS/AD/BOTH)
- `menu_items` has `tax_rate` (default 13.00) and `station` (kitchen/bar/grill) columns
- `ingredients` has `category` (food/beverage/housekeeping/minibar/amenity/banquet/maintenance/other)
- `outlets` table with `is_default` flag, auto-created on tenant registration along with `billing_settings`
- Full hotel schema: `room_types`, `room_type_minibar`, `room_type_housekeeping_kit`, `pricing_rules`, `rooms`, `guests`, `hotel_reservations`, `guest_folio`, `room_charges`, `housekeeping_tasks`
- Customer profile tables: `customers`, `customer_preferences`, `customer_visit_notes`, `loyalty_accounts`, `loyalty_transactions`
- `bills.status` includes `room_charge_posted`
- `core.reset_tokens` table for password reset flow
- `statement_cache_size=0` set in `database.py` for PgBouncer compatibility on CI
- 50 features in `core.features`, 74 tables per tenant schema

---

## Running Tests

```bash
cd backend
pytest tests/ -v --tb=short
```

Test results are saved as Excel files in the backend directory. Full run takes 25-35 minutes; occasional `WinError 121` semaphore timeouts on Windows after long runs are environment issues, not code bugs.

**Current test count: 411 passing**

| Module | Tests |
|--------|-------|
| Auth + Password Reset | 58 |
| Menu Categories + Items | 40 |
| Ingredients + Item Linking | 19 |
| Roles + Permissions | 23 |
| Security | 9 |
| Tenants | 6 |
| Users | 20 |
| Floor (Sections + Tables) | 33 |
| Orders + Order Items + KOT | 43 |
| Billing + Credit Accounts | 27 |
| Inventory (Suppliers, Stock, POs) | 39 |
| Outlets | 18 |
| Hotel (Room Types, Rooms, Guests, Reservations) | 66 |
| **Total** | **411** |

---

## Environment Variables

```env
DB_HOST=
DB_PORT=
DB_USER=
DB_PASSWORD=
DB_NAME=

JWT_SECRET_KEY=
JWT_ALGORITHM=
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=
JWT_REFRESH_TOKEN_EXPIRE_DAYS=

APP_NAME=
APP_VERSION=
DEBUG=

SMTP_HOST=
SMTP_PORT=
SMTP_USER=
SMTP_PASSWORD=
EMAILS_FROM_EMAIL=
```

**Additional dependency:** `pip install nepali-datetime` (BS/AD date conversion).

---

## CI/CD

GitHub Actions runs the full test suite on every push to `main` or `develop`. Results are emailed as an Excel report to `mainalisuyog0@gmail.com`.

Secrets required in GitHub: `DB_HOST`, `DB_PORT`, `DB_USER`, `DB_PASSWORD`, `DB_NAME`, `JWT_SECRET_KEY`, `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `EMAILS_FROM_EMAIL`.

---

## What Is Next

**Critical — feature gating (session 2):**
- Add `require_feature(feature_code, level)` dependency checking `role_permissions` and `user_permission_overrides`
- Apply to 89 of 118 endpoints
- Subscription tier gating (EZ plan blocks hotel module etc.)
- Update `staff_token` fixture to assign a role with appropriate permissions

**Other backend gaps:**
- Table reservations for restaurants (`table_reservations` table exists, no endpoints)
- Menu offers and happy hours (`menu_offers` table exists, no endpoints)
- Combo items (`combo_items` table exists, no endpoints)
- Loyalty program endpoints (`loyalty_accounts`/`loyalty_transactions` tables exist, no endpoints)
- Internal communications (chat rooms, messages, announcements — schema exists, no endpoints)
- Housekeeping task management and minibar consumption tracking
- HR module (shifts, attendance, leave, payroll, shift handovers)
- Expenses module (categories, logs, petty cash, cash register)
- Analytics module (daily snapshots, IRD reports, occupancy, staff performance)
- Reorder alert → notification row creation
- Discount approval workflow enforcement

**Separate/future:**
- live payment gateway integration
- Print agent (Raspberry Pi + thermal printer)
- Frontend (Next.js) — not started