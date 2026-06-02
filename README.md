# Service by SSRM

Nepal-first hospitality ERP SaaS. Replaces POS, HMS, HRMS, inventory, internal comms, and analytics for restaurants and hotels. Multi-tenant, analytics-first, built for Nepal's hospitality context.

---

## Tech Stack

- **Backend**: FastAPI (Python)
- **Database**: PostgreSQL on Supabase
- **Frontend**: Next.js (not started)
- **Auth**: JWT (access + refresh tokens)
- **Email**: SMTP via Python smtplib

---

## Architecture

### Multi-tenancy
One schema per tenant. Global `core` schema holds platform-level data. Each business gets a fully isolated private schema provisioned on registration.

- `core.tenants` — business registry
- `core.users` — platform-level auth
- `core.features` — shared feature registry (43 features)
- `core.refresh_tokens` — JWT refresh token store
- `core.reset_tokens` — password reset token store
- `tenant_{slug}.*` — all operational tables per business

### Tenant provisioning
When a business registers, `core.provision_tenant(schema_name)` creates 60+ tables in their private schema including roles, menu, inventory, floor, orders, billing, HR, expenses, comms, and analytics.

---

## Project Structure
Service By SSRM/
├── README.md
├── migration.sql                    # Full DB migration — run in Supabase SQL Editor
└── backend/
├── pytest.ini
├── requirements.txt
├── conftest.py                  # Root-level Excel reporter hooks
├── .env
├── .env.example
└── app/
├── main.py
├── api/v1/endpoints/
│   ├── auth.py              # Register, login, refresh, logout, change-password,
│   │                        # forgot-password, reset-password, me
│   ├── users.py             # Staff CRUD, assign role, permissions, deactivate
│   ├── roles.py             # Role templates, permissions, feature registry
│   ├── tenants.py           # Tenant profile, onboarding
│   ├── menu.py              # Menu categories and items
│   └── ingredients.py       # Ingredients CRUD + item ingredient linking
├── core/
│   ├── config.py
│   ├── security.py          # JWT create/decode
│   ├── dependencies.py      # get_current_user, get_current_admin, require_permission
│   └── database.py          # asyncpg pool, get_db, get_tenant_db
├── schemas/
│   ├── auth.py
│   ├── user.py
│   ├── tenant.py
│   ├── role.py
│   ├── menu.py
│   └── ingredient.py
├── services/
│   ├── auth_service.py      # login, change_password, refresh, logout,
│   │                        # forgot_password, reset_password
│   ├── tenant_service.py    # register_tenant
│   ├── user_service.py      # create_user, assign_role, update_user, permissions
│   ├── role_service.py      # role templates, permissions
│   ├── menu_service.py      # categories, items
│   └── ingredient_service.py # ingredients, item ingredient linking
└── utils/
├── password.py          # bcrypt hash/verify
└── email.py             # send_welcome_email, send_password_reset_email,
# send_registration_confirmation_email
└── tests/
├── conftest.py              # fixtures: client, db, registered_tenant,
│                            # admin_token, staff_token, admin_token_b, etc.
├── auth/
│   ├── test_register.py
│   ├── test_login.py
│   ├── test_logout.py
│   ├── test_refresh.py
│   ├── test_change_password.py
│   ├── test_me.py
│   └── test_password_reset.py
├── menu/
│   ├── test_categories.py
│   ├── test_items.py
│   └── test_ingredients.py
├── roles/
│   ├── test_features.py
│   ├── test_role_templates.py
│   └── test_permissions.py
├── security/
│   ├── test_jwt_security.py
│   ├── test_password_storage.py
│   └── test_tenant_isolation.py
├── tenants/
│   ├── test_tenant_profile.py
│   └── test_onboarding.py
└── users/
├── test_create_user.py
├── test_list_users.py
├── test_update_user.py
├── test_assign_role.py
├── test_deactivate.py
└── test_user_permissions.py
---

## API Endpoints

### Auth
| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| POST | `/api/v1/auth/register` | None | Register new business + admin |
| POST | `/api/v1/auth/login` | None | Login with email, password, tenant_slug |
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
| GET | `/api/v1/roles/features` | Bearer | List all platform features |
| POST | `/api/v1/roles` | Admin | Create role template |
| GET | `/api/v1/roles` | Admin | List role templates |
| GET | `/api/v1/roles/{id}` | Admin | Get role with permissions |
| PATCH | `/api/v1/roles/{id}` | Admin | Update role |
| DELETE | `/api/v1/roles/{id}` | Admin | Delete role |

### Tenants
| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | `/api/v1/tenants/me` | Admin | Get tenant profile |
| POST | `/api/v1/tenants/me/complete-onboarding` | Admin | Mark onboarding complete |

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
| POST | `/api/v1/ingredients` | Admin | Create ingredient |
| GET | `/api/v1/ingredients` | Bearer | List ingredients |
| GET | `/api/v1/ingredients/{id}` | Bearer | Get ingredient |
| PATCH | `/api/v1/ingredients/{id}` | Admin | Update ingredient |
| DELETE | `/api/v1/ingredients/{id}` | Admin | Delete (blocks if linked to items) |
| POST | `/api/v1/menu/items/{id}/ingredients` | Admin | Link ingredient to menu item |
| GET | `/api/v1/menu/items/{id}/ingredients` | Bearer | List item ingredients |
| PATCH | `/api/v1/menu/items/{id}/ingredients/{ingr_id}` | Admin | Update quantity used |
| DELETE | `/api/v1/menu/items/{id}/ingredients/{ingr_id}` | Admin | Remove ingredient from item |

---

## Database Setup

The full migration is in `migration.sql`. Run the entire file in Supabase SQL Editor to reset and rebuild the database from scratch.

**Key decisions baked into the migration:**
- `core.users` has `is_admin`, `is_super_admin`, `must_change_password` columns
- `menu_items` has `tax_rate` (default 13.00) and `station` (kitchen/bar/grill) columns
- `core.reset_tokens` table for password reset flow
- `statement_cache_size=0` set in `database.py` for PgBouncer compatibility on CI

---

## Running Tests

```bash
cd backend
pytest tests/ -v --tb=short
```

Test results are saved as Excel files in the backend directory.

**Current test count: 175 passing**

| Module | Tests |
|--------|-------|
| Auth + Password Reset | 58 |
| Menu Categories + Items | 40 |
| Ingredients + Item Linking | 19 |
| Roles + Permissions | 23 |
| Security | 9 |
| Tenants | 6 |
| Users | 20 |
| **Total** | **175** |

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

---

## CI/CD

GitHub Actions runs the full test suite on every push to `main` or `develop`. Results are emailed as an Excel report.

Secrets required in GitHub: `DB_HOST`, `DB_PORT`, `DB_USER`, `DB_PASSWORD`, `DB_NAME`, `JWT_SECRET_KEY`, `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `EMAILS_FROM_EMAIL`.

---

## What Is Next

- Tables and sections (floor management)
- Orders module
- Billing
- Inventory stock management
- Hotel module
- HR and payroll
- Expenses
- Analytics
- Internal communications
- Frontend (Next.js)