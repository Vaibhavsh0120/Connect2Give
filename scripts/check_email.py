"""Send a test message to the configured SMTP account when run explicitly."""

import os

import django
from django.core.mail import send_mail
from django.conf import settings


def main():
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'food_donation_project.settings')
    django.setup()
    if not settings.EMAIL_HOST_USER:
        raise SystemExit("Configure EMAIL_HOST_USER before running this check.")
    send_mail(
        'Test Email from Connect2Give',
        'Your Connect2Give email configuration is working.',
        settings.DEFAULT_FROM_EMAIL,
        [settings.EMAIL_HOST_USER],
        fail_silently=False,
    )
    print("Test email sent.")


if __name__ == '__main__':
    main()
