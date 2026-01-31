# Generated migration for adding verification & trust protocol

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('portal', '0006_add_geolocation_tracking'),
    ]

    operations = [
        migrations.CreateModel(
            name='VolunteerTrustScore',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('total_deliveries', models.IntegerField(default=0)),
                ('verified_deliveries', models.IntegerField(default=0)),
                ('rejected_deliveries', models.IntegerField(default=0)),
                ('average_rating', models.FloatField(default=0.0)),
                ('trust_score', models.FloatField(default=100.0, help_text='0-100 score, starts at 100')),
                ('badges', models.JSONField(default=list, help_text="List of earned badges: ['verified', 'trusted', 'reliable', 'excellent']")),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('volunteer', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='trust_score', to='portal.volunteerprofile')),
            ],
        ),
        migrations.AddField(
            model_name='donation',
            name='verified_at',
            field=models.DateTimeField(blank=True, help_text='When NGO verified the donation', null=True),
        ),
        migrations.AddField(
            model_name='donation',
            name='verified_by',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='verified_donations', to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddField(
            model_name='donation',
            name='verification_notes',
            field=models.TextField(blank=True, help_text="NGO's verification notes", null=True),
        ),
        migrations.AddField(
            model_name='donation',
            name='is_verified',
            field=models.BooleanField(db_index=True, default=False),
        ),
        migrations.AddField(
            model_name='donation',
            name='verification_count',
            field=models.IntegerField(default=0, help_text='Number of attempts before verification'),
        ),
    ]
