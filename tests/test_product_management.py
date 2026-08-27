import re
import sqlite3
import unittest

from app import app


class ProductManagementTests(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()
        with self.client.session_transaction() as current_session:
            current_session["user_id"] = 1

    def test_product_list_renders_all_products_with_search_and_pagination(self):
        response = self.client.get("/products")
        html = response.get_data(as_text=True)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(re.findall(r'<tr class="product-row"', html)), 60)
        self.assertIn("const pageSize = 50", html)
        self.assertIn("row.dataset.search.includes(query)", html)
        self.assertIn("Product list", html)
        self.assertIn("Add product", html)

    def test_edit_page_is_prefilled_for_existing_product(self):
        with sqlite3.connect(app.config["DATABASE"]) as db:
            product_id, product_name = db.execute(
                "SELECT id, name FROM products ORDER BY id LIMIT 1"
            ).fetchone()

        response = self.client.get(f"/products/{product_id}/edit")
        html = response.get_data(as_text=True)

        self.assertEqual(response.status_code, 200)
        self.assertIn(f"/products/{product_id}/edit", html)
        self.assertIn(f'value="{product_name}"', html)
        self.assertIn("Save changes", html)

    def test_invalid_edit_keeps_submitted_values(self):
        with sqlite3.connect(app.config["DATABASE"]) as db:
            product_id = db.execute("SELECT id FROM products ORDER BY id LIMIT 1").fetchone()[0]

        response = self.client.post(
            f"/products/{product_id}/edit",
            data={
                "name": "Updated demo product",
                "sku": "",
                "price": "",
                "product_group": "Demo Catalogue",
                "unit": "piece",
            },
        )
        html = response.get_data(as_text=True)

        self.assertEqual(response.status_code, 200)
        self.assertIn('value="Updated demo product"', html)
        self.assertIn("SKU is required.", html)
        self.assertIn("Selling price is required.", html)


if __name__ == "__main__":
    unittest.main()
