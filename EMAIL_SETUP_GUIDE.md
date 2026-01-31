# Connect2Give Email Configuration Guide

## Overview
The volunteer registration system automatically sends welcome emails with login credentials when an NGO registers a new volunteer.

---

## Files Modified to Fix Errors

### 1. **portal/views/auth_views.py**
- **Fixed:** Added missing `login_required` import
- **Added:** Email-related imports (`send_mail`, `render_to_string`, `strip_tags`)
- **Status:** ✅ Fixed

---

## Email Feature Implementation

### What Happens When NGO Registers a Volunteer?

1. **Volunteer Registration Form Submitted** (`ngo_register_volunteer` view)
   - NGO enters: Full Name, Email, Phone, Aadhar Number
   
2. **System Generates Credentials**
   - Temporary 12-character random password
   - Unique username from email prefix
   - `must_change_password` flag set to True
   
3. **Email is Automatically Sent** with:
   - Username
   - Temporary password
   - Login URL
   - Instructions to change password
   - Welcome message with next steps

4. **Volunteer Receives Email**
   - Template: `/templates/emails/volunteer_invitation.html`
   - Subject: "Welcome to Connect2Give - Your Account Details"
   - Professional HTML-formatted email

---

## Email Configuration in Django

### Current Setup (in `food_donation_project/settings.py`)

```python
# Email Configuration
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'smtp.gmail.com'
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = env('EMAIL_HOST_USER')           # Your Gmail address
EMAIL_HOST_PASSWORD = env('EMAIL_HOST_PASSWORD')   # App-specific password
DEFAULT_FROM_EMAIL = env('DEFAULT_FROM_EMAIL')     # Sender email
```

---

## Step 1: Enable Gmail SMTP (Recommended)

### Prerequisites
- Gmail account
- 2-Step Verification enabled

### Steps

1. **Go to Google Account Settings**
   - Visit: https://myaccount.google.com
   - Click "Security" in left sidebar

2. **Enable 2-Step Verification**
   - Scroll to "Signing in to Google"
   - Click "2-Step Verification"
   - Follow instructions

3. **Generate App Password**
   - After 2FA is enabled, search for "App passwords"
   - Select "Mail" and "Windows Computer" (or your OS)
   - Google will generate a 16-character password
   - Copy this password

---

## Step 2: Create `.env` File

### Location
Create `.env` file in the project root directory (same level as `manage.py`)

### Content

```env
# Email Configuration
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=your-email@gmail.com
EMAIL_HOST_PASSWORD=xxxx xxxx xxxx xxxx
DEFAULT_FROM_EMAIL=your-email@gmail.com

# Other existing environment variables
DEBUG=True
SECRET_KEY=your-secret-key
DATABASE_NAME=connect2give_db
DATABASE_USER=root
DATABASE_PASSWORD=
DATABASE_HOST=localhost
DATABASE_PORT=3306
```

### Important Notes
- Replace `your-email@gmail.com` with your actual Gmail address
- Paste the 16-character app password (with or without spaces - both work)
- Keep this file secure - **Add to `.gitignore`**

---

## Step 3: Verify Settings

Ensure these are already in place:

1. **Templates Directory Structure**
   ```
   templates/
   ├── emails/
   │   ├── volunteer_invitation.html      ✅ Exists
   │   └── volunteer_password_reset.html  ✅ Exists
   ├── auth/
   ├── ngo/
   └── ...
   ```

2. **NGO View Function** (`portal/views/ngo_views.py`)
   - Function: `ngo_register_volunteer` (Line 106+)
   - Sends email with credentials
   - Creates volunteer profile
   - ✅ All working

---

## Step 4: Test the Email Feature

### Manual Testing

1. **Start Django Server**
   ```bash
   python manage.py runserver
   ```

2. **Log in as NGO**
   - Navigate to NGO dashboard

3. **Register a Volunteer**
   - Fill form with test data:
     - Full Name: John Doe
     - Email: your-test-email@gmail.com
     - Phone: 9876543210
     - Aadhar: 123456789012

4. **Check Email**
   - Look for email from `DEFAULT_FROM_EMAIL`
   - Should have credentials and login link

### Using Django Shell (Advanced)

```bash
python manage.py shell
```

```python
from django.core.mail import send_mail
from django.conf import settings

send_mail(
    'Test Email',
    'This is a test message',
    settings.DEFAULT_FROM_EMAIL,
    ['your-email@example.com'],
    fail_silently=False,
)
```

---

## Alternative Email Providers

### SendGrid
```env
EMAIL_BACKEND=sendgrid_backend.SendgridBackend
SENDGRID_API_KEY=your-sendgrid-api-key
DEFAULT_FROM_EMAIL=noreply@yourdomain.com
```

### AWS SES
```env
EMAIL_BACKEND=django_ses.SESBackend
AWS_ACCESS_KEY_ID=your-key
AWS_SECRET_ACCESS_KEY=your-secret
AWS_SES_REGION_NAME=us-east-1
AWS_SES_REGION_ENDPOINT=email.us-east-1.amazonaws.com
```

---

## Troubleshooting

### Error: "No module named 'sendgrid_backend'"
**Solution:** Use Gmail SMTP as shown in Step 1

### Error: "530 5.7.0 Authentication failed"
**Possible causes:**
- Wrong email/password
- 2FA not enabled
- App password not used
- **Solution:** Regenerate app password from Google Account

### Email Not Sending (but no error)
- Check `fail_silently=False` in send_mail() to see actual errors
- Check email template file exists at correct path
- Verify `DEFAULT_FROM_EMAIL` in settings.py

### Test SMTP Connection (Python)
```python
import smtplib

try:
    server = smtplib.SMTP('smtp.gmail.com', 587)
    server.starttls()
    server.login('your-email@gmail.com', 'your-app-password')
    print("✅ SMTP Connection Successful!")
    server.quit()
except Exception as e:
    print(f"❌ Connection Failed: {e}")
```

---

## Files Involved in Email Feature

### Backend Files
1. **portal/views/ngo_views.py** - `ngo_register_volunteer()` function
2. **portal/forms.py** - `NGORegisterVolunteerForm` validation
3. **portal/models.py** - `VolunteerProfile` model
4. **food_donation_project/settings.py** - Email configuration

### Template Files
1. **templates/emails/volunteer_invitation.html** - Welcome email
2. **templates/emails/volunteer_password_reset.html** - Password reset email

### URL Routes
- `portal/urls.py` - Route: `/dashboard/ngo/register-volunteer/`

---

## Email Content Details

### Volunteer Invitation Email

**Subject:** "Welcome to Connect2Give - Your Account Details"

**Contains:**
- Volunteer's name
- Username (auto-generated)
- Temporary password (12 random characters)
- NGO name
- Login URL
- Instructions (4 steps)
- Action button

**Styling:**
- Professional blue header (#0284c7)
- Responsive design (mobile-friendly)
- Clear credentials box with monospace font

---

## Production Deployment Notes

1. **Use Environment Variables** - Never hardcode email credentials
2. **Enable 2FA** on Gmail account
3. **Use App Password** - NOT your regular Gmail password
4. **Set `fail_silently=False`** during testing
5. **Monitor Email Bounces** - Check spam filters
6. **Add SPF/DKIM records** for custom domain emails

---

## Security Best Practices

- Keep `.env` file in `.gitignore`
- Rotate app passwords regularly
- Use separate email for notifications
- Monitor failed authentication attempts
- Enable 2FA on email account
- Test email delivery before production

---

## Summary

The email system is **production-ready**:
- ✅ Automatic credential generation
- ✅ Professional HTML templates
- ✅ Secure password handling
- ✅ Error handling with fallback
- ✅ Configurable via environment variables

Just add your Gmail SMTP credentials to `.env` and the system will automatically send welcome emails to all newly registered volunteers!
