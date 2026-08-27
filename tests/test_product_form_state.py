import unittest
from uuid import uuid4

from app import app


class ProductFormStateTests(unittest.TestCase):
    def test_invalid_submit_keeps_values_and_marks_field_errors(self):
        client = app.test_client()
        with client.session_transaction() as session:
            session["user_id"] = 1

        response = client.post(
            "/products/new",
            data={
                "name": "Laptop Pro",
                "sku": "",
                "price": "",
                "product_group": "General",
                "unit": "piece",
                "status": "active",
            },
            follow_redirects=False,
        )

        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertIn('value="Laptop Pro"', html)
        self.assertIn('id="name"', html)
        self.assertIn('id="sku"', html)
        self.assertIn('SKU is required.', html)
        self.assertIn('Selling price is required.', html)

    def test_successful_submit_redirects_and_flushes_form_state(self):
        client = app.test_client()
        with client.session_transaction() as session:
            session["user_id"] = 1

        save_response = client.post(
            "/products/new",
            data={
                "name": "Saved Product",
                "sku": f"SP-{uuid4().hex[:12]}",
                "price": "149.99",
                "product_group": "General",
                "category": "Electronics",
                "brand": "Sales",
                "unit": "piece",
                "tax_rate": "0",
                "stock_quantity": "10",
                "reorder_level": "2",
                "status": "active",
            },
            follow_redirects=True,
        )
        self.assertEqual(save_response.status_code, 200)
        self.assertIn('Product added successfully.', save_response.get_data(as_text=True))


if __name__ == "__main__":
    unittest.main()
