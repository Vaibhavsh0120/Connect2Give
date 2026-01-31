# portal/views/tracking_views.py
"""
Real-time Geolocation Tracking Views
"""

import json
from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.utils import timezone
from django.db import transaction

from ..models import VolunteerProfile, Donation
from ..decorators import user_type_required


@login_required(login_url='login_page')
@user_type_required('VOLUNTEER')
@require_http_methods(["POST"])
def update_volunteer_location(request):
    """
    API endpoint to update volunteer's real-time location
    Called by geolocation_tracker.js periodically
    """
    try:
        data = json.loads(request.body)
        latitude = data.get('latitude')
        longitude = data.get('longitude')
        accuracy = data.get('accuracy')
        
        # Validate coordinates
        if not latitude or not longitude:
            return JsonResponse({
                'success': False,
                'message': 'Invalid coordinates'
            }, status=400)
        
        # Ensure coordinates are within valid range
        if not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
            return JsonResponse({
                'success': False,
                'message': 'Coordinates out of range'
            }, status=400)
        
        volunteer_profile = request.user.volunteer_profile
        
        with transaction.atomic():
            # Update volunteer location
            volunteer_profile.latitude = float(latitude)
            volunteer_profile.longitude = float(longitude)
            volunteer_profile.last_location_update = timezone.now()
            volunteer_profile.save()
            
            print(f"[v0] Updated location for {volunteer_profile.full_name}: {latitude}, {longitude}")
        
        return JsonResponse({
            'success': True,
            'message': 'Location updated successfully'
        })
    
    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'message': 'Invalid JSON'
        }, status=400)
    except Exception as e:
        print(f"[v0] Error updating location: {e}")
        return JsonResponse({
            'success': False,
            'message': f'Error: {str(e)}'
        }, status=500)


@login_required(login_url='login_page')
@user_type_required('VOLUNTEER')
def volunteer_active_tracking(request):
    """
    Dashboard showing volunteer's current tracking status
    """
    volunteer_profile = request.user.volunteer_profile
    
    # Get active donations
    active_donations = Donation.objects.filter(
        assigned_volunteer=volunteer_profile,
        status__in=['ACCEPTED', 'COLLECTED']
    ).select_related('restaurant').count()
    
    context = {
        'volunteer': volunteer_profile,
        'active_donations': active_donations,
        'current_latitude': volunteer_profile.latitude,
        'current_longitude': volunteer_profile.longitude,
        'last_update': volunteer_profile.last_location_update
    }
    
    return render(request, 'volunteer/active_tracking.html', context)


@login_required(login_url='login_page')
@user_type_required('NGO')
def ngo_volunteer_locations(request):
    """
    NGO dashboard showing real-time locations of active volunteers
    """
    ngo_profile = request.user.ngo_profile
    
    # Get all volunteers registered with this NGO
    volunteers = ngo_profile.volunteers.filter(
        user__is_active=True
    ).select_related('user').order_by('-last_location_update')
    
    # Get active deliveries
    from ..models import Donation
    active_deliveries = Donation.objects.filter(
        target_camp__ngo=ngo_profile,
        status__in=['ACCEPTED', 'COLLECTED', 'VERIFICATION_PENDING']
    ).select_related('assigned_volunteer', 'restaurant').count()
    
    # Prepare location data for map
    locations_data = []
    for volunteer in volunteers:
        if volunteer.latitude and volunteer.longitude:
            locations_data.append({
                'id': volunteer.id,
                'name': volunteer.full_name,
                'latitude': volunteer.latitude,
                'longitude': volunteer.longitude,
                'last_update': volunteer.last_location_update.isoformat() if volunteer.last_location_update else None,
                'is_active': volunteer.user.is_active
            })
    
    context = {
        'ngo_profile': ngo_profile,
        'volunteers': volunteers,
        'locations_json': json.dumps(locations_data),
        'active_deliveries': active_deliveries,
        'total_volunteers': volunteers.count()
    }
    
    return render(request, 'ngo/volunteer_locations.html', context)


@login_required(login_url='login_page')
@user_type_required('NGO')
def get_volunteers_locations_api(request):
    """
    API endpoint for getting volunteer locations (AJAX)
    """
    try:
        ngo_profile = request.user.ngo_profile
        
        volunteers = ngo_profile.volunteers.filter(
            user__is_active=True
        ).values('id', 'full_name', 'latitude', 'longitude', 'last_location_update')
        
        locations = []
        for volunteer in volunteers:
            if volunteer['latitude'] and volunteer['longitude']:
                locations.append({
                    'id': volunteer['id'],
                    'name': volunteer['full_name'],
                    'latitude': float(volunteer['latitude']),
                    'longitude': float(volunteer['longitude']),
                    'last_update': volunteer['last_location_update'].isoformat() if volunteer['last_location_update'] else None
                })
        
        return JsonResponse({
            'success': True,
            'locations': locations
        })
    
    except Exception as e:
        print(f"[v0] Error fetching locations: {e}")
        return JsonResponse({
            'success': False,
            'message': str(e)
        }, status=500)


@login_required(login_url='login_page')
@user_type_required('VOLUNTEER')
def volunteer_location_privacy_settings(request):
    """
    Volunteer settings for location sharing privacy
    """
    volunteer_profile = request.user.volunteer_profile
    
    if request.method == 'POST':
        # Update privacy settings
        allow_location_sharing = request.POST.get('allow_location_sharing') == 'on'
        share_with_ngos = request.POST.get('share_with_ngos') == 'on'
        
        volunteer_profile.allow_location_sharing = allow_location_sharing
        volunteer_profile.share_location_with_ngos = share_with_ngos
        volunteer_profile.save()
        
        return JsonResponse({
            'success': True,
            'message': 'Privacy settings updated'
        })
    
    context = {
        'volunteer': volunteer_profile
    }
    
    return render(request, 'volunteer/location_privacy.html', context)
