import json
import re

from django.test import TestCase
from django.urls import reverse

from portal.models import RestaurantProfile, User


class PublicMapTests(TestCase):
    def test_address_is_serialized_as_data(self):
        address = "O'Connell Street </script><script>window.injected = true</script>"
        RestaurantProfile.objects.create(
            user=User.objects.create_user(username="restaurant"),
            restaurant_name="Test Kitchen",
            address=address,
            phone_number="1234567890",
            latitude=0,
            longitude=77,
        )

        response = self.client.get(reverse("index"))

        self.assertNotContains(response, address)
        match = re.search(
            r'<script id="restaurants-map-data" type="application/json">(.*?)</script>',
            response.content.decode(),
        )
        self.assertIsNotNone(match)
        self.assertEqual(json.loads(match.group(1))[0]["address"], address)
