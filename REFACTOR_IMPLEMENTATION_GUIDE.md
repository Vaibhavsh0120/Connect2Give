# Connect2Give Django Refactor - Implementation Guide

## Overview
This guide documents the major system refactor implemented for Connect2Give, transforming it from a public-access volunteer model to a strictly managed NGO-volunteer hierarchy with enhanced security, verification, and real-time tracking.

---

## 1. Data Integrity & Custom Authentication

### 1.1 Custom Validators for Name Fields
- **Location**: `portal/models.py` (lines 8-14)
- **Implementation**: Added `alphabetic_validator` using Django's `RegexValidator`
- **Applied to**: 
  - `RestaurantProfile.restaurant_name`
  - `NGOProfile.ngo_name` and `NGOProfile.contact_person`
  - `VolunteerProfile.full_name`
- **Validation**: Only accepts alphabetic characters (a-z, A-Z) and spaces

### 1.2 Username Management
- **Location**: `portal/views/auth_views.py` (lines 21-37)
- **New Endpoint**: `/api/check-username/` (AJAX)
- **Features**:
  - Async availability check before form submission
  - Minimum 3 characters requirement
  - Real-time validation feedback with visual indicators (✓/✕)
- **Related Template**: `templates/auth/register_step_1.html` (lines 50-68, 134-173)

### 1.3 Must-Change-Password Flag
- **Location**: `portal/models.py` (line 24)
- **Field**: `User.must_change_password` (Boolean, default=False)
- **Purpose**: Force volunteers to set a new password on first login after NGO registration

---

## 2. NGO-Managed Volunteer Onboarding

### 2.1 Disabled Public Volunteer Signup
- **Location**: `portal/views/auth_views.py` (lines 91-92)
- **Change**: Public registration flow no longer allows "Volunteer" role selection
- **Template**: `templates/auth/register_step_2.html` (lines 38-44)
- **Redirect**: Users wanting to volunteer must be registered by an NGO

### 2.2 NGO Volunteer Registration Portal
- **Location**: `portal/views/ngo_views.py` (lines 113-228)
- **URL**: `/dashboard/ngo/register-volunteer/`
- **Template**: `templates/ngo/register_volunteer.html`
- **Form**: `NGORegisterVolunteerForm` in `portal/forms.py` (lines 126-174)

### 2.3 Required Fields for Volunteer Registration
- Full Name (alphabetic only)
- Email Address (unique)
- Phone Number
- Aadhar Card Number (12 digits, unique)

### 2.4 Automatic Email Workflow (SMTP)
- **Location**: `portal/views/ngo_views.py` (lines 155-167)
- **Email Template**: `templates/emails/volunteer_invitation.html`
- **Process**:
  1. NGO submits volunteer registration form
  2. System generates temporary password (12 characters, random)
  3. User account created with `must_change_password=True`
  4. VolunteerProfile linked to NGO via `registered_ngo` FK
  5. SMTP email sent with username, temporary password, and login link

---

## 3. Forced First-Time Password Change

### 3.1 Login Interception
- **Location**: `portal/views/auth_views.py` (lines 141-160)
- **Logic**: After successful authentication, check `user.must_change_password`
- **Action**: If True, redirect to `/force-password-change/`

### 3.2 Password Change View
- **Location**: `portal/views/auth_views.py` (lines 162-195)
- **URL**: `/force-password-change/`
- **Template**: `templates/auth/force_password_change.html`
- **Features**:
  - Real-time password strength indicator
  - Requirement checklist (8+ chars, uppercase, number)
  - Prevents access to dashboard until completed
  - Updates `must_change_password=False` upon success

### 3.3 Hard Constraint
- Dashboard routes check `must_change_password` flag
- No data access until password is changed
- Automatic re-authentication after password change

---

## 4. NGO Password Management

### 4.1 Volunteer Reset Functionality
- **Location**: `portal/views/ngo_views.py` (lines 197-228)
- **URL**: `/dashboard/ngo/reset-volunteer-password/<id>/`
- **Template**: `templates/ngo/reset_volunteer_password.html`

### 4.2 Reset Process
1. NGO clicks "Reset & Resend Password" button next to volunteer
2. Confirmation page shows volunteer details
3. Upon confirmation, new temporary password generated
4. Email sent with new credentials
5. `must_change_password` set to True again

---

## 5. Database Changes

### 5.1 New Migration File
- **Location**: `portal/migrations/0006_add_password_change_fields.py`
- **Changes**:
  - Added `User.must_change_password` field
  - Added `VolunteerProfile.email` field
  - Added `VolunteerProfile.aadhar_number` field (unique)
  - Added `VolunteerProfile.registered_ngo` FK to NGOProfile
  - Updated `Donation.status` choices: `VERIFYING` → `VERIFICATION_PENDING`
  - Applied name validators to RestaurantProfile, NGOProfile, VolunteerProfile

### 5.2 Model Relationships
```
User (1) ←→ (Many) VolunteerProfile
NGOProfile (1) ←→ (Many) VolunteerProfile (through registered_ngo FK)
```

---

## 6. Email Configuration

### 6.1 Required Environment Variables
```
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.gmail.com  # Or your SMTP provider
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=your-email@gmail.com
EMAIL_HOST_PASSWORD=your-app-password  # Use app-specific password for Gmail
DEFAULT_FROM_EMAIL=noreply@connect2give.com
```

### 6.2 Email Templates
- **Volunteer Invitation**: `templates/emails/volunteer_invitation.html`
- **Password Reset**: `templates/emails/volunteer_password_reset.html`

---

## 7. URL Routing Updates

### 7.1 New Routes Added to `portal/urls.py`
```python
path('force-password-change/', views.force_password_change, name='force_password_change'),
path('api/check-username/', views.check_username_availability, name='check_username'),
path('dashboard/ngo/register-volunteer/', views.ngo_register_volunteer, name='ngo_register_volunteer'),
path('dashboard/ngo/reset-volunteer-password/<int:volunteer_id>/', 
     views.ngo_reset_volunteer_password, name='ngo_reset_volunteer_password'),
```

---

## 8. Form Validation

### 8.1 NGORegisterVolunteerForm
- **Location**: `portal/forms.py` (lines 126-174)
- **Validations**:
  - `clean_full_name()`: Only alphabetic + spaces
  - `clean_aadhar_number()`: Exactly 12 digits, unique check
  - `clean_email()`: Email uniqueness across User table

---

## 9. NGO Dashboard Updates

### 9.1 New Navigation Item
- Added "Register Volunteer" tab in NGO sidebar
- Accessible via: `ngo/base.html` (to be updated)

### 9.2 Volunteer List View
- Shows registered volunteers with status (Pending/Active)
- "Reset & Resend Password" button per volunteer
- Sorted by creation date (newest first)

---

## 10. Running the Migration

### Steps:
```bash
# Apply migrations
python manage.py migrate portal

# Create superuser if needed
python manage.py createsuperuser

# Test email configuration
python manage.py shell
from django.core.mail import send_mail
send_mail(
    'Test',
    'Test message',
    'from@example.com',
    ['to@example.com'],
    fail_silently=False,
)
```

---

## 11. Testing Checklist

- [ ] User registers with username (AJAX validation works)
- [ ] Public volunteer signup is blocked
- [ ] NGO can register volunteer with form
- [ ] Email with credentials is sent
- [ ] Volunteer receives email and can access login page
- [ ] Login redirects to force password change if `must_change_password=True`
- [ ] Volunteer cannot access dashboard without changing password
- [ ] Password strength indicator works
- [ ] NGO can reset volunteer password
- [ ] New email is sent after reset
- [ ] Name fields validate alphabetic-only input
- [ ] Aadhar validation (12 digits, unique)

---

## 12. Security Considerations

- **Password Hashing**: Django's default PBKDF2 used
- **HTTPS**: Ensure HTTPS in production (set `SECURE_SSL_REDIRECT=True`)
- **CSRF Protection**: All forms include {% csrf_token %}
- **Session Security**: Secure session cookies in production
- **Email Security**: Use environment variables for SMTP credentials
- **Validation**: Server-side validation on all inputs

---

## 13. Future Enhancements Needed

### Phase 5-8 (Not Yet Implemented):
1. **Pickup vs Delivery Mode Split** - Modal interface for volunteers
2. **Real-Time Geolocation Tracking** - Geolocation API integration
3. **Route Optimization (TSP)** - Traveling Salesman Problem algorithm
4. **Verification & Trust Protocol** - NGO approval workflow for completed pickups
5. **Mobile Responsive Design** - Enhanced CSS for all breakpoints

---

## 14. File Summary

### Modified Files:
- `portal/models.py` - Added validators and new fields
- `portal/forms.py` - New NGORegisterVolunteerForm
- `portal/views/auth_views.py` - Username check, password change logic
- `portal/views/ngo_views.py` - Volunteer registration and password reset
- `portal/urls.py` - New routes
- `templates/auth/register_step_1.html` - Username field + AJAX
- `templates/auth/register_step_2.html` - Removed volunteer option
- `templates/auth/force_password_change.html` - NEW
- `templates/ngo/register_volunteer.html` - NEW
- `templates/ngo/reset_volunteer_password.html` - NEW
- `templates/emails/volunteer_invitation.html` - NEW
- `templates/emails/volunteer_password_reset.html` - NEW
- `portal/migrations/0006_add_password_change_fields.py` - NEW

---

## 15. Support & Troubleshooting

### Email Not Sending
- Check EMAIL_HOST_USER and EMAIL_HOST_PASSWORD in .env
- For Gmail: Use App Passwords (not regular password)
- Enable "Less secure apps" if using regular Gmail password

### Username Check Not Working
- Ensure JavaScript is enabled in browser
- Check browser console for AJAX errors
- Verify `/api/check-username/` route is accessible

### Password Change Redirect Loop
- Verify `must_change_password` field exists in database
- Check migration ran successfully
- Clear browser cache and session cookies

---

## 16. Deployment Notes

1. **Environment Variables**: All email/auth vars must be set
2. **Static Files**: Run `python manage.py collectstatic` before deployment
3. **Database**: Run migrations in production environment
4. **Email Provider**: Set up SMTP provider (Gmail, SendGrid, etc.)
5. **SSL Certificate**: Use HTTPS in production

---

**Last Updated**: January 2026
**Status**: Phase 1-3 Complete | Phase 4-8 Pending
