# Generated migration for adding geolocation tracking fields

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('portal', '0005_add_donation_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='volunteerprofile',
            name='last_location_update',
            field=models.DateTimeField(blank=True, help_text='Timestamp of last geolocation update', null=True),
        ),
        migrations.AddField(
            model_name='volunteerprofile',
            name='allow_location_sharing',
            field=models.BooleanField(default=True, help_text='Allow real-time location sharing during active tasks'),
        ),
        migrations.AddField(
            model_name='volunteerprofile',
            name='share_location_with_ngos',
            field=models.BooleanField(default=True, help_text='Allow NGOs to see my real-time location'),
        ),
    ]
