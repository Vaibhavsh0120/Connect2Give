# portal/forms.py

from django import forms
from django.core.exceptions import ValidationError
import re
from .models import DonationCamp, Donation, NGOProfile, RestaurantProfile, VolunteerProfile, User

# --- Helper for Cross-Model Phone Uniqueness ---
def validate_phone_unique_systemwide(phone_number, exclude_user_id=None):
    """
    Ensures a phone number is not used by ANY Restaurant, NGO, or Volunteer.
    exclude_user_id: ID of the user currently editing (to allow saving their own number)
    """
    if not phone_number:
        return

    # Check Restaurants (exclude current user if applicable)
    rest_qs = RestaurantProfile.objects.filter(phone_number=phone_number)
    if exclude_user_id:
        rest_qs = rest_qs.exclude(user_id=exclude_user_id)
    if rest_qs.exists():
        raise ValidationError("This phone number is already registered to a Restaurant.")

    # Check NGOs
    ngo_qs = NGOProfile.objects.filter(contact_number=phone_number)
    if exclude_user_id:
        ngo_qs = ngo_qs.exclude(user_id=exclude_user_id)
    if ngo_qs.exists():
        raise ValidationError("This phone number is already registered to an NGO.")

    # Check Volunteers
    vol_qs = VolunteerProfile.objects.filter(phone_number=phone_number)
    if exclude_user_id:
        vol_qs = vol_qs.exclude(user_id=exclude_user_id)
    if vol_qs.exists():
        raise ValidationError("This phone number is already registered to a Volunteer.")

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
    A form for NGOs to edit their profile information.
    Editable: NGO Name, Contact, Address, Email (User), Name (User).
    Read-Only: Registration Number.
    """
    # --- Signup Field: Full Name (Step 1) ---
    full_name = forms.CharField(
        label="Representative Name",
        required=True,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g., John Doe'})
    )
    
    # --- Signup Field: Email (Step 1) ---
    email = forms.EmailField(
        required=True, 
        label="Email Address",
        widget=forms.EmailInput(attrs={'class': 'form-control'})
    )
    
    # --- Signup Field: Registration Number (Step 2 - Read Only) ---
    registration_number = forms.CharField(
        label="Registration Number",
        required=False,
        widget=forms.TextInput(attrs={'disabled': 'disabled', 'class': 'form-control bg-gray-100'})
    )

    class Meta:
        model = NGOProfile
        fields = [
            'ngo_name', 
            'contact_number', 
            'address', 
            'latitude', 
            'longitude', 
            'profile_picture', 
            'banner_image'
        ]
        labels = {
            'ngo_name': 'Organization Name',
            'address': 'Primary Address',
            'contact_number': 'Contact Number',
            'profile_picture': 'Profile Picture (Logo)',
            'banner_image': 'Banner Image (for your public page)',
        }
        widgets = {
            'latitude': forms.HiddenInput(),
            'longitude': forms.HiddenInput(),
            'address': forms.Textarea(attrs={'rows': 3}),
            'contact_number': forms.TextInput(attrs={
                'type': 'tel',
                'pattern': '[0-9]{10}',
                'maxlength': '10',
                'placeholder': '9876543210',
                'inputmode': 'numeric'
            }),
        }
        help_texts = {
            'contact_number': 'Enter a valid 10-digit mobile number',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            # Populate fields from User model
            self.fields['email'].initial = self.instance.user.email
            self.fields['full_name'].initial = self.instance.user.get_full_name()
            # Populate disabled field
            self.fields['registration_number'].initial = self.instance.registration_number

    def clean_contact_number(self):
        """Validate contact number format and SYSTEM-WIDE uniqueness"""
        contact_number = self.cleaned_data.get('contact_number', '').strip()
        if not contact_number.isdigit() or len(contact_number) != 10:
            raise ValidationError('Contact number must be exactly 10 digits.')
        
        # Check against ALL profiles (Restaurant, NGO, Volunteer)
        validate_phone_unique_systemwide(contact_number, exclude_user_id=self.instance.user.pk)
        return contact_number

    def clean_email(self):
        """Validate email uniqueness"""
        email = self.cleaned_data.get('email')
        if User.objects.filter(email=email).exclude(pk=self.instance.user.pk).exists():
            raise ValidationError("This email address is already in use by another account.")
        return email

    def save(self, commit=True):
        profile = super().save(commit=False)
        # Update User model (Email and Name)
        user = profile.user
        user.email = self.cleaned_data['email']
        
        full_name_parts = self.cleaned_data['full_name'].strip().split(' ', 1)
        user.first_name = full_name_parts[0]
        user.last_name = full_name_parts[1] if len(full_name_parts) > 1 else ''
        
        user.save()
        if commit:
            profile.save()
        return profile

class RestaurantProfileForm(forms.ModelForm):
    """
    A form for Restaurants to edit their profile.
    Editable: Restaurant Name, Phone, Address, Email (User), Name (User).
    """
    # --- Signup Field: Full Name (Step 1) ---
    full_name = forms.CharField(
        label="Owner/Manager Name",
        required=True,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g., Jane Smith'})
    )
    
    # --- Signup Field: Email (Step 1) ---
    email = forms.EmailField(
        required=True, 
        label="Email Address",
        widget=forms.EmailInput(attrs={'class': 'form-control'})
    )

    class Meta:
        model = RestaurantProfile
        fields = [
            'restaurant_name',
            'phone_number',
            'address',
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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            # Populate fields from User model
            self.fields['email'].initial = self.instance.user.email
            self.fields['full_name'].initial = self.instance.user.get_full_name()

    def clean_phone_number(self):
        """Validate phone number uniqueness SYSTEM-WIDE"""
        phone = self.cleaned_data.get('phone_number')
        
        # Check against ALL profiles (Restaurant, NGO, Volunteer)
        validate_phone_unique_systemwide(phone, exclude_user_id=self.instance.user.pk)
        return phone

    def clean_email(self):
        """Validate email uniqueness"""
        email = self.cleaned_data.get('email')
        if User.objects.filter(email=email).exclude(pk=self.instance.user.pk).exists():
            raise ValidationError("This email address is already in use by another account.")
        return email

    def save(self, commit=True):
        profile = super().save(commit=False)
        # Update User model (Email and Name)
        user = profile.user
        user.email = self.cleaned_data['email']
        
        full_name_parts = self.cleaned_data['full_name'].strip().split(' ', 1)
        user.first_name = full_name_parts[0]
        user.last_name = full_name_parts[1] if len(full_name_parts) > 1 else ''
        
        user.save()
        if commit:
            profile.save()
        return profile

class VolunteerProfileForm(forms.ModelForm):
    """
    A form for Volunteers to edit their profile.
    Editable: Full Name, Email, Phone, Skills, Address.
    Read-Only: Aadhar Number.
    """
    # --- Signup Field: Email (Step 1) ---
    email = forms.EmailField(
        required=True, 
        label="Email Address",
        widget=forms.EmailInput(attrs={'class': 'form-control'})
    )

    # --- Aadhar Number (Read Only) ---
    aadhar_number = forms.CharField(
        label="Aadhar Number",
        required=False,
        widget=forms.TextInput(attrs={'disabled': 'disabled', 'class': 'form-control bg-gray-100'})
    )

    # Pre-defined skill choices
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
        choices=SKILL_CHOICES[1:],
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
        if self.instance.pk:
            # Populate email from User model
            self.fields['email'].initial = self.instance.user.email
            
            # Populate Aadhar read-only
            if self.instance.aadhar_number:
                self.fields['aadhar_number'].initial = self.instance.aadhar_number
            else:
                self.fields['aadhar_number'].widget.attrs['placeholder'] = 'Not provided'
            
            # Parse skills string to list
            if self.instance.skills:
                skills_list = [s.strip().lower().replace(' ', '_') for s in self.instance.skills.split(',')]
                self.initial['skills'] = skills_list
    
    def clean_skills(self):
        """Convert skills list back to comma-separated string"""
        skills = self.cleaned_data.get('skills', [])
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
        """Validate Full Name (Alphabets only)"""
        full_name = self.cleaned_data.get('full_name', '').strip()
        if not re.match(r'^[a-zA-Z\s]+$', full_name):
            raise ValidationError('Full name can only contain alphabetic characters and spaces.')
        return full_name

    def clean_phone_number(self):
        """Validate phone number uniqueness SYSTEM-WIDE"""
        phone = self.cleaned_data.get('phone_number')
        
        # Check against ALL profiles (Restaurant, NGO, Volunteer)
        validate_phone_unique_systemwide(phone, exclude_user_id=self.instance.user.pk)
        return phone

    def clean_email(self):
        """Validate email uniqueness"""
        email = self.cleaned_data.get('email')
        if User.objects.filter(email=email).exclude(pk=self.instance.user.pk).exists():
            raise ValidationError("This email address is already in use by another account.")
        return email

    def save(self, commit=True):
        profile = super().save(commit=False)
        user = profile.user
        user.email = self.cleaned_data['email']
        user.save()
        
        # VolunteerProfile has its own email field (legacy?), sync it too
        profile.email = self.cleaned_data['email']
        
        if commit:
            profile.save()
        return profile

class NGORegisterVolunteerForm(forms.Form):
    """
    A form for NGOs to register new volunteers.
    Ensures no duplicate data system-wide.
    """
    SKILL_CHOICES = [
        ('driving', 'Driving'),
        ('first_aid', 'First Aid'),
        ('cooking', 'Cooking'),
        ('logistics', 'Logistics'),
        ('communication', 'Communication'),
        ('medical', 'Medical'),
        ('packaging', 'Packaging'),
    ]
    
    full_name = forms.CharField(
        max_length=255,
        widget=forms.TextInput(attrs={'placeholder': 'John Doe', 'class': 'form-control'}),
        label='Volunteer Full Name',
        help_text='Alphabetic characters and spaces only'
    )
    
    username = forms.CharField(
        max_length=150,
        min_length=3,
        widget=forms.TextInput(attrs={
            'placeholder': 'volunteer_username', 
            'class': 'form-control',
            'autocomplete': 'off'
        }),
        label='Username',
        help_text='Unique username for login (3-150 characters, letters, numbers, underscores, hyphens)'
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
    
    skills = forms.MultipleChoiceField(
        choices=SKILL_CHOICES,
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'skill-checkbox'}),
        required=False,
        label='Skills'
    )
    
    address = forms.CharField(
        widget=forms.Textarea(attrs={
            'rows': 3, 
            'class': 'form-control',
            'placeholder': 'Enter volunteer primary address...',
            'id': 'id_volunteer_address'
        }),
        required=False,
        label='Primary Address'
    )
    
    latitude = forms.FloatField(
        widget=forms.HiddenInput(attrs={'id': 'id_volunteer_latitude'}),
        required=False
    )
    
    longitude = forms.FloatField(
        widget=forms.HiddenInput(attrs={'id': 'id_volunteer_longitude'}),
        required=False
    )
    
    profile_picture = forms.ImageField(
        required=False,
        label='Profile Picture',
        help_text='Optional profile photo'
    )
    
    def clean_full_name(self):
        full_name = self.cleaned_data.get('full_name', '').strip()
        if not re.match(r'^[a-zA-Z\s]+$', full_name):
            raise ValidationError('Full name can only contain alphabetic characters and spaces.')
        return full_name
    
    def clean_username(self):
        username = self.cleaned_data.get('username', '').strip().lower()
        if not username:
            raise ValidationError('Username is required.')
        if len(username) < 3:
            raise ValidationError('Username must be at least 3 characters.')
        if not username.replace('_', '').replace('-', '').isalnum():
            raise ValidationError('Username can only contain letters, numbers, underscores, and hyphens.')
        if User.objects.filter(username=username).exists():
            raise ValidationError('This username is already taken.')
        return username
    
    def clean_aadhar_number(self):
        aadhar = self.cleaned_data.get('aadhar_number', '').strip()
        if not aadhar.isdigit() or len(aadhar) != 12:
            raise ValidationError('Aadhar number must be exactly 12 digits.')
        if VolunteerProfile.objects.filter(aadhar_number=aadhar).exists():
            raise ValidationError('This Aadhar number is already registered.')
        return aadhar
    
    def clean_email(self):
        email = self.cleaned_data.get('email', '').strip().lower()
        if User.objects.filter(email=email).exists():
            raise ValidationError('This email is already registered in the system.')
        return email
    
    def clean_phone_number(self):
        phone = self.cleaned_data.get('phone_number', '').strip()
        # Check uniqueness across ALL user types
        validate_phone_unique_systemwide(phone)
        return phone

    def clean_skills(self):
        skills = self.cleaned_data.get('skills', [])
        skill_map = {
            'driving': 'Driving',
            'first_aid': 'First Aid',
            'cooking': 'Cooking',
            'logistics': 'Logistics',
            'communication': 'Communication',
            'medical': 'Medical',
            'packaging': 'Packaging',
        }
        readable_skills = [skill_map.get(s, s) for s in skills if s]
        return ', '.join(str(skill) for skill in readable_skills)