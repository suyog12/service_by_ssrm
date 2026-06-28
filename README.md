# Service by SSRM

A hospitality management platform built for restaurants and hotels. One system for every operational layer — orders, billing, inventory, hotel management, HR, payroll, internal communications, and analytics.

---

## What It Does

Running a restaurant or hotel means managing many moving parts at once. Service by SSRM brings all of them into one place so owners and managers have a clear picture of their business without switching between tools or reconciling data from multiple sources.

**For restaurants:**
Table management, order taking, kitchen tickets, billing with VAT compliance, inventory tracking down to ingredient level, staff scheduling and payroll, and loyalty programs for returning customers.

**For hotels:**
Room management, guest profiles, reservations, check-in and check-out, guest folio with room charges, housekeeping task assignment, and minibar tracking — all connected to the same billing and inventory system.

**For both:**
A role-based team management system so every staff member sees exactly what they need and nothing they should not. An internal communications layer for messaging between team members. And a business intelligence layer that surfaces what is actually happening across the operation.

---

## Who It Is For

Service by SSRM is designed for hospitality businesses that have outgrown basic POS tools and need a proper system — without the complexity and cost of enterprise software built for global hotel chains.

It works for a single restaurant, a hotel with a restaurant, a cafe group with multiple locations, or a resort managing rooms, dining, and staff all under one roof.

---

## Subscription Plans

| Plan | Best For |
|---|---|
| EZ | Single-outlet restaurants focused on orders and billing |
| Pro | Growing restaurants and small hotels needing full operations management |
| Max | Multi-outlet groups and hotels requiring the complete platform |
| Enterprise | Large hospitality groups with custom requirements |

Hotel features, advanced analytics, and multi-outlet management are available on Pro plan and above. All limits and features per plan are configured and adjustable by the platform administrator.

New businesses start with a free trial on the Pro plan. A grace period applies before any account suspension on missed renewal.

---

## Key Features

### Operations
- Table and floor management with real-time status
- Order management for dine-in, takeaway, and room service
- Kitchen order tickets with food and drinks split
- Full billing with VAT, service charge, discounts, and multiple payment methods
- Credit accounts for corporate clients
- Printable VAT-compliant invoices and statements

### Inventory
- Ingredient-level stock tracking with weighted average costing
- Automatic stock deduction when dishes are served
- Purchase orders with full approval and receiving workflow
- Reorder alerts and stock adjustment logs
- Expiry date tracking per batch

### Hotel
- Room type management with seasonal pricing rules
- Guest profiles with corporate account support
- Reservation management with availability checking
- Check-in, check-out, and guest folio with running charges
- Housekeeping task assignment and kit tracking
- Minibar consumption tracking

### HR and Payroll
- Staff shift definitions and attendance tracking
- Leave management with approval workflow
- Payroll processing with SSF and PF scheme support
- Nepal income tax slab support
- Shift handover records

### Team and Communications
- Role-based access control at the feature level
- Per-user permission overrides
- Encrypted internal messaging with direct and group rooms
- Announcement channels
- File sharing, message reactions, read receipts, and presence tracking
- In-app notifications for operational events

### Nepal-Specific
- Bikram Sambat dates alongside AD dates on all financial documents
- VAT at 13% with inclusive and exclusive modes
- PAN and VAT number support on invoices
- eSewa, Khalti, and FonePay payment method support
- Nepal timezone handling throughout

---

## Platform Architecture

Service by SSRM is a multi-tenant SaaS platform. Each business gets a fully isolated environment — no tenant can access another tenant's data. The platform is built on PostgreSQL with a schema-per-tenant architecture, giving each business their own private database schema provisioned automatically on registration.

The backend is built on FastAPI with async PostgreSQL access via asyncpg. File storage runs on Cloudflare R2. Authentication uses JWT with single active session enforcement per user.

---

## Running the Platform Locally

### Requirements

- Python 3.12
- A Supabase project (PostgreSQL)
- A Cloudflare R2 bucket
- conda or any Python virtual environment manager

### Setup

```bash
# Clone the repository
git clone https://github.com/suyog12/service_by_ssrm.git
cd service_by_ssrm/backend

# Create and activate environment
conda create -n CTBA python=3.12
conda activate CTBA

# Install dependencies
pip install -r requirements.txt

# Configure environment variables
cp .env.example .env
# Edit .env and fill in all required values

# Apply database schema
# Open your Supabase SQL Editor and run migration.sql in full

# Start the development server
uvicorn app.main:app --reload
```

The API will be available at `http://localhost:8000`. Interactive documentation is at `http://localhost:8000/docs`.

### Environment Variables

```env
# Database
DB_HOST=
DB_PORT=
DB_USER=
DB_PASSWORD=
DB_NAME=

# Auth
JWT_SECRET_KEY=
JWT_ALGORITHM=HS256
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=30
JWT_REFRESH_TOKEN_EXPIRE_DAYS=7

# App
APP_NAME=Service by SSRM
APP_VERSION=1.0.0
DEBUG=False

# Email
SMTP_HOST=
SMTP_PORT=587
SMTP_USER=
SMTP_PASSWORD=
EMAILS_FROM_EMAIL=

# Encryption
ENCRYPTION_SECRET=

# Cloudflare R2
R2_ACCOUNT_ID=
R2_ACCESS_KEY_ID=
R2_SECRET_ACCESS_KEY=
R2_BUCKET_NAME=
R2_PUBLIC_URL=

# Test mode — disables background scheduler
TESTING=1
```

---

## Running Tests

```bash
cd backend
pytest tests/ -v --tb=short
```

The test suite runs against a live Supabase instance. All 760 tests are integration tests covering the full API surface. CI runs automatically on every push via GitHub Actions and results are delivered by email.

---

## Database

The full schema is in `migration.sql` at the root of the repository. Running it in the Supabase SQL Editor drops and recreates all schemas from scratch and provisions two test tenants used by the test suite.

`migration.sql` is the single source of truth for the database schema.

---

## Related Systems

**Service By SSRM Admin Portal** — A separate internal application used by the SSRM team to manage tenants, subscriptions, payments, onboarding, and platform analytics. In development.

---

## License

Proprietary. All rights reserved. Unauthorized copying, distribution, or use of this software is prohibited.

&copy; 2026 Service by SSRM. All rights reserved.
