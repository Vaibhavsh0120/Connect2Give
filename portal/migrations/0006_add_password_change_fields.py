# Generated migration for adding new fields

from django.db import migrations, models
import django.core.validators

class Migration(migrations.Migration):

    dependencies = [
        ('portal', '0005_badge_donation_rating_donation_review_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='must_change_password',
            field=models.BooleanField(default=False, help_text='Force user to change password on next login'),
        ),
        migrations.AlterField(
            model_name='restaurantprofile',
            name='restaurant_name',
            field=models.CharField(
                max_length=255,
                validators=[django.core.validators.RegexValidator(
                    code='invalid_name',
                    message='This field can only contain alphabetic characters and spaces.',
                    regex='^[a-zA-Z\\s]+$'
                )]
            ),
        ),
        migrations.AlterField(
            model_name='ngoprofile',
            name='ngo_name',
            field=models.CharField(
                max_length=255,
                validators=[django.core.validators.RegexValidator(
                    code='invalid_name',
                    message='This field can only contain alphabetic characters and spaces.',
                    regex='^[a-zA-Z\\s]+$'
                )]
            ),
        ),
        migrations.AlterField(
            model_name='ngoprofile',
            name='contact_person',
            field=models.CharField(
                max_length=100,
                validators=[django.core.validators.RegexValidator(
                    code='invalid_name',
                    message='This field can only contain alphabetic characters and spaces.',
                    regex='^[a-zA-Z\\s]+$'
                )]
            ),
        ),
        migrations.AddField(
            model_name='volunteerprofile',
            name='email',
            field=models.EmailField(blank=True, null=True, max_length=254),
        ),
        migrations.AddField(
            model_name='volunteerprofile',
            name='aadhar_number',
            field=models.CharField(blank=True, help_text='12-digit Aadhar number', max_length=12, null=True, unique=True),
        ),
        migrations.AddField(
            model_name='volunteerprofile',
            name='registered_ngo',
            field=models.ForeignKey(
                blank=True,
                help_text='NGO that registered this volunteer',
                null=True,
                on_delete=models.deletion.SET_NULL,
                related_name='managed_volunteers',
                to='portal.ngoprofile'
            ),
        ),
        migrations.AlterField(
            model_name='volunteerprofile',
            name='full_name',
            field=models.CharField(
                max_length=255,
                validators=[django.core.validators.RegexValidator(
                    code='invalid_name',
                    message='This field can only contain alphabetic characters and spaces.',
                    regex='^[a-zA-Z\\s]+$'
                )]
            ),
        ),
        migrations.AlterField(
            model_name='donation',
            name='status',
            field=models.CharField(
                choices=[
                    ('PENDING', 'Pending Pickup'),
                    ('ACCEPTED', 'On its Way'),
                    ('COLLECTED', 'Collected by Volunteer'),
                    ('VERIFICATION_PENDING', 'Pending Verification'),
                    ('DELIVERED', 'Delivered & Verified')
                ],
                db_index=True,
                default='PENDING',
                max_length=20
            ),
        ),
    ]
