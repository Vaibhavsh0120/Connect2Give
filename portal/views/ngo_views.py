# portal/views/ngo_views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.db.models import Q, Count
from django.contrib import messages
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.conf import settings
from django.db import transaction, IntegrityError
import secrets
import string
import socket  # Imported to help catch network errors
from ..models import DonationCamp, Donation, NGOProfile, VolunteerProfile, User, NGOVolunteer
from ..forms import DonationCampForm, NGOProfileForm, NGORegisterVolunteerForm
from ..decorators import user_type_required

@login_required(login_url='login_page')
@user_type_required('NGO')
def ngo_dashboard_overview(request):
    ngo_profile = request.user.ngo_profile
    stats = {
        'active_camps': DonationCamp.objects.filter(ngo=ngo_profile, is_active=True).count(),
        'total_volunteers': ngo_profile.volunteers.count(),
        'donations_to_verify': Donation.objects.filter(target_camp__ngo=ngo_profile, status='VERIFYING').count(),
        'total_donations_received': Donation.objects.filter(target_camp__ngo=ngo_profile, status='DELIVERED').count()
    }
    context = {'stats': stats}
    return render(request, 'ngo/dashboard_overview.html', context)

@login_required(login_url='login_page')
@user_type_required('NGO')
def ngo_manage_camps(request):
    ngo_profile = request.user.ngo_profile
    view_param = request.GET.get('view', None)

    if request.method == 'POST':
        form = DonationCampForm(request.POST)
        if form.is_valid():
            camp = form.save(commit=False)
            camp.ngo = ngo_profile
            camp.save()
            messages.success(request, 'New camp created successfully!')
            return redirect('ngo_manage_camps')
    else:
        form = DonationCampForm()

    # Optimized queries with select_related for foreign keys
    active_camps = DonationCamp.objects.filter(ngo=ngo_profile, is_active=True).order_by('start_time')
    completed_camps = DonationCamp.objects.filter(ngo=ngo_profile, is_active=False).order_by('-completed_at')
    donations_to_verify = Donation.objects.filter(
        target_camp__ngo=ngo_profile, 
        status='VERIFYING'
    ).select_related('restaurant', 'assigned_volunteer', 'target_camp').order_by('delivered_at')
    delivered_donations = Donation.objects.filter(
        target_camp__ngo=ngo_profile, 
        status='DELIVERED'
    ).select_related('restaurant', 'assigned_volunteer', 'target_camp').order_by('-delivered_at')[:50]
    
    context = {
        'form': form, 
        'active_camps': active_camps, 
        'completed_camps': completed_camps, 
        'donations_to_verify': donations_to_verify,
        'delivered_donations': delivered_donations,
        'active_tab': view_param
    }
    return render(request, 'ngo/manage_camps.html', context)

@login_required(login_url='login_page')
@user_type_required('NGO')
def ngo_manage_volunteers(request):
    ngo_profile = request.user.ngo_profile
    # Optimized query with annotation for active deliveries count
    registered_volunteers = ngo_profile.volunteers.annotate(
        active_deliveries=Count(
            'assigned_donations', 
            filter=Q(assigned_donations__status__in=['ACCEPTED', 'COLLECTED'])
        )
    ).order_by('full_name')
    context = {'volunteers': registered_volunteers}
    return render(request, 'ngo/manage_volunteers.html', context)

@login_required(login_url='login_page')
@user_type_required('NGO')
def ngo_profile(request):
    profile = get_object_or_404(NGOProfile, user=request.user)

    if request.method == 'POST':
        form = NGOProfileForm(request.POST, request.FILES, instance=profile)
        
        # Handle username update
        new_username = request.POST.get('username', '').strip()
        username_error = None
        
        if new_username and new_username != request.user.username:
            # Check if username is already taken
            if User.objects.filter(username=new_username).exclude(pk=request.user.pk).exists():
                username_error = 'This username is already taken.'
            elif len(new_username) > 150:
                username_error = 'Username must be 150 characters or fewer.'
            else:
                request.user.username = new_username
                request.user.save()
        
        if form.is_valid() and not username_error:
            form.save()
            messages.success(request, 'Your profile has been updated successfully!')
            return redirect('ngo_profile')
        elif username_error:
            messages.error(request, username_error)
    else:
        form = NGOProfileForm(instance=profile)

    context = {'form': form}
    return render(request, 'ngo/profile.html', context)

@login_required(login_url='login_page')
@user_type_required('NGO')
def ngo_settings(request):
    return render(request, 'ngo/settings.html')

@login_required(login_url='login_page')
@user_type_required('NGO')
def ngo_register_volunteer(request):
    """NGO portal to register new volunteers with atomic rollback and human-readable errors"""
    ngo_profile = request.user.ngo_profile
    error_popup = None
    
    if request.method == 'POST':
        form = NGORegisterVolunteerForm(request.POST, request.FILES)
        if form.is_valid():
            try:
                # TRANSACTION BLOCK: All or Nothing
                with transaction.atomic():
                    # 1. Generate Creds
                    temp_password = ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(12))
                    username = form.cleaned_data['username']
                    
                    # 2. Create User
                    user = User.objects.create_user(
                        username=username,
                        email=form.cleaned_data['email'],
                        password=temp_password,
                        user_type=User.UserType.VOLUNTEER,
                        first_name=form.cleaned_data['full_name'].split(' ')[0],
                        last_name=' '.join(form.cleaned_data['full_name'].split(' ')[1:]),
                        must_change_password=True
                    )
                    
                    # 3. Create Profile
                    volunteer_profile = VolunteerProfile.objects.create(
                        user=user,
                        full_name=form.cleaned_data['full_name'],
                        email=form.cleaned_data['email'],
                        phone_number=form.cleaned_data['phone_number'],
                        aadhar_number=form.cleaned_data['aadhar_number'],
                        skills=form.cleaned_data.get('skills', ''),
                        address=form.cleaned_data.get('address', ''),
                        latitude=form.cleaned_data.get('latitude'),
                        longitude=form.cleaned_data.get('longitude'),
                        registered_ngo=ngo_profile
                    )
                    
                    # 4. Handle Image
                    if form.cleaned_data.get('profile_picture'):
                        volunteer_profile.profile_picture = form.cleaned_data['profile_picture']
                        volunteer_profile.save()
                    
                    # 5. Link to NGO
                    NGOVolunteer.objects.create(ngo=ngo_profile, volunteer=volunteer_profile)
                    
                    # 6. Send Email
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
                
                # Success
                messages.success(request, f'Volunteer {form.cleaned_data["full_name"]} registered successfully! Invitation email sent.')
                return redirect('ngo_register_volunteer')
                
            except Exception as e:
                # DB has rolled back automatically. Now assume friendly error.
                error_str = str(e)
                
                # Human Readable Mappings
                if "Connection refused" in error_str or "111" in error_str or "61" in error_str:
                    error_popup = "Connection Failed: Could not connect to the email server. Please check your internet connection or email settings."
                elif "AuthenticationError" in error_str or "535" in error_str:
                    error_popup = "Email Login Failed: The system could not log in to the email account. Check the 'EMAIL_HOST_PASSWORD' in your settings."
                elif "gaierror" in error_str or "Temporary failure" in error_str:
                    error_popup = "DNS Error: Could not find the email server. Please check your internet connection."
                elif "Duplicate entry" in error_str:
                    # Catch-all for database integrity errors that slipped past the form
                    error_popup = "Registration Failed: A volunteer with this information (Email, Username, or Aadhar) already exists."
                else:
                    # Fallback for other errors
                    error_popup = f"Registration Failed: {error_str}"
    else:
        form = NGORegisterVolunteerForm()
    
    # Get registered volunteers
    registered_volunteers = VolunteerProfile.objects.filter(registered_ngo=ngo_profile).select_related('user').order_by('-created_at')
    
    context = {
        'form': form,
        'registered_volunteers': registered_volunteers,
        'error_popup': error_popup,
    }
    return render(request, 'ngo/register_volunteer.html', context)

@login_required(login_url='login_page')
@user_type_required('NGO')
def ngo_reset_volunteer_password(request, volunteer_id):
    """Reset volunteer password and resend invitation"""
    ngo_profile = request.user.ngo_profile
    volunteer_profile = get_object_or_404(VolunteerProfile, id=volunteer_id, registered_ngo=ngo_profile)
    
    if request.method == 'POST':
        # Generate new temporary password
        temp_password = ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(12))
        
        # Update user password
        volunteer_profile.user.set_password(temp_password)
        volunteer_profile.user.must_change_password = True
        volunteer_profile.user.save()
        
        # Send email with new credentials
        subject = f'Connect2Give - Password Reset'
        context = {
            'volunteer_name': volunteer_profile.full_name,
            'username': volunteer_profile.user.username,
            'temp_password': temp_password,
            'ngo_name': ngo_profile.ngo_name,
            'login_url': request.build_absolute_uri('/login/'),
        }
        html_message = render_to_string('emails/volunteer_password_reset.html', context)
        plain_message = strip_tags(html_message)
        
        recipient_email = volunteer_profile.email
        if recipient_email:
            send_mail(
                subject,
                plain_message,
                settings.DEFAULT_FROM_EMAIL,
                [recipient_email],
                html_message=html_message,
                fail_silently=False,
            )
        
        messages.success(request, f'New password sent to {volunteer_profile.full_name}')
        return redirect('ngo_register_volunteer')
    
    context = {'volunteer': volunteer_profile}
    return render(request, 'ngo/reset_volunteer_password.html', context)