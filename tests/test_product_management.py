import re
import sqlite3
import unittest
from datetime import datetime, timezone
from uuid import uuid4

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
        with sqlite3.connect(app.config["DATABASE"]) as db:
            product_count = db.execute("SELECT COUNT(*) FROM products").fetchone()[0]
        self.assertEqual(len(re.findall(r'<tr class="product-row"', html)), product_count)
        self.assertIn('<option value="10" selected>10</option>', html)
        self.assertIn('<option value="20">20</option>', html)
        self.assertIn('<option value="50">50</option>', html)
        self.assertIn('<option value="100">100</option>', html)
        with open("static/pagination.js", encoding="utf-8") as pagination_file:
            pagination_script = pagination_file.read()
        self.assertIn("const pageSize = Number(pageSizeSelect.value) || 50", pagination_script)
        self.assertIn("Showing ${firstVisible}-${lastVisible} of ${matchingRows.length}", pagination_script)
        self.assertIn("Product list", html)
        self.assertIn("Add product", html)
        self.assertEqual(len(re.findall(r'class="table-delete-action"', html)), product_count)

    def test_delete_removes_only_the_requested_product(self):
        sku = f"DELETE-{uuid4().hex[:10]}"
        with sqlite3.connect(app.config["DATABASE"]) as db:
            cursor = db.execute(
                "INSERT INTO products (name, sku, price_cents, product_group, unit, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                ("Delete Test Product", sku, 1000, "Test", "piece", datetime.now(timezone.utc).isoformat()),
            )
            product_id = cursor.lastrowid
            db.commit()

        response = self.client.post(f"/products/{product_id}/delete", follow_redirects=True)
        html = response.get_data(as_text=True)

        self.assertEqual(response.status_code, 200)
        self.assertIn("Product deleted successfully.", html)
        with sqlite3.connect(app.config["DATABASE"]) as db:
            self.assertIsNone(db.execute("SELECT id FROM products WHERE id = ?", (product_id,)).fetchone())
            self.assertIsNotNone(db.execute("SELECT id FROM products ORDER BY id LIMIT 1").fetchone())

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
