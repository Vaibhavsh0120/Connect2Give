# portal/views/__init__.py

# Import all views from the separated files
from .auth_views import *
from .restaurant_views import *
from .ngo_views import *
from .volunteer_views import *
from .api_views import *

# --- HELPER & PUBLIC VIEWS ---
from django.shortcuts import render, redirect
import json
from ..models import User, DonationCamp, RestaurantProfile, Donation
from django.utils import timezone
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.http import JsonResponse
from django.http import HttpResponse
from django.conf import settings
import os


# FIX 1: Update this function to correctly redirect new users
def get_user_dashboard_redirect(user):
    # Check for Superuser first to avoid registration redirect
    if user.is_superuser:
        return redirect('index')

    if user.user_type == User.UserType.RESTAURANT:
        return redirect('restaurant_dashboard')
    elif user.user_type == User.UserType.NGO:
        return redirect('ngo_dashboard_overview')
    elif user.user_type == User.UserType.VOLUNTEER:
        return redirect('volunteer_dashboard')
    else:
        # For new users (default 'ADMIN' type), redirect to complete their profile
        return redirect('register_step_2')

def index(request):
    # FIX 2: Add this check at the top of the index view
    # Only redirect to dashboard if authenticated AND NOT a superuser
    if request.user.is_authenticated and not request.user.is_superuser:
        return get_user_dashboard_redirect(request.user)
        
    # The rest of the function is for non-logged-in users OR Superusers
    active_camps = DonationCamp.objects.filter(is_active=True).select_related('ngo')
    all_restaurants = RestaurantProfile.objects.filter(latitude__isnull=False, longitude__isnull=False)
    
    camps_map_data = []
    if active_camps.exists():
        camps_map_data = [{"lat": c.latitude, "lon": c.longitude, "name": c.name, "ngo": c.ngo.ngo_name, "address": c.location_address, "start": c.start_time.strftime('%d %b %Y, %H:%M')} for c in active_camps if c.latitude and c.longitude]
    
    restaurants_map_data = []
    if all_restaurants.exists():
        restaurants_map_data = [{"lat": r.latitude, "lon": r.longitude, "name": r.restaurant_name, "address": r.address} for r in all_restaurants]
    
    context = {'camps_map_data': json.dumps(camps_map_data), 'restaurants_map_data': json.dumps(restaurants_map_data)}
    return render(request, 'index.html', context)

# Action views used by multiple user types
@login_required(login_url='login_page')
def mark_camp_as_completed(request, camp_id):
    if request.user.user_type != 'NGO': return redirect('index')
    camp = get_object_or_404(DonationCamp, pk=camp_id, ngo=request.user.ngo_profile)
    if request.method == 'POST':
        camp.is_active = False
        camp.completed_at = timezone.now()
        camp.save()
    redirect_url = reverse('ngo_manage_camps') + '?view=history'
    return redirect(redirect_url)

@login_required(login_url='login_page')
def confirm_delivery(request, donation_id):
    if request.user.user_type != 'NGO': return redirect('index')
    donation = get_object_or_404(Donation, pk=donation_id, target_camp__ngo=request.user.ngo_profile)
    if request.method == 'POST':
        donation.status = 'DELIVERED'
        donation.save()
    redirect_url = reverse('ngo_manage_camps') + '?view=verification'
    return redirect(redirect_url)

@login_required(login_url='login_page')
def rate_donation(request, donation_id):
    """NGO rates a completed donation delivery, always returns JSON."""
    if request.user.user_type != 'NGO' or request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Unauthorized request.'}, status=403)
    
    try:
        donation = get_object_or_404(Donation, pk=donation_id, target_camp__ngo=request.user.ngo_profile, status='DELIVERED')
        
        rating = request.POST.get('rating')
        review = request.POST.get('review', '')
        
        if not rating:
            return JsonResponse({'success': False, 'message': 'Rating is a required field.'}, status=400)

        rating = int(rating)
        if not (1 <= rating <= 5):
            raise ValueError("Rating must be between 1 and 5.")
        
        donation.rating = rating
        donation.review = review
        donation.save()
        
        return JsonResponse({'success': True, 'message': 'Rating submitted successfully!'})

    except (ValueError, TypeError) as e:
        return JsonResponse({'success': False, 'message': f'Invalid data: {e}'}, status=400)
    except Donation.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'Donation not found or already rated.'}, status=404)
    except Exception as e:
        return JsonResponse({'success': False, 'message': 'An unexpected error occurred.'}, status=500)

# --- NEW SERVICE WORKER VIEW ---
def serve_sw(request):
    try:
        sw_path = os.path.join(settings.BASE_DIR, 'static', 'js', 'sw.js')
        with open(sw_path, 'r') as f:
            return HttpResponse(f.read(), content_type='application/javascript')
    except FileNotFoundError:
        return HttpResponse("Service worker not found.", status=404, content_type='text/plain')