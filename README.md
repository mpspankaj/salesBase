# SalesProduct Login System

A Flask and SQLite login/registration starter for a sales management website.

## Run locally

1. Create and activate a virtual environment:

   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```

2. Install dependencies:

   ```powershell
   pip install -r requirements.txt
   ```

3. Set a strong secret key for anything beyond local development:

   ```powershell
   $env:SECRET_KEY = "replace-with-a-long-random-value"
   ```

4. Optional: change the SQLite lock wait timeout. The default is 30 seconds:

   ```powershell
   $env:DATABASE_TIMEOUT = "60"
   ```

5. Start the app:

   ```powershell
   python app.py
   ```

Open <http://127.0.0.1:5000>. The SQLite database (`sales_product.db`) and `users` table are created automatically on startup.

## Included flow

- Register with a unique username, email, and matching 8+ character password.
- Passwords are stored with Werkzeug's secure password hash.
- Log in to reach a session-protected dashboard.
- Use `Forgot password?` to verify username and email, then reset via a one-time 15-minute link.
- Log out to clear the session.
- Use the authenticated `Settings` tab to show or hide the Sales App, Products, and Customers tabs.

For local development, the reset link is shown on the recovery page because no email provider is configured. In production, send that generated link through an email service instead of displaying it in the page.

The navigation preferences are stored in the SQLite `app_settings` table and are initialized automatically with all three workspace tabs enabled. Dashboard and Settings remain available so the navigation can always be restored.

## Product master fields

The product master includes the core commercial and inventory fields: product name, SKU, selling price, product group, category, brand, description, unit of measure, cost price, tax rate, opening stock, reorder level, supplier, barcode, status, and created timestamp. Existing databases are upgraded automatically at startup without deleting existing products.

## Customer master and invoices

The customer master supports list search, configurable pagination, add, edit, and delete. It stores customer name, unique customer code, phone, email, tax ID/GSTIN, billing address, shipping address, city, state, postal code, country, invoice notes, status, and created timestamp for future invoice printing.

## SQLite concurrency

SQLite is initialized in WAL mode automatically. Database connections use a 30-second busy timeout by default (configurable with `DATABASE_TIMEOUT`), and registration write connections commit and close immediately after the insert so they do not hold a write connection open longer than necessary.
