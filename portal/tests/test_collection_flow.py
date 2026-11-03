from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone
from datetime import timedelta
from portal.models import Donation, VolunteerProfile, User, RestaurantProfile

class VolunteerCollectionFlowTests(TestCase):
    def setUp(self):
        # Create a volunteer user
        self.volunteer_user = User.objects.create_user(
            username='volunteer',
            password='password123',
            user_type='VOLUNTEER'
        )
        self.volunteer_profile = VolunteerProfile.objects.create(
            user=self.volunteer_user,
            full_name='Test Volunteer'
        )

        # Create a restaurant user and profile for donation
        self.restaurant_user = User.objects.create_user(
            username='restaurant',
            password='password123',
            user_type='RESTAURANT'
        )
        self.restaurant_profile = RestaurantProfile.objects.create(
            user=self.restaurant_user,
            restaurant_name='Test Restaurant'
        )

        self.client = Client()
        self.client.login(username='volunteer', password='password123')

    def test_mark_as_collected_logic(self):
        """
        Test the full flow: Accept -> Mark as Collected -> Cleanup check.
        """
        # 1. Create an ACCEPTED donation
        donation = Donation.objects.create(
            restaurant=self.restaurant_profile,
            food_description='Test Donation',
            quantity=10,
            pickup_address='123 Main St',
            status='ACCEPTED',
            assigned_volunteer=self.volunteer_profile,
            accepted_at=timezone.now()
        )

        # 2. Mark as collected
        response = self.client.post(reverse('mark_as_collected', args=[donation.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['success'])

        # 3. Verify DB update
        donation.refresh_from_db()
        self.assertEqual(donation.status, 'COLLECTED')
        self.assertIsNotNone(donation.collected_at)

        # 4. Verify Cleanup logic ignores it
        # Simulate time passing (move accepted_at back)
        donation.accepted_at = timezone.now() - timedelta(minutes=40)
        donation.save()

        # Trigger cleanup
        self.client.get(reverse('volunteer_pickups'))

        donation.refresh_from_db()
        self.assertEqual(donation.status, 'COLLECTED')
        self.assertEqual(donation.assigned_volunteer, self.volunteer_profile)

    def test_accepted_cleanup_but_collected_safe(self):
        """
        Verify that ACCEPTED gets cleaned up, but if we could mark it COLLECTED, it stays.
        """
        # Create two donations, both "accepted" 40 mins ago
        old_time = timezone.now() - timedelta(minutes=40)

        d_accepted = Donation.objects.create(
            restaurant=self.restaurant_profile,
            food_description='Accepted Only',
            quantity=10,
            pickup_address='123 Main St',
            status='ACCEPTED',
            assigned_volunteer=self.volunteer_profile,
            accepted_at=old_time
        )

        d_collected = Donation.objects.create(
            restaurant=self.restaurant_profile,
            food_description='Collected',
            quantity=10,
            pickup_address='123 Main St',
            status='COLLECTED',
            assigned_volunteer=self.volunteer_profile,
            accepted_at=old_time,
            collected_at=old_time + timedelta(minutes=10)
        )

        # Trigger cleanup via the view
        self.client.get(reverse('volunteer_pickups'))

        d_accepted.refresh_from_db()
        d_collected.refresh_from_db()

        # Verify d_accepted is reset
        self.assertEqual(d_accepted.status, 'PENDING')
        self.assertIsNone(d_accepted.assigned_volunteer)

        # Verify d_collected is untouched
        self.assertEqual(d_collected.status, 'COLLECTED')
        self.assertEqual(d_collected.assigned_volunteer, self.volunteer_profile)
