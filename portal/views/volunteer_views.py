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
from ..utils import RouteOptimizer, Location, build_route_map_data


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
def volunteer_manage_pickups(request):
    volunteer_profile = request.user.volunteer_profile
    view = request.GET.get('view')
    
    thirty_minutes_ago = timezone.now() - timedelta(minutes=30)
    Donation.objects.filter(status='ACCEPTED', accepted_at__lt=thirty_minutes_ago).update(status='PENDING', assigned_volunteer=None, accepted_at=None)

    # Optimized queries with select_related for foreign keys
    active_donations = Donation.objects.filter(
        assigned_volunteer=volunteer_profile, 
        status__in=['ACCEPTED', 'COLLECTED']
    ).select_related('restaurant').order_by('accepted_at')
    
    delivery_history = Donation.objects.filter(
        assigned_volunteer=volunteer_profile, 
        status__in=['VERIFYING', 'DELIVERED']
    ).select_related('restaurant', 'target_camp').order_by('-delivered_at')
    
    available_donations = Donation.objects.filter(
        status='PENDING'
    ).select_related('restaurant').order_by('-created_at')
    
    # Get search query
    search_query = request.GET.get('q', '').strip()
    
    # Apply search filter
    if search_query:
        from django.db.models import Q
        available_donations = available_donations.filter(
            Q(restaurant__restaurant_name__icontains=search_query) |
            Q(pickup_address__icontains=search_query)
        )

    context = {
        'active_donations': active_donations,
        'available_donations': available_donations,
        'delivery_history': delivery_history,
        'view': view
    }

    if view == 'delivery_route':
        if not volunteer_profile.latitude or not volunteer_profile.longitude:
            messages.error(request, 'Please set your location in your profile before calculating routes.')
            return redirect('volunteer_profile')
        
        volunteer_location = (volunteer_profile.latitude, volunteer_profile.longitude)
        active_camps = DonationCamp.objects.filter(ngo__in=volunteer_profile.registered_ngos.all(), is_active=True)
        
        nearest_camp = None
        min_dist = float('inf')

        for camp in active_camps:
            if camp.latitude and camp.longitude:
                dist = geodesic(volunteer_location, (camp.latitude, camp.longitude)).km
                if dist < min_dist:
                    min_dist = dist
                    nearest_camp = camp
        
        context['nearest_camp'] = nearest_camp
        
        if nearest_camp:
            context['nearest_camp_data'] = {
                'name': nearest_camp.name,
                'latitude': nearest_camp.latitude,
                'longitude': nearest_camp.longitude,
                'pk': nearest_camp.pk
            }
        context['volunteer_location_data'] = {
            'lat': volunteer_profile.latitude,
            'lon': volunteer_profile.longitude
        }

    return render(request, 'volunteer/manage_pickups.html', context)


@login_required(login_url='login_page')
@user_type_required('VOLUNTEER')
def volunteer_manage_camps(request):
    volunteer_profile = request.user.volunteer_profile
    registered_ngos = volunteer_profile.registered_ngos.all()
    
    # Get search query
    search_query = request.GET.get('q', '').strip()
    available_ngos = NGOProfile.objects.exclude(pk__in=[n.pk for n in registered_ngos])
    
    # Apply search filter
    if search_query:
        from django.db.models import Q
        available_ngos = available_ngos.filter(
            Q(ngo_name__icontains=search_query) | 
            Q(address__icontains=search_query)
        )
    
    context = {
        'registered_ngos': registered_ngos,
        'available_ngos': available_ngos,
    }
    return render(request, 'volunteer/manage_camps.html', context)

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
def register_with_ngo(request, ngo_id):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Invalid request.'}, status=400)
    
    try:
        ngo = get_object_or_404(NGOProfile, pk=ngo_id)
        volunteer = request.user.volunteer_profile
        ngo.volunteers.add(volunteer)
        return JsonResponse({'success': True, 'message': f'Successfully registered with {ngo.ngo_name}.'})
    except Exception as e:
        return JsonResponse({'success': False, 'message': 'An unexpected error occurred.'}, status=500)


@login_required(login_url='login_page')
@user_type_required('VOLUNTEER')
def unregister_from_ngo(request, ngo_id):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Invalid request.'}, status=400)
        
    try:
        ngo = get_object_or_404(NGOProfile, pk=ngo_id)
        volunteer = request.user.volunteer_profile
        ngo.volunteers.remove(volunteer)
        return JsonResponse({'success': True, 'message': f'Successfully unregistered from {ngo.ngo_name}.'})
    except Exception as e:
        return JsonResponse({'success': False, 'message': 'An unexpected error occurred.'}, status=500)


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
    if request.method != 'POST': 
        return redirect('index')
    donations = Donation.objects.filter(assigned_volunteer=request.user.volunteer_profile, status__in=['ACCEPTED', 'COLLECTED'])
    camp = get_object_or_404(DonationCamp, pk=camp_id)
    
    updated_count = 0
    for donation in donations:
        donation.status = 'VERIFYING'
        donation.target_camp = camp
        donation.delivered_at = timezone.now()
        donation.save()
        updated_count += 1
        
    if updated_count > 0:
        messages.success(request, f'{updated_count} item(s) marked as delivered and are pending verification by the NGO.')
    else:
        messages.warning(request, 'You had no active pickups to deliver.')

    return redirect('volunteer_manage_pickups')

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
        
        if not volunteer_profile.latitude or not volunteer_profile.longitude:
            return JsonResponse({
                'success': False, 
                'message': 'Please set your location in your profile first'
            }, status=400)
        
        # Get volunteer's current location
        volunteer_location = Location(
            lat=volunteer_profile.latitude,
            lon=volunteer_profile.longitude,
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
        
        # Calculate optimized route
        optimized_route, total_distance = RouteOptimizer.nearest_neighbor_tsp(
            volunteer_location,
            pickup_locations
        )
        
        # Estimate time
        estimated_time = RouteOptimizer.estimate_time_minutes(
            total_distance,
            stops_count=len(pickup_locations)
        )
        
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
        
        if not volunteer_profile.latitude or not volunteer_profile.longitude:
            return JsonResponse({
                'success': False,
                'message': 'Please set your location in your profile first'
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
        
        # Get volunteer's location
        volunteer_location = Location(
            lat=volunteer_profile.latitude,
            lon=volunteer_profile.longitude,
            location_id=0,
            location_type='volunteer',
            name='Your Location'
        )
        
        # Find nearest active donation camp
        active_camps = DonationCamp.objects.filter(is_active=True).select_related('ngo')
        
        if not active_camps.exists():
            return JsonResponse({
                'success': False,
                'message': 'No active donation camps found'
            }, status=400)
        
        # Find nearest camp
        nearest_camp = None
        min_distance = float('inf')
        
        for camp in active_camps:
            if camp.latitude and camp.longitude:
                camp_location = Location(
                    lat=camp.latitude,
                    lon=camp.longitude,
                    location_id=camp.pk,
                    location_type='camp'
                )
                distance = volunteer_location.distance_to(camp_location)
                if distance < min_distance:
                    min_distance = distance
                    nearest_camp = (camp, camp_location)
        
        if not nearest_camp:
            return JsonResponse({
                'success': False,
                'message': 'Could not find a valid delivery location'
            }, status=400)
        
        camp, camp_location = nearest_camp
        
        # Calculate route from volunteer to camp
        route = [volunteer_location, camp_location]
        total_distance = min_distance
        
        estimated_time = RouteOptimizer.estimate_time_minutes(
            total_distance,
            stops_count=1
        )
        
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
