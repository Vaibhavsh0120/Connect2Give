# portal/views/auth_views.py
from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.contrib.messages import get_messages
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.conf import settings
from ..models import User, RestaurantProfile, NGOProfile, VolunteerProfile

def get_user_dashboard_redirect(user):
    # If the user is a superuser (Admin), redirect to index to show the restriction message
    if user.is_superuser:
        return redirect('index')

    if user.user_type == User.UserType.RESTAURANT:
        return redirect('restaurant_dashboard')
    elif user.user_type == User.UserType.NGO:
        return redirect('ngo_dashboard_overview')
    elif user.user_type == User.UserType.VOLUNTEER:
        return redirect('volunteer_dashboard')
    else:
        # If user type is not set, redirect to complete the profile
        return redirect('register_step_2')

@require_http_methods(["GET", "POST"])
def check_username_availability(request):
    """AJAX endpoint to check if username is available"""
    if request.method == 'GET':
        username = request.GET.get('username', '').strip().lower()
        if not username:
            return JsonResponse({'available': False, 'message': 'Username is required'})
        
        if len(username) < 3:
            return JsonResponse({'available': False, 'message': 'Username must be at least 3 characters'})
        
        available = not User.objects.filter(username=username).exists()
        return JsonResponse({
            'available': available,
            'message': 'Username is available' if available else 'Username is already taken'
        })
    return JsonResponse({'error': 'Invalid request'}, status=400)

def register_step_1(request):
    if request.user.is_authenticated:
        return get_user_dashboard_redirect(request.user)
    if request.method == 'POST':
        full_name = request.POST.get('full_name')
        email = request.POST.get('email')
        # Username collection removed from Step 1
        password = request.POST.get('password')
        password2 = request.POST.get('password2')

        if password != password2:
            return render(request, 'auth/register_step_1.html', {'error': 'Passwords do not match.'})
        if User.objects.filter(email=email).exists():
            return render(request, 'auth/register_step_1.html', {'error': 'Email already registered.'})

        request.session['registration_data'] = {
            'full_name': full_name,
            'email': email,
            'password': password,
            # Username is no longer stored here; collected in Step 2
        }
        return redirect('register_step_2')
    return render(request, 'auth/register_step_1.html')

def register_step_2(request):
    # This view now handles both manual and Google signup completions.
    # DISABLED PUBLIC VOLUNTEER SIGNUP - NGOs only
    
    # For manual signup, data is in the session.
    registration_data = request.session.get('registration_data')

    # For Google signup, the user is already authenticated but has no role.
    if request.user.is_authenticated and not registration_data:
        # Check if the user has already completed this step.
        if request.user.user_type != User.UserType.ADMIN:
             return get_user_dashboard_redirect(request.user)
    elif not registration_data and not request.user.is_authenticated:
        return redirect('register_step_1')


    if request.method == 'POST':
        user_type = request.POST.get('user_type')
        
        # Block public volunteer registration
        if user_type == User.UserType.VOLUNTEER:
            messages.error(request, 'Public volunteer signup is disabled. Please ask an NGO to register you.')
            return render(request, 'auth/register_step_2.html', {'user_type_error': True})
        
        latitude = request.POST.get('latitude') or None
        longitude = request.POST.get('longitude') or None
        address = request.POST.get('address')
        
        # Get and validate username
        username = request.POST.get('username', '').strip().lower()
        username_error = None
        
        # Validate username
        if not username or len(username) < 3:
            username_error = 'Username must be at least 3 characters.'
        elif len(username) > 150:
            username_error = 'Username must be 150 characters or fewer.'
        elif User.objects.filter(username=username).exists():
            # If Google user is just updating their profile but keeping their generated username (if it matches), skip check
            if not (request.user.is_authenticated and request.user.username == username):
                username_error = 'This username is already taken.'
        elif not username.replace('_', '').replace('-', '').isalnum():
            username_error = 'Username can only contain letters, numbers, underscores, and hyphens.'
        
        if username_error:
            return render(request, 'auth/register_step_2.html', {'error': username_error})
        
        user = None
        if registration_data: # Manual registration flow
            # Username is now collected in Step 2, so we use the 'username' variable from POST directly.
            # Fallback to session is no longer needed for 'username', but kept for robustness if logic changes back.
            step1_username = registration_data.get('username', username)
            
            user = User.objects.create_user(
                username=step1_username,
                email=registration_data['email'],
                password=registration_data['password'],
                user_type=user_type,
                first_name=registration_data.get('full_name', '').split(' ')[0],
                last_name=' '.join(registration_data.get('full_name', '').split(' ')[1:])
            )
            del request.session['registration_data']

        elif request.user.is_authenticated: # Google registration flow
            user = request.user
            # Update username if user had auto-generated one
            if user.username != username:
                user.username = username
            user.user_type = user_type
            user.save()

        if user:
            if user_type == User.UserType.RESTAURANT:
                RestaurantProfile.objects.create(
                    user=user,
                    restaurant_name=request.POST.get('restaurant_name'),
                    address=address,
                    phone_number=request.POST.get('restaurant_phone_number'),
                    latitude=latitude,
                    longitude=longitude
                )
            elif user_type == User.UserType.NGO:
                # Validate contact_number is 10 digits
                contact_number = request.POST.get('contact_number', '').strip()
                if not contact_number.isdigit() or len(contact_number) != 10:
                    messages.error(request, 'Contact number must be exactly 10 digits.')
                    return render(request, 'auth/register_step_2.html', {'error': 'Invalid contact number.'})
                
                NGOProfile.objects.create(
                    user=user,
                    ngo_name=request.POST.get('ngo_name'),
                    registration_number=request.POST.get('registration_number'),
                    address=address,
                    contact_number=contact_number,
                    latitude=latitude,
                    longitude=longitude
                )
            
            messages.success(request, 'Registration successful! Please log in.')
            return redirect('login_page')

    context = {}
    if request.user.is_authenticated:
        context['user'] = request.user
        # Pre-fill username for Google signup (either their nickname or empty)
        context['prefill_username'] = request.user.username or request.user.first_name or ''

    return render(request, 'auth/register_step_2.html', context)


def login_page(request):
    if request.user.is_authenticated:
        # Check if user must change password
        if getattr(request.user, 'must_change_password', False):  # type: ignore
            return redirect('force_password_change')
        return get_user_dashboard_redirect(request.user)
        
    if request.method == 'POST':
        user = authenticate(request, username=request.POST.get('username'), password=request.POST.get('password'))
        if user is not None:
            login(request, user)
            # Check if user must change password
            user = User.objects.get(pk=user.pk)  # Re-fetch to get the custom User model type
            if user.must_change_password:  # type: ignore
                messages.warning(request, 'You must change your password before proceeding.')
                return redirect('force_password_change')
            messages.success(request, f'Successfully signed in as {user.username}.')
            return get_user_dashboard_redirect(user)
        else:
            return render(request, 'auth/login.html', {'error': 'Invalid username or password.'})
    return render(request, 'auth/login.html')

@login_required(login_url='login_page')
def force_password_change(request):
    """Force user to change password if must_change_password flag is True"""
    if not getattr(request.user, 'must_change_password', False):  # type: ignore
        return redirect('login_page')
    
    if request.method == 'POST':
        new_password = request.POST.get('new_password')
        new_password2 = request.POST.get('new_password2')
        
        if new_password != new_password2:
            messages.error(request, 'Passwords do not match.')
            return render(request, 'auth/force_password_change.html')
        
        if len(new_password) < 8:
            messages.error(request, 'Password must be at least 8 characters long.')
            return render(request, 'auth/force_password_change.html')
        
        request.user.set_password(new_password)
        request.user.must_change_password = False
        request.user.save()
        
        # Re-authenticate the user with new password
        login(request, request.user, backend='django.contrib.auth.backends.ModelBackend')
        
        messages.success(request, 'Password changed successfully!')
        return get_user_dashboard_redirect(request.user)
    
    return render(request, 'auth/force_password_change.html')

def logout_view(request):
    storage = get_messages(request)
    for message in storage:
        pass 
    if hasattr(storage, 'used'):
        storage.used = True # type: ignore

    logout(request)
    return redirect('index')

def google_callback(request):
    """Handle Google OAuth callback"""
    if request.user.is_authenticated:
        # If the user is new (user_type is still ADMIN), redirect to complete their profile
        if request.user.user_type == User.UserType.ADMIN and not hasattr(request.user, 'restaurant_profile') and not hasattr(request.user, 'ngo_profile') and not hasattr(request.user, 'volunteer_profile'):
            return redirect('register_step_2')
        return get_user_dashboard_redirect(request.user)
    return redirect('login_page')


@login_required(login_url='login_page')
def link_google_account(request):
    """Initiate Google linking for an already authenticated user"""
    # For users with email/password signup, link their Google account
    # This is typically handled by the social auth library
    messages.info(request, 'Click the "Link Google Account" button below to connect your Google account.')
    return redirect(request.META.get('HTTP_REFERER', 'volunteer_settings'))


@login_required(login_url='login_page')
def unlink_google_account(request):
    """Unlink Google account from user if they have a local password set"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Invalid request'}, status=400)
    
    try:
        user = request.user
        
        # Check if user has a password set
        if not user.has_usable_password():
            return JsonResponse({
                'success': False, 
                'message': 'Cannot unlink Google without a password. Set a password first.'
            }, status=400)
        
        # Try to remove Google social auth entry
        try:
            from allauth.socialaccount.models import SocialAccount
        except ImportError:
             return JsonResponse({'success': False, 'message': 'Social auth configuration error'}, status=500)

        try:
            social_auth = SocialAccount.objects.get(user=user, provider='google')
            social_auth.delete()
            return JsonResponse({'success': True, 'message': 'Google account unlinked'})
        except SocialAccount.DoesNotExist:
            return JsonResponse({
                'success': False, 
                'message': 'Google account is not linked'
            }, status=400)
        except Exception as e:
            return JsonResponse({
                'success': False, 
                'message': str(e)
            }, status=400)
    
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=500)


@login_required(login_url='login_page')
def set_password_after_google(request):
    """Allow Google-signed-up users to set a local password"""
    if request.method == 'POST':
        new_password = request.POST.get('new_password')
        new_password2 = request.POST.get('new_password2')
        
        if new_password != new_password2:
            messages.error(request, 'Passwords do not match.')
            return redirect(request.META.get('HTTP_REFERER', 'volunteer_settings'))
        
        if len(new_password) < 8:
            messages.error(request, 'Password must be at least 8 characters long.')
            return redirect(request.META.get('HTTP_REFERER', 'volunteer_settings'))
        
        request.user.set_password(new_password)
        request.user.save()
        
        messages.success(request, 'Password set successfully! You can now login with your email and password.')
        return redirect(request.META.get('HTTP_REFERER', 'volunteer_settings'))
    
    messages.error(request, 'Invalid request')
    return redirect('volunteer_settings')

@login_required
@require_http_methods(["POST"])
def delete_account(request):
    """Permanently delete the user account."""
    try:
        user = request.user
        # Log the user out before deleting to avoid session issues
        logout(request)
        # Delete the user (this should cascade to profiles like NGOProfile/RestaurantProfile)
        user.delete()
        return JsonResponse({'success': True, 'message': 'Account deleted successfully'})
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=500)