import unittest

from app import validate_product_payload


class ProductValidationTests(unittest.TestCase):
    def test_valid_product_payload(self):
        payload = {
            "name": "Laptop Pro 14",
            "sku": "LP-14-001",
            "price": "1299.99",
            "product_group": "Electronics",
            "category": "Computers",
            "brand": "Apex",
            "description": "14-inch business laptop",
            "unit": "piece",
            "cost_price": "999.99",
            "tax_rate": "18.5",
            "stock_quantity": "25",
            "reorder_level": "5",
            "supplier": "Apex Supply Co.",
            "barcode": "1234567890123",
            "status": "active",
        }
        self.assertIsNone(validate_product_payload(payload))

    def test_required_fields_are_checked(self):
        errors = validate_product_payload({})
        self.assertIn("Product name is required.", errors)
        self.assertIn("SKU is required.", errors)
        self.assertIn("Selling price is required.", errors)
        self.assertIn("Product group is required.", errors)
        self.assertIn("Unit is required.", errors)

    def test_invalid_values_and_lengths(self):
        payload = {
            "name": "A",
            "sku": "!!!",
            "price": "-1",
            "product_group": "",
            "unit": "invalid-unit",
            "category": "A" * 81,
            "tax_rate": "101",
            "stock_quantity": "-1",
            "reorder_level": "-1",
            "barcode": "A" * 81,
            "status": "unknown",
        }
        errors = validate_product_payload(payload)
        self.assertIn("Product name must be between 2 and 120 characters.", errors)
        self.assertIn("SKU format is invalid.", errors)
        self.assertIn("Selling price must be 0 or greater.", errors)
        self.assertIn("Product group is required.", errors)
        self.assertIn("Unit is required.", errors)
        self.assertIn("Category must be between 2 and 80 characters.", errors)
        self.assertIn("Tax rate must be between 0 and 100.", errors)
        self.assertIn("Opening stock cannot be negative.", errors)
        self.assertIn("Reorder level cannot be negative.", errors)
        self.assertIn("Barcode format is invalid.", errors)
        self.assertIn("Status must be active or inactive.", errors)


if __name__ == "__main__":
    unittest.main()
