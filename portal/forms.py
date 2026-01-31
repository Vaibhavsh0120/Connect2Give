# portal/forms.py

from django import forms
from django.core.exceptions import ValidationError
import re
from .models import DonationCamp, Donation, NGOProfile, RestaurantProfile, VolunteerProfile, User

class DonationCampForm(forms.ModelForm):
    """
    A form for creating and updating DonationCamp instances.
    """
    start_time = forms.DateTimeField(
        widget=forms.DateTimeInput(attrs={'type': 'datetime-local'}),
        label="Camp Start Time"
    )

    class Meta:
        model = DonationCamp
        fields = ['name', 'location_address', 'start_time', 'latitude', 'longitude']
        labels = {
            'name': 'Camp Name',
            'location_address': 'Camp Location Address',
        }
        widgets = {
            'latitude': forms.HiddenInput(),
            'longitude': forms.HiddenInput(),
        }

class DonationForm(forms.ModelForm):
    """
    A form for Restaurants to create new food Donations.
    """
    class Meta:
        model = Donation
        fields = ['food_description', 'quantity', 'pickup_address']
        labels = {
            'food_description': 'Food Description (e.g., 20 veg thalis, 5kg rice)',
            'quantity': 'Quantity (e.g., number of meals)',
            'pickup_address': 'Pickup Address'
        }
        widgets = {
            'pickup_address': forms.Textarea(attrs={'rows': 3}),
        }

class NGOProfileForm(forms.ModelForm):
    """
    A form for NGOs to edit their profile information, including images.
    """
    class Meta:
        model = NGOProfile
        fields = [
            'ngo_name', 
            'address', 
            'contact_person', 
            'latitude', 
            'longitude', 
            'profile_picture', 
            'banner_image'
        ]
        labels = {
            'ngo_name': 'Organization Name',
            'address': 'Primary Address',
            'contact_person': 'Contact Person Name',
            'profile_picture': 'Profile Picture (Logo)',
            'banner_image': 'Banner Image (for your public page)',
        }
        widgets = {
            'latitude': forms.HiddenInput(),
            'longitude': forms.HiddenInput(),
            'address': forms.Textarea(attrs={'rows': 3}),
        }

class RestaurantProfileForm(forms.ModelForm):
    """
    A form for Restaurants to edit their profile information, including images.
    """
    class Meta:
        model = RestaurantProfile
        fields = [
            'restaurant_name',
            'address',
            'phone_number',
            'latitude',
            'longitude',
            'profile_picture',
        ]
        labels = {
            'restaurant_name': 'Restaurant Name',
            'address': 'Primary Address',
            'phone_number': 'Public Phone Number',
            'profile_picture': 'Profile Picture (Logo)',
        }
        widgets = {
            'latitude': forms.HiddenInput(),
            'longitude': forms.HiddenInput(),
            'address': forms.Textarea(attrs={'rows': 3}),
        }

class VolunteerProfileForm(forms.ModelForm):
    """
    A form for Volunteers to edit their profile information.
    """
    # Pre-defined skill choices for volunteers
    SKILL_CHOICES = [
        ('', 'Select your skills...'),
        ('driving', 'Driving'),
        ('first_aid', 'First Aid'),
        ('cooking', 'Cooking'),
        ('logistics', 'Logistics'),
        ('communication', 'Communication'),
        ('medical', 'Medical'),
        ('packaging', 'Packaging'),
        ('other', 'Other'),
    ]
    
    skills = forms.MultipleChoiceField(
        choices=SKILL_CHOICES[1:],  # Exclude placeholder
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'skill-checkbox'}),
        required=False,
        label='Skills'
    )
    
    class Meta:
        model = VolunteerProfile
        fields = [
            'full_name', 
            'phone_number', 
            'skills', 
            'address', 
            'latitude', 
            'longitude', 
            'profile_picture'
        ]
        labels = {
            'full_name': 'Full Name',
            'phone_number': 'Phone Number',
            'skills': 'Skills',
            'address': 'Your Primary Address',
            'profile_picture': 'Profile Picture',
        }
        widgets = {
            'latitude': forms.HiddenInput(),
            'longitude': forms.HiddenInput(),
            'address': forms.Textarea(attrs={'rows': 3, 'id': 'id_address'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Convert stored skills string to list for initial value
        if self.instance and self.instance.skills:
            skills_list = [s.strip().lower().replace(' ', '_') for s in self.instance.skills.split(',')]
            self.initial['skills'] = skills_list
    
    def clean_skills(self):
        """Convert skills list back to comma-separated string for storage"""
        skills = self.cleaned_data.get('skills', [])
        # Convert skill codes to readable names
        skill_map = {
            'driving': 'Driving',
            'first_aid': 'First Aid',
            'cooking': 'Cooking',
            'logistics': 'Logistics',
            'communication': 'Communication',
            'medical': 'Medical',
            'packaging': 'Packaging',
            'other': 'Other',
        }
        readable_skills = [skill_map.get(s, s) for s in skills if s]
        return ', '.join([s for s in readable_skills if s is not None])
    
    def clean_full_name(self):
        """Validate that full_name contains only alphabetic characters and spaces"""
        full_name = self.cleaned_data.get('full_name', '').strip()
        if not re.match(r'^[a-zA-Z\s]+$', full_name):
            raise ValidationError('Full name can only contain alphabetic characters and spaces.')
        return full_name

class NGORegisterVolunteerForm(forms.Form):
    """
    A form for NGOs to register new volunteers.
    """
    full_name = forms.CharField(
        max_length=255,
        widget=forms.TextInput(attrs={'placeholder': 'John Doe', 'class': 'form-control'}),
        label='Volunteer Full Name',
        help_text='Alphabetic characters and spaces only'
    )
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={'placeholder': 'volunteer@example.com', 'class': 'form-control'}),
        label='Email Address'
    )
    phone_number = forms.CharField(
        max_length=15,
        widget=forms.TextInput(attrs={'placeholder': '+91 98765 43210', 'class': 'form-control'}),
        label='Phone Number'
    )
    aadhar_number = forms.CharField(
        max_length=12,
        widget=forms.TextInput(attrs={'placeholder': '123456789012', 'class': 'form-control'}),
        label='Aadhar Card Number (12 digits)',
        help_text='Required for verification'
    )
    
    def clean_full_name(self):
        """Validate that full_name contains only alphabetic characters and spaces"""
        full_name = self.cleaned_data.get('full_name', '').strip()
        if not re.match(r'^[a-zA-Z\s]+$', full_name):
            raise ValidationError('Full name can only contain alphabetic characters and spaces.')
        return full_name
    
    def clean_aadhar_number(self):
        """Validate Aadhar number is 12 digits"""
        aadhar = self.cleaned_data.get('aadhar_number', '').strip()
        if not aadhar.isdigit() or len(aadhar) != 12:
            raise ValidationError('Aadhar number must be exactly 12 digits.')
        if VolunteerProfile.objects.filter(aadhar_number=aadhar).exists():
            raise ValidationError('This Aadhar number is already registered.')
        return aadhar
    
    def clean_email(self):
        """Validate email is unique"""
        email = self.cleaned_data.get('email', '').strip().lower()
        if User.objects.filter(email=email).exists():
            raise ValidationError('This email is already registered in the system.')
        return email
