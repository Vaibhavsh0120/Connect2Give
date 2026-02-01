# portal/views/volunteer_views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from datetime import timedelta
import json
from ..models import Donation, DonationCamp, NGOProfile, VolunteerProfile
from ..forms import VolunteerProfileForm
from django.contrib import messages
from geopy.distance import geodesic
from django.http import JsonResponse
from django.db import transaction
from ..decorators import user_type_required
from django.conf import settings
from ..utils import RouteOptimizer, Location, build_route_map_data, get_route_optimizer


@login_required(login_url='login_page')
@user_type_required('VOLUNTEER')
def volunteer_dashboard(request):
    volunteer_profile = request.user.volunteer_profile
    
    stats = {
        'active_pickups': Donation.objects.filter(assigned_volunteer=volunteer_profile, status__in=['ACCEPTED', 'COLLECTED']).count(),
        'completed_deliveries': Donation.objects.filter(assigned_volunteer=volunteer_profile, status='DELIVERED').count(),
        'registered_ngos': volunteer_profile.registered_ngos.count(),
        'available_donations': Donation.objects.filter(status='PENDING').count(),
    }

    # Optimized queries with select_related
    available_donations = Donation.objects.filter(status='PENDING').select_related('restaurant').order_by('-created_at')
    upcoming_camps = DonationCamp.objects.filter(
        ngo__in=volunteer_profile.registered_ngos.all(), 
        is_active=True
    ).select_related('ngo').order_by('start_time')

    donations_map_data = [{"lat": d.restaurant.latitude, "lon": d.restaurant.longitude, "name": d.restaurant.restaurant_name, "food": d.food_description, "id": d.pk} for d in available_donations if d.restaurant.latitude and d.restaurant.longitude]
    camps_map_data = [{"lat": c.latitude, "lon": c.longitude, "name": c.name, "ngo": c.ngo.ngo_name, "address": c.location_address} for c in upcoming_camps if c.latitude and c.longitude]
    
    # Check if user is already subscribed to push notifications
    is_subscribed = bool(volunteer_profile.webpush_subscription)
    
    context = {
        'stats': stats,
        'donations_map_data': json.dumps(donations_map_data),
        'camps_map_data': json.dumps(camps_map_data),
        'is_subscribed_to_notifications': is_subscribed,
        'WEBPUSH_SETTINGS': settings.WEBPUSH_SETTINGS
    }
    return render(request, 'volunteer/dashboard.html', context)

@login_required(login_url='login_page')
@user_type_required('VOLUNTEER')
def volunteer_pickups(request):
    """
    View for "My Pickups" - Manage donations in ACCEPTED and COLLECTED status
    Shows restaurants to pick up from and allows marking items as collected
    """
    volunteer_profile = request.user.volunteer_profile
    
    # Auto-expire pickups not collected within 30 minutes
    thirty_minutes_ago = timezone.now() - timedelta(minutes=30)
    Donation.objects.filter(status='ACCEPTED', accepted_at__lt=thirty_minutes_ago).update(
        status='PENDING', assigned_volunteer=None, accepted_at=None
    )

    # Get active pickups (ACCEPTED or COLLECTED donations)
    active_donations = Donation.objects.filter(
        assigned_volunteer=volunteer_profile, 
        status__in=['ACCEPTED', 'COLLECTED']
    ).select_related('restaurant').order_by('accepted_at')
    
    # Get available donations for new pickups
    available_donations = Donation.objects.filter(
        status='PENDING'
    ).select_related('restaurant').order_by('-created_at')
    
    # Search filtering
    search_query = request.GET.get('q', '').strip()
    if search_query:
        from django.db.models import Q
        available_donations = available_donations.filter(
            Q(restaurant__restaurant_name__icontains=search_query) |
            Q(pickup_address__icontains=search_query)
        )

    # Get stats
    collected_count = Donation.objects.filter(
        assigned_volunteer=volunteer_profile,
        status='COLLECTED'
    ).count()
    
    context = {
        'active_donations': active_donations,
        'available_donations': available_donations,
        'collected_count': collected_count,
    }
    
    return render(request, 'volunteer/pickups.html', context)


@login_required(login_url='login_page')
@user_type_required('VOLUNTEER')
def volunteer_deliveries(request):
    """
    View for "My Deliveries" - Manage delivery of COLLECTED donations
    Shows map to nearest camp and handles delivery completion
    """
    volunteer_profile = request.user.volunteer_profile
    
    # Get collected donations ready for delivery
    collected_donations = Donation.objects.filter(
        assigned_volunteer=volunteer_profile, 
        status='COLLECTED'
    ).select_related('restaurant').order_by('collected_at')
    
    # Get delivery history
    delivery_history = Donation.objects.filter(
        assigned_volunteer=volunteer_profile, 
        status__in=['VERIFICATION_PENDING', 'DELIVERED']
    ).select_related('restaurant', 'target_camp').order_by('-delivered_at')
    
    # Get stats
    active_pickups = Donation.objects.filter(
        assigned_volunteer=volunteer_profile,
        status='ACCEPTED'
    ).count()
    
    pending_verification_count = Donation.objects.filter(
        assigned_volunteer=volunteer_profile,
        status='VERIFICATION_PENDING'
    ).count()
    
    completed_deliveries = Donation.objects.filter(
        assigned_volunteer=volunteer_profile,
        status='DELIVERED'
    ).count()
    
    context = {
        'collected_donations': collected_donations,
        'delivery_history': delivery_history,
        'active_pickups': active_pickups,
        'collected_count': collected_donations.count(),
        'pending_verification_count': pending_verification_count,
        'completed_deliveries': completed_deliveries,
    }

    # If user has collected items, prepare map data
    if collected_donations.exists():
        # Profile location as fallback; GPS will be used in frontend
        if not volunteer_profile.latitude or not volunteer_profile.longitude:
            messages.warning(request, 'Please enable location access or set your location in your profile for accurate routing.')
        
        route_optimizer = get_route_optimizer(use_google_maps=False)
        
        volunteer_location = Location(
            lat=volunteer_profile.latitude or 0,
            lon=volunteer_profile.longitude or 0,
            location_id=0,
            location_type='volunteer',
            name='Your Location'
        )
        
        # Get active camps from registered NGOs
        active_camps = DonationCamp.objects.filter(
            ngo__in=volunteer_profile.registered_ngos.all(), 
            is_active=True
        )
        
        camp_locations = []
        camp_map = {}
        for camp in active_camps:
            if camp.latitude and camp.longitude:
                loc = Location(
                    lat=camp.latitude,
                    lon=camp.longitude,
                    location_id=camp.pk,
                    location_type='camp',
                    name=camp.name
                )
                camp_locations.append(loc)
                camp_map[camp.pk] = camp
        
        # Find nearest camp
        nearest_camp = None
        if camp_locations:
            nearest_loc, nearest_distance, nearest_eta = route_optimizer.find_nearest_location(
                volunteer_location, camp_locations
            )
            if nearest_loc and nearest_loc.id in camp_map:
                nearest_camp = camp_map[nearest_loc.id]
        
        context['nearest_camp'] = nearest_camp
        
        if nearest_camp:
            context['nearest_camp_data'] = {
                'name': nearest_camp.name,
                'latitude': nearest_camp.latitude,
                'longitude': nearest_camp.longitude,
                'pk': nearest_camp.pk,
                'ngo_name': nearest_camp.ngo.ngo_name,
                'address': nearest_camp.location_address
            }
        
        context['volunteer_location_data'] = {
            'lat': volunteer_profile.latitude,
            'lon': volunteer_profile.longitude
        }

    return render(request, 'volunteer/deliveries.html', context)


@login_required(login_url='login_page')
@user_type_required('VOLUNTEER')
def volunteer_manage_pickups(request):
    """
    Deprecated: Redirect to pickups or deliveries view based on status
    Kept for backward compatibility
    """
    view = request.GET.get('view')
    
    if view == 'delivery_route':
        return redirect('volunteer_deliveries')
    else:
        return redirect('volunteer_pickups')


@login_required(login_url='login_page')
@user_type_required('VOLUNTEER')
def volunteer_profile(request):
    from ..models import User
    profile = get_object_or_404(VolunteerProfile, user=request.user)
    username_error = None
    
    if request.method == 'POST':
        form = VolunteerProfileForm(request.POST, request.FILES, instance=profile)
        
        # Handle username update
        new_username = request.POST.get('username', '').strip()
        
        if new_username and new_username != request.user.username:
            # Check if username is already taken
            if User.objects.filter(username=new_username).exclude(pk=request.user.pk).exists():
                username_error = 'This username is already taken.'
            elif len(new_username) > 150:
                username_error = 'Username must be 150 characters or fewer.'
            elif len(new_username) < 3:
                username_error = 'Username must be at least 3 characters.'
            elif not new_username.replace('_', '').replace('-', '').isalnum():
                username_error = 'Username can only contain letters, numbers, underscores, and hyphens.'
            else:
                request.user.username = new_username
                request.user.save()
        
        if form.is_valid() and not username_error:
            form.save()
            messages.success(request, 'Your profile has been updated successfully!')
            return redirect('volunteer_profile')
    else:
        form = VolunteerProfileForm(instance=profile)
        
    context = {'form': form, 'username_error': username_error}
    return render(request, 'volunteer/profile.html', context)

@login_required(login_url='login_page')
@user_type_required('VOLUNTEER')
def volunteer_settings(request):
    return render(request, 'volunteer/settings.html')


# --- ACTION VIEWS ---

@login_required(login_url='login_page')
@user_type_required('VOLUNTEER')
def accept_donation(request, donation_id):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Invalid request'}, status=400)
    
    try:
        with transaction.atomic():
            donation = Donation.objects.select_for_update().get(pk=donation_id)
            
            if donation.status != 'PENDING':
                return JsonResponse({'success': False, 'message': 'This donation is no longer available.'}, status=404)

            volunteer = request.user.volunteer_profile

            if Donation.objects.filter(assigned_volunteer=volunteer, status__in=['ACCEPTED', 'COLLECTED']).count() >= 10:
                return JsonResponse({'success': False, 'message': 'You cannot accept more than 10 donations at a time.'}, status=400)

            donation.assigned_volunteer = volunteer
            donation.status = 'ACCEPTED'
            donation.accepted_at = timezone.now()
            donation.save()
            
            return JsonResponse({'success': True, 'message': 'Donation accepted! Please check your active pickups.'})
            
    except Donation.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'Donation not found.'}, status=404)
    except Exception as e:
        print(f"Error in accept_donation: {e}")
        return JsonResponse({'success': False, 'message': 'An unexpected error occurred.'}, status=500)

@login_required(login_url='login_page')
@user_type_required('VOLUNTEER')
def cancel_pickup(request, donation_id):
    """Cancel a pickup - reset donation status to PENDING"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Invalid request.'}, status=400)
    
    try:
        donation = get_object_or_404(Donation, pk=donation_id)
        
        # Verify this volunteer owns the pickup
        if donation.assigned_volunteer != request.user.volunteer_profile:
            return JsonResponse({'success': False, 'message': 'Unauthorized.'}, status=403)
        
        # Only allow cancellation for ACCEPTED or COLLECTED status
        if donation.status not in ['ACCEPTED', 'COLLECTED']:
            return JsonResponse({'success': False, 'message': 'Cannot cancel donation in current status.'}, status=400)
        
        # Reset donation to PENDING
        donation.status = 'PENDING'
        donation.assigned_volunteer = None
        donation.accepted_at = None
        donation.collected_at = None
        donation.save()
        
        return JsonResponse({'success': True, 'message': 'Pickup cancelled. The donation is now available for other volunteers.'})
    except Exception as e:
        print(f"Error in cancel_pickup: {e}")
        return JsonResponse({'success': False, 'message': 'An error occurred.'}, status=500)


@login_required(login_url='login_page')
@user_type_required('VOLUNTEER')
def mark_as_collected(request, donation_id):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Invalid request.'}, status=400)

    try:
        donation = get_object_or_404(Donation, pk=donation_id)
        if donation.assigned_volunteer != request.user.volunteer_profile:
             return JsonResponse({'success': False, 'message': 'Unauthorized.'}, status=403)

        if donation.status != 'ACCEPTED':
            return JsonResponse({'success': False, 'message': 'Invalid donation status.'}, status=400)

        donation.status = 'COLLECTED'
        donation.collected_at = timezone.now()
        donation.save()

        return JsonResponse({'success': True, 'message': 'Marked as collected!'})
    except Exception as e:
        print(f"Error in mark_as_collected: {e}")
        return JsonResponse({'success': False, 'message': 'An error occurred.'}, status=500)


@login_required(login_url='login_page')
@user_type_required('VOLUNTEER')
def mark_as_delivered(request, camp_id):
    """
    Mark all collected donations as delivered to a camp.
    Sets status to VERIFICATION_PENDING for NGO approval (Trust Protocol).
    """
    if request.method != 'POST': 
        return JsonResponse({'success': False, 'message': 'Invalid request.'}, status=400)
    
    try:
        volunteer_profile = request.user.volunteer_profile
        
        # Guard Logic: Check for uncollected items (accepted but not collected)
        uncollected_count = Donation.objects.filter(
            assigned_volunteer=volunteer_profile,
            status='ACCEPTED'
        ).count()
        
        if uncollected_count > 0:
            return JsonResponse({
                'success': False, 
                'message': f'Cannot deliver yet. You have {uncollected_count} item(s) still marked as "Accepted" but not collected.'
            }, status=400)
        
        # Only deliver COLLECTED donations
        donations = Donation.objects.filter(
            assigned_volunteer=volunteer_profile, 
            status='COLLECTED'
        )
        camp = get_object_or_404(DonationCamp, pk=camp_id)
        
        updated_count = 0
        with transaction.atomic():
            for donation in donations:
                donation.status = 'VERIFICATION_PENDING'  # Trust Protocol: Requires NGO verification
                donation.target_camp = camp
                donation.delivered_at = timezone.now()
                donation.save()
                updated_count += 1
        
        if updated_count > 0:
            return JsonResponse({
                'success': True, 
                'message': f'{updated_count} item(s) marked as delivered and are pending verification by {camp.ngo.ngo_name}.'
            })
        else:
            return JsonResponse({
                'success': False, 
                'message': 'You had no collected pickups to deliver. Collect items first.'
            }, status=400)
    except Exception as e:
        print(f"Error in mark_as_delivered: {e}")
        return JsonResponse({'success': False, 'message': 'An error occurred.'}, status=500)

@login_required(login_url='login_page')
@user_type_required('VOLUNTEER')
def save_webpush_subscription(request):
    """API endpoint to save webpush subscription data"""
    import json
    
    # ADD THIS: Log that the view was called
    print("--- Received request to save webpush subscription ---")

    if request.method != 'POST':
        # ADD THIS: Log invalid method
        print("ERROR: Invalid request method:", request.method)
        return JsonResponse({'success': False, 'message': 'Invalid request'}, status=400)
    
    try:
        data = json.loads(request.body)
        # ADD THIS: Log the data received from the frontend
        print("Subscription data received:", data)
        
        volunteer_profile = request.user.volunteer_profile
        volunteer_profile.webpush_subscription = json.dumps(data)
        volunteer_profile.save()
        
        # ADD THIS: Log success
        print("Successfully saved subscription for:", volunteer_profile.full_name)
        return JsonResponse({'success': True, 'message': 'Subscription saved successfully'})
    except Exception as e:
        # ADD THIS: Log any exceptions that occur
        print(f"ERROR saving subscription: {e}")
        return JsonResponse({'success': False, 'message': str(e)}, status=500)

@login_required(login_url='login_page')
def volunteer_leaderboard(request):
    """Display volunteer leaderboard with rankings based on deliveries and ratings"""
    from django.db.models import Count, Avg, F, Q, Value, FloatField
    from django.db.models.functions import Coalesce
    
    # Calculate volunteer scores: total deliveries + weighted average rating
    volunteers = VolunteerProfile.objects.annotate(
        total_deliveries=Count('assigned_donations', filter=Q(assigned_donations__status='DELIVERED')),
        avg_rating=Coalesce(Avg('assigned_donations__rating', filter=Q(assigned_donations__rating__isnull=False)), Value(0.0), output_field=FloatField()),
        score=F('total_deliveries') + F('avg_rating') * 2  # Weight rating with factor of 2
    ).filter(
        total_deliveries__gt=0  # Only show volunteers with at least 1 delivery
    ).order_by('-score', '-total_deliveries')[:20]  # Top 20
    
    context = {
        'volunteers': volunteers
    }
    return render(request, 'volunteer/leaderboard.html', context)


@login_required(login_url='login_page')
@user_type_required('VOLUNTEER')
def calculate_pickup_route(request):
    """API endpoint to calculate optimized pickup route using TSP"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Invalid request'}, status=400)
    
    try:
        volunteer_profile = request.user.volunteer_profile
        
        # Try to get current GPS location from request body
        try:
            body = json.loads(request.body) if request.body else {}
            current_lat = body.get('current_lat')
            current_lon = body.get('current_lon')
        except json.JSONDecodeError:
            current_lat = None
            current_lon = None
        
        # Use GPS location if available, otherwise fall back to profile location
        if current_lat and current_lon:
            volunteer_lat = float(current_lat)
            volunteer_lon = float(current_lon)
        elif volunteer_profile.latitude and volunteer_profile.longitude:
            volunteer_lat = volunteer_profile.latitude
            volunteer_lon = volunteer_profile.longitude
        else:
            return JsonResponse({
                'success': False, 
                'message': 'Please enable location access or set your location in your profile'
            }, status=400)
        
        # Get volunteer's current location (GPS or profile fallback)
        volunteer_location = Location(
            lat=volunteer_lat,
            lon=volunteer_lon,
            location_id=0,
            location_type='volunteer',
            name='Your Location'
        )
        
        # Get active accepted/collected donations
        active_donations = Donation.objects.filter(
            assigned_volunteer=volunteer_profile,
            status__in=['ACCEPTED', 'COLLECTED']
        ).select_related('restaurant')
        
        if not active_donations.exists():
            return JsonResponse({
                'success': False,
                'message': 'You have no active pickups'
            }, status=400)
        
        # Convert donations to Location objects
        pickup_locations = []
        for donation in active_donations:
            if donation.restaurant.latitude and donation.restaurant.longitude:
                pickup_locations.append(Location(
                    lat=donation.restaurant.latitude,
                    lon=donation.restaurant.longitude,
                    location_id=donation.pk,
                    location_type='donation',
                    name=f"{donation.restaurant.restaurant_name} - {donation.food_description}"
                ))
        
        if not pickup_locations:
            return JsonResponse({
                'success': False,
                'message': 'No valid pickup locations found'
            }, status=400)
        
        # Calculate optimized route using geodesic calculations (free, no API key needed)
        route_optimizer = get_route_optimizer(use_google_maps=False)
        optimized_route, total_distance, estimated_time = route_optimizer.nearest_neighbor_tsp(
            volunteer_location,
            pickup_locations
        )
        
        # Add stop time to ETA (5 min per stop)
        estimated_time = int(estimated_time + len(pickup_locations) * 5)
        
        # Build response
        return JsonResponse({
            'success': True,
            'route': build_route_map_data(optimized_route),
            'total_distance_km': round(total_distance, 2),
            'estimated_time_minutes': estimated_time,
            'total_pickups': len(pickup_locations)
        })
    
    except Exception as e:
        print(f"Error calculating route: {e}")
        return JsonResponse({
            'success': False,
            'message': f'Error calculating route: {str(e)}'
        }, status=500)


@login_required(login_url='login_page')
@user_type_required('VOLUNTEER')
def calculate_delivery_route(request):
    """API endpoint to calculate optimized delivery route to nearest camp"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Invalid request'}, status=400)
    
    try:
        volunteer_profile = request.user.volunteer_profile
        
        # Try to get current GPS location from request body
        try:
            body = json.loads(request.body) if request.body else {}
            current_lat = body.get('current_lat')
            current_lon = body.get('current_lon')
        except json.JSONDecodeError:
            current_lat = None
            current_lon = None
        
        # Use GPS location if available, otherwise fall back to profile location
        if current_lat and current_lon:
            volunteer_lat = float(current_lat)
            volunteer_lon = float(current_lon)
        elif volunteer_profile.latitude and volunteer_profile.longitude:
            volunteer_lat = volunteer_profile.latitude
            volunteer_lon = volunteer_profile.longitude
        else:
            return JsonResponse({
                'success': False,
                'message': 'Please enable location access or set your location in your profile'
            }, status=400)
        
        # Check if volunteer has collected pickups
        collected_donations = Donation.objects.filter(
            assigned_volunteer=volunteer_profile,
            status__in=['ACCEPTED', 'COLLECTED']
        ).count()
        
        if collected_donations == 0:
            return JsonResponse({
                'success': False,
                'message': 'You must collect pickups first'
            }, status=400)
        
        # Get volunteer's current location (GPS or profile fallback)
        volunteer_location = Location(
            lat=volunteer_lat,
            lon=volunteer_lon,
            location_id=0,
            location_type='volunteer',
            name='Your Location'
        )
        
        # Find nearest active donation camp using road distance
        active_camps = DonationCamp.objects.filter(is_active=True).select_related('ngo')
        
        if not active_camps.exists():
            return JsonResponse({
                'success': False,
                'message': 'No active donation camps found'
            }, status=400)
        
        # Convert camps to Location objects
        camp_locations = []
        camp_map = {}
        for camp in active_camps:
            if camp.latitude and camp.longitude:
                loc = Location(
                    lat=camp.latitude,
                    lon=camp.longitude,
                    location_id=camp.pk,
                    location_type='camp',
                    name=camp.name
                )
                camp_locations.append(loc)
                camp_map[camp.pk] = camp
        
        if not camp_locations:
            return JsonResponse({
                'success': False,
                'message': 'No valid donation camps with coordinates found'
            }, status=400)
        
        # Find nearest camp using geodesic distances (free, no API key needed)
        route_optimizer = get_route_optimizer(use_google_maps=False)
        nearest_loc, total_distance, estimated_time = route_optimizer.find_nearest_location(
            volunteer_location, camp_locations
        )
        
        if not nearest_loc or nearest_loc.id not in camp_map:
            return JsonResponse({
                'success': False,
                'message': 'Could not find a valid delivery location'
            }, status=400)
        
        camp = camp_map[nearest_loc.id]
        camp_location = nearest_loc
        
        # Calculate route from volunteer to camp
        route = [volunteer_location, camp_location]
        
        return JsonResponse({
            'success': True,
            'route': build_route_map_data(route),
            'nearest_camp': {
                'id': camp.pk,
                'name': camp.name,
                'ngo_name': camp.ngo.ngo_name,
                'address': camp.location_address
            },
            'total_distance_km': round(total_distance, 2),
            'estimated_time_minutes': estimated_time
        })
    
    except Exception as e:
        print(f"Error calculating delivery route: {e}")
        return JsonResponse({
            'success': False,
            'message': f'Error calculating route: {str(e)}'
        }, status=500)


@login_required(login_url='login_page')
@user_type_required('VOLUNTEER')
def get_volunteer_stats(request):
    """API endpoint to get volunteer's current mode stats"""
    try:
        volunteer_profile = request.user.volunteer_profile
        
        # Get active pickups
        active_pickups = Donation.objects.filter(
            assigned_volunteer=volunteer_profile,
            status__in=['ACCEPTED', 'COLLECTED']
        ).count()
        
        # Get collected items
        collected_items = Donation.objects.filter(
            assigned_volunteer=volunteer_profile,
            status='COLLECTED'
        ).count()
        
        # Get pending verification
        pending_verification = Donation.objects.filter(
            assigned_volunteer=volunteer_profile,
            status='VERIFICATION_PENDING'
        ).count()
        
        # Get completed deliveries
        completed_deliveries = Donation.objects.filter(
            assigned_volunteer=volunteer_profile,
            status='DELIVERED'
        ).count()
        
        return JsonResponse({
            'success': True,
            'active_pickups': active_pickups,
            'collected_items': collected_items,
            'pending_verification': pending_verification,
            'completed_deliveries': completed_deliveries,
            'can_deliver': collected_items > 0 and active_pickups > 0
        })
    
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': str(e)
        }, status=500)


@login_required(login_url='login_page')
@user_type_required('VOLUNTEER')
def get_nearest_camp(request):
    """API endpoint to get the nearest active camp for delivery"""
    try:
        volunteer_profile = request.user.volunteer_profile
        
        # Get registered NGOs
        registered_ngos = volunteer_profile.registered_ngos.all()
        
        if not registered_ngos.exists():
            return JsonResponse({
                'success': False,
                'message': 'You must be registered with at least one NGO to deliver.',
                'camp_id': None
            }, status=400)
        
        # Get active camps from registered NGOs
        active_camps = DonationCamp.objects.filter(
            ngo__in=registered_ngos,
            is_active=True
        ).order_by('-created_at')
        
        if not active_camps.exists():
            return JsonResponse({
                'success': False,
                'message': 'No active camps available right now. Please try again later.',
                'camp_id': None
            }, status=400)
        
        # For now, return the first active camp (nearest will be calculated on map in deliveries view)
        nearest_camp = active_camps.first()
        
        return JsonResponse({
            'success': True,
            'camp_id': nearest_camp.pk,
            'camp_name': nearest_camp.name,
            'ngo_name': nearest_camp.ngo.ngo_name,
            'latitude': nearest_camp.latitude,
            'longitude': nearest_camp.longitude,
            'address': nearest_camp.location_address
        })
    
    except Exception as e:
        print(f"Error in get_nearest_camp: {e}")
        return JsonResponse({
            'success': False,
            'message': 'An error occurred.',
            'camp_id': None
        }, status=500)
