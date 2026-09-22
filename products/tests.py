from django.test import TestCase

from .serializers import ProductSerializer


class ProductSerializerTests(TestCase):
	def test_accepts_positive_price(self):
		serializer = ProductSerializer(
			data={
				"name": "Coffee",
				"price": "12.50",
				"description": "Whole bean coffee",
				"category": "Beverages",
				"in_stock": True,
			}
		)

		self.assertTrue(serializer.is_valid(), serializer.errors)

	def test_rejects_non_positive_price(self):
		for price in ("0", "-1"):
			with self.subTest(price=price):
				serializer = ProductSerializer(
					data={"name": "Coffee", "price": price}
				)

				self.assertFalse(serializer.is_valid())
				self.assertEqual(
					serializer.errors["price"][0],
					"Price must be greater than 0.",
				)
