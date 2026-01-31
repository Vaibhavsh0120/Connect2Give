# Connect2Give - Implementation Checklist

## Files Modified to Fix Errors

### ✅ 1. portal/views/auth_views.py
**Status:** FIXED
- **Line 4:** Added `from django.contrib.auth.decorators import login_required`
- **Lines 9-12:** Added email imports for future use
- **Error Fixed:** `NameError: name 'login_required' is not defined`
- **Date Modified:** Today

---

## Email Feature - Complete Implementation Guide

### Part 1: Gmail Setup (One-Time Only)

#### Step 1.1: Enable 2-Step Verification
```
1. Go to https://myaccount.google.com
2. Click "Security" in the left sidebar
3. Under "Signing in to Google", find "2-Step Verification"
4. Click it and follow the prompts to enable
5. You may be asked to verify your identity
```

#### Step 1.2: Generate App Password
```
1. After 2FA is enabled, search for "App passwords" in Google Account
2. You should see a dropdown menu with Mail and Windows Computer
3. Select "Mail" and your operating system
4. Google will display a 16-character password
5. Copy this password (you'll need it next)
```

**Example App Password:** `wxyz abcd efgh ijkl`

---

### Part 2: Project Configuration

#### Step 2.1: Create .env File

**Location:** Project root (same directory as `manage.py`)

**Command:**
```bash
# Windows
type nul > .env

# Linux/Mac
touch .env
```

#### Step 2.2: Add Email Configuration to .env

**File Content:**
```env
# ============================================
# EMAIL CONFIGURATION
# ============================================
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=your-email@gmail.com
EMAIL_HOST_PASSWORD=xxxx xxxx xxxx xxxx
DEFAULT_FROM_EMAIL=your-email@gmail.com

# ============================================
# EXISTING CONFIGURATION (Keep These)
# ============================================
DEBUG=True
SECRET_KEY=your-secret-key-here
DB_NAME=connect2give_db
DB_USER=root
DB_PASSWORD=
DB_HOST=localhost
DB_PORT=3306
```

**Important:** 
- Replace `your-email@gmail.com` with your actual Gmail address
- Replace `xxxx xxxx xxxx xxxx` with the 16-character app password from Step 1.2

#### Step 2.3: Add .env to .gitignore

**File:** `.gitignore`

**Add this line:**
```
.env
```

**Command:**
```bash
echo ".env" >> .gitignore
```

---

### Part 3: Test the System

#### Step 3.1: Start Django Server
```bash
python manage.py runserver
```

**Expected Output:**
```
System check identified no issues (0 silenced).
Starting development server at http://127.0.0.1:8000/
Quit the server with CTRL-BREAK.
```

#### Step 3.2: Test Volunteer Registration

1. **Log in as NGO**
   - URL: `http://localhost:8000/login/`
   - Use NGO credentials

2. **Go to Volunteer Registration**
   - URL: `http://localhost:8000/dashboard/ngo/register-volunteer/`
   - OR click "Register Volunteer" in NGO dashboard

3. **Fill Registration Form**
   ```
   Full Name: John Doe
   Email: test-email@gmail.com
   Phone Number: 9876543210
   Aadhar Number: 123456789012
   ```

4. **Submit Form**
   - Click "Register Volunteer" button
   - You should see success message

5. **Check Email**
   - Go to test-email@gmail.com inbox
   - Look for email from `DEFAULT_FROM_EMAIL`
   - Subject: "Welcome to Connect2Give - Your Account Details"

6. **Verify Email Contains**
   - Volunteer's name
   - Username (auto-generated)
   - Temporary password
   - Login URL
   - Welcome instructions

---

## Email Feature - What Happens Automatically

### When NGO Clicks "Register Volunteer":

```
Form Submission
    ↓
Backend Processing (ngo_views.py - Line 106)
    ├─ Generate: Temporary Password (12 chars, random)
    ├─ Generate: Unique Username (from email)
    ├─ Create: User Account in Database
    ├─ Create: Volunteer Profile
    └─ Send: Welcome Email
        ├─ Template: volunteer_invitation.html
        ├─ To: Volunteer's email address
        ├─ From: DEFAULT_FROM_EMAIL from .env
        └─ Subject: Welcome to Connect2Give - Your Account Details
    ↓
Success Message Shown to NGO
    ↓
Volunteer Receives Email with Credentials
    ↓
Volunteer Logs In
    ↓
Forced to Change Password (must_change_password=True)
    ↓
Account Active!
```

---

## Email Files Already in Place

### Backend Code
- ✅ **portal/views/ngo_views.py**
  - Function: `ngo_register_volunteer()` (Line 106+)
  - Sends email automatically
  
- ✅ **portal/forms.py**
  - Form: `NGORegisterVolunteerForm`
  - Validates: Email uniqueness, Aadhar format
  
- ✅ **portal/models.py**
  - Model: `VolunteerProfile`
  - Field: `registered_ngo` (FK to NGO)
  - Field: `aadhar_number` (unique)

### Email Templates
- ✅ **templates/emails/volunteer_invitation.html**
  - Beautiful HTML email
  - Shows credentials
  - Mobile-responsive
  - Professional styling
  
- ✅ **templates/emails/volunteer_password_reset.html**
  - Password reset email
  - Used by password reset function

### Configuration
- ✅ **food_donation_project/settings.py**
  - Email configuration (uses .env)
  - Uses environment variables
  - Supports multiple email backends

### Database
- ✅ Migrations already created
  - Fields for new features added
  - Ready for database sync

---

## Quick Reference: Email Sending Code

### Location
**File:** `portal/views/ngo_views.py`
**Lines:** 149-168

### Code
```python
# Send email with credentials
subject = f'Welcome to Connect2Give - Your Account Details'
context = {
    'volunteer_name': form.cleaned_data['full_name'],
    'username': username,
    'temp_password': temp_password,
    'ngo_name': ngo_profile.ngo_name,
    'login_url': request.build_absolute_uri('/login/'),
}
html_message = render_to_string('emails/volunteer_invitation.html', context)
plain_message = strip_tags(html_message)

send_mail(
    subject,
    plain_message,
    settings.DEFAULT_FROM_EMAIL,
    [form.cleaned_data['email']],
    html_message=html_message,
    fail_silently=False,
)
```

---

## Troubleshooting Guide

### Issue 1: Server Won't Start - "NameError: login_required not defined"
**Status:** ✅ FIXED
- auth_views.py has been updated
- Just run server again

### Issue 2: Email Not Sending - No Error in Console
**Possible Causes:**
1. `.env` file not created
2. `.env` file in wrong location (should be in project root)
3. Email credentials are wrong
4. 2FA not enabled on Gmail

**Solution:**
- Verify .env exists in same directory as manage.py
- Verify email and password are correct
- Check Gmail account settings

### Issue 3: "530 5.7.0 Authentication failed"
**Cause:** Wrong Gmail credentials
**Solutions:**
1. Verify you're using app password (not regular Gmail password)
2. Verify email address matches your Gmail
3. Regenerate app password from Google Account
4. Ensure email in .env has exact 16 characters (with spaces ok)

### Issue 4: "SMTP Connection refused"
**Cause:** Gmail SMTP server unreachable
**Solutions:**
1. Check internet connection
2. Verify EMAIL_HOST is "smtp.gmail.com"
3. Verify EMAIL_PORT is 587
4. Verify EMAIL_USE_TLS is True

### Issue 5: Template Not Found Error
**Cause:** Email template missing
**Solution:** 
- Check `/templates/emails/volunteer_invitation.html` exists
- Verify template has correct filename
- Check TEMPLATES setting in settings.py

---

## Production Checklist

Before deploying to production:

- [ ] Email configuration tested locally
- [ ] `.env` file added to `.gitignore`
- [ ] `.env` file NOT committed to git
- [ ] `fail_silently=False` in send_mail (for debugging)
- [ ] Email logs monitored
- [ ] Spam filter configured
- [ ] Sender email verified on email service
- [ ] Error handling in place
- [ ] Email templates finalized
- [ ] Test email sent to admin

---

## Email Customization

### Change Sender Email
**File:** `.env`
```env
DEFAULT_FROM_EMAIL=custom-email@gmail.com
```

### Change Email Subject
**File:** `portal/views/ngo_views.py`, Line 150
```python
subject = f'Welcome to Connect2Give - Your Account Details'
# Change to:
subject = f'Your {ngo_profile.ngo_name} Volunteer Account'
```

### Change Email Template
**File:** `templates/emails/volunteer_invitation.html`
- Edit HTML directly
- Keep {{ variable }} placeholders
- Test rendering

### Add More Template Variables
1. Add variable to context dictionary in ngo_views.py
2. Use in template with {{ variable_name }}

---

## Files Modified Summary

| File | Change | Status |
|------|--------|--------|
| portal/views/auth_views.py | Added login_required import | ✅ Fixed |
| portal/views/ngo_views.py | Already has email code | ✅ Ready |
| portal/forms.py | Already has validation | ✅ Ready |
| portal/models.py | Already has fields | ✅ Ready |
| templates/emails/volunteer_invitation.html | Already exists | ✅ Ready |
| food_donation_project/settings.py | Already configured | ✅ Ready |

---

## Next Steps

### Immediate (5 minutes)
1. ✅ Fix was applied to auth_views.py
2. Create `.env` file in project root
3. Add Gmail SMTP credentials

### Short Term (15 minutes)
1. Start Django server
2. Test volunteer registration
3. Verify email is received

### Medium Term (Next session)
1. Monitor email delivery
2. Customize email template if needed
3. Set up email logging
4. Test error scenarios

### Long Term (Production)
1. Set up SendGrid or AWS SES for production
2. Configure email bounce handling
3. Set up email analytics
4. Monitor delivery rates

---

## Support Resources

### Gmail SMTP Setup
- https://support.google.com/accounts/answer/185833

### Django Email Documentation
- https://docs.djangoproject.com/en/stable/topics/email/

### SendGrid (Alternative)
- https://sendgrid.com/

### AWS SES (Alternative)
- https://aws.amazon.com/ses/

---

## Summary

The email feature is **COMPLETE and READY TO USE**:
- ✅ All code is implemented
- ✅ Templates are ready
- ✅ Configuration is in place
- ✅ Error fixed in auth_views.py

**All you need to do:**
1. Create `.env` file
2. Add Gmail credentials
3. Test by registering a volunteer
4. Check email for welcome message

That's it! The system will automatically send emails whenever an NGO registers a volunteer.
