import unittest

from app import validate_register_payload


class RegisterValidationTests(unittest.TestCase):
    def test_valid_registration_payload(self):
        payload = {
            "username": "johndoe",
            "email": "john@example.com",
            "password": "StrongPass123",
            "confirm_password": "StrongPass123",
        }
        self.assertIsNone(validate_register_payload(payload))

    def test_missing_and_invalid_fields(self):
        errors = validate_register_payload({})
        self.assertIn("Username is required.", errors)
        self.assertIn("Email is required.", errors)
        self.assertIn("Password is required.", errors)
        self.assertIn("Confirm password is required.", errors)

        errors = validate_register_payload({
            "username": "ab",
            "email": "bad-email",
            "password": "123",
            "confirm_password": "456",
        })
        self.assertIn("Username must be between 3 and 50 characters.", errors)
        self.assertIn("Enter a valid email address.", errors)
        self.assertIn("Password must be at least 8 characters.", errors)
        self.assertIn("Passwords do not match.", errors)


if __name__ == "__main__":
    unittest.main()
