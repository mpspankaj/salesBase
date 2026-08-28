import sqlite3
import unittest
from uuid import uuid4

from app import app, validate_customer_payload


class CustomerManagementTests(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()
        with self.client.session_transaction() as current_session:
            current_session["user_id"] = 1

    def test_customer_validation_requires_invoice_identity_and_billing(self):
        errors = validate_customer_payload({})
        self.assertIn("Customer name is required.", errors)
        self.assertIn("Customer code is required.", errors)
        self.assertIn("Phone number is required.", errors)
        self.assertIn("Billing address is required.", errors)
        self.assertIn("Country is required.", errors)
        self.assertIn("Phone number format is invalid.", validate_customer_payload({
            "name": "Customer", "customer_code": "CUST-1", "phone": "-------",
            "billing_address": "Address", "country": "India"
        }))

    def test_customer_add_validation_and_form_state(self):
        response = self.client.post(
            "/customers/new",
            data={"name": "Acme Retail", "customer_code": "", "phone": "9876543210", "billing_address": "12 Main Road", "country": "India"},
        )
        html = response.get_data(as_text=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn('value="Acme Retail"', html)
        self.assertIn("Customer code is required.", html)

    def test_customer_list_edit_and_delete(self):
        code = f"TEST-{uuid4().hex[:10]}"
        with sqlite3.connect(app.config["DATABASE"]) as db:
            cursor = db.execute(
                "INSERT INTO customers (name, customer_code, phone, billing_address, country, status, created_at) VALUES (?, ?, ?, ?, ?, ?, datetime('now'))",
                ("Test Customer", code, "9876543210", "12 Main Road", "India", "active"),
            )
            customer_id = cursor.lastrowid
            db.commit()

        list_response = self.client.get("/customers")
        list_html = list_response.get_data(as_text=True)
        self.assertEqual(list_response.status_code, 200)
        self.assertIn("Test Customer", list_html)
        self.assertIn("Rows per page", list_html)
        self.assertIn("Customer", list_html)

        edit_response = self.client.get(f"/customers/{customer_id}/edit")
        self.assertEqual(edit_response.status_code, 200)
        self.assertIn('value="Test Customer"', edit_response.get_data(as_text=True))

        delete_response = self.client.post(f"/customers/{customer_id}/delete", follow_redirects=True)
        self.assertEqual(delete_response.status_code, 200)
        self.assertIn("Customer deleted successfully.", delete_response.get_data(as_text=True))
        with sqlite3.connect(app.config["DATABASE"]) as db:
            self.assertIsNone(db.execute("SELECT id FROM customers WHERE id = ?", (customer_id,)).fetchone())


if __name__ == "__main__":
    unittest.main()
