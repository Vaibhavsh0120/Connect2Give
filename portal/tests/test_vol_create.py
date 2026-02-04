# test_email.py
import os
import django
from django.core.mail import send_mail
from django.conf import settings

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'food_donation_project.settings')
django.setup()

print("--- Testing Email Configuration ---")
print(f"User: {settings.EMAIL_HOST_USER}")
print(f"Host: {settings.EMAIL_HOST}:{settings.EMAIL_PORT}")

try:
    send_mail(
        'Test Email from Connect2Give',
        'If you see this, your email configuration is working perfectly!',
        settings.DEFAULT_FROM_EMAIL,
        [settings.EMAIL_HOST_USER], # Sends email to yourself
        fail_silently=False,
    )
    print("\n✅ SUCCESS! Email sent successfully.")
except Exception as e:
    print("\n❌ FAILED! Google refused the connection.")
    print(f"Error: {e}")