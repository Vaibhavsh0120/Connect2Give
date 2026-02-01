# portal/views/verification_views.py
"""
Verification & Trust Protocol Views
Handles NGO verification of delivered donations
"""

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.db import transaction
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from ..models import Donation, DonationCamp, NGOProfile, VolunteerProfile
from ..decorators import user_type_required


@login_required(login_url='login_page')
@user_type_required('NGO')
def ngo_pending_verifications(request):
    """
    NGO dashboard showing donations pending verification
    """
    ngo_profile = request.user.ngo_profile
    
    # Get all donations targeting this NGO's camps that are pending verification
    pending_donations = Donation.objects.filter(
        target_camp__ngo=ngo_profile,
        status='VERIFICATION_PENDING'
    ).select_related(
        'restaurant',
        'assigned_volunteer',
        'target_camp'
    ).order_by('-delivered_at')
    
    # Get delivered and verified for comparison
    verified_donations = Donation.objects.filter(
        target_camp__ngo=ngo_profile,
        status='DELIVERED'
    ).select_related(
        'restaurant',
        'assigned_volunteer',
        'target_camp'
    ).order_by('-delivered_at')[:20]
    
    context = {
        'pending_donations': pending_donations,
        'verified_donations': verified_donations,
        'pending_count': pending_donations.count(),
        'ngo_profile': ngo_profile
    }
    
    return render(request, 'ngo/pending_verifications.html', context)


@login_required(login_url='login_page')
@user_type_required('NGO')
@require_http_methods(["POST"])
def verify_and_approve_donation(request, donation_id):
    """
    NGO marks a donation as verified and approved
    Updates donation status to DELIVERED and volunteer stats
    """
    try:
        donation = get_object_or_404(Donation, pk=donation_id)
        ngo_profile = request.user.ngo_profile
        
        # Verify the donation has a target camp and belongs to this NGO's camp
        if not donation.target_camp or donation.target_camp.ngo != ngo_profile:
            return JsonResponse({
                'success': False,
                'message': 'Unauthorized - this donation is not assigned to your camp'
            }, status=403)
        
        # Verify donation is in pending verification status
        if donation.status != 'VERIFICATION_PENDING':
            return JsonResponse({
                'success': False,
                'message': f'Donation is in {donation.status} status, cannot verify'
            }, status=400)
        
        with transaction.atomic():
            # Update donation status
            donation.status = 'DELIVERED'
            donation.verified_at = timezone.now()
            donation.verified_by = request.user
            donation.is_verified = True
            donation.save()
            
            # Log verified delivery
            if donation.assigned_volunteer:
                volunteer = donation.assigned_volunteer
                print(f"[v0] Verified delivery from {volunteer.full_name} for {donation.restaurant.restaurant_name}")
            
            return JsonResponse({
                'success': True,
                'message': f'Donation from {donation.restaurant.restaurant_name} verified and approved',
                'donation_id': donation.id
            })
    
    except Exception as e:
        print(f"Error verifying donation: {e}")
        return JsonResponse({
            'success': False,
            'message': f'Error verifying donation: {str(e)}'
        }, status=500)


@login_required(login_url='login_page')
@user_type_required('NGO')
@require_http_methods(["POST"])
def reject_donation_verification(request, donation_id):
    """
    NGO rejects a delivery (quality issues, etc.)
    Resets donation to allow volunteer to try again
    """
    try:
        donation = get_object_or_404(Donation, pk=donation_id)
        ngo_profile = request.user.ngo_profile
        rejection_reason = request.POST.get('reason', 'Quality issues')
        
        # Verify the donation has a target camp and belongs to this NGO's camp
        if not donation.target_camp or donation.target_camp.ngo != ngo_profile:
            return JsonResponse({
                'success': False,
                'message': 'Unauthorized'
            }, status=403)
        
        # Verify donation is pending verification
        if donation.status != 'VERIFICATION_PENDING':
            return JsonResponse({
                'success': False,
                'message': 'Can only reject donations pending verification'
            }, status=400)
        
        with transaction.atomic():
            # Reset donation to COLLECTED status
            donation.status = 'COLLECTED'
            donation.delivered_at = None
            donation.verification_count += 1
            donation.save()
            
            # Log rejected delivery
            if donation.assigned_volunteer:
                volunteer = donation.assigned_volunteer
                print(f"[v0] Donation rejected from {volunteer.full_name}: {rejection_reason}")
            
            return JsonResponse({
                'success': True,
                'message': f'Donation rejected. Volunteer can collect and re-deliver.',
                'donation_id': donation.id
            })
    
    except Exception as e:
        print(f"Error rejecting donation: {e}")
        return JsonResponse({
            'success': False,
            'message': f'Error: {str(e)}'
        }, status=500)


@login_required(login_url='login_page')
@user_type_required('NGO')
def donation_verification_detail(request, donation_id):
    """
    Detailed view for verifying a single donation
    """
    donation = get_object_or_404(Donation, pk=donation_id)
    ngo_profile = request.user.ngo_profile
    
    # Verify access - check if target_camp exists
    if not donation.target_camp or donation.target_camp.ngo != ngo_profile:
        messages.error(request, 'Unauthorized access')
        return redirect('ngo_dashboard_overview')
    
    context = {
        'donation': donation,
        'restaurant': donation.restaurant,
        'volunteer': donation.assigned_volunteer,
        'camp': donation.target_camp
    }
    
    return render(request, 'ngo/verify_donation_detail.html', context)


@login_required(login_url='login_page')
@user_type_required('VOLUNTEER')
def volunteer_delivery_history(request):
    """
    Volunteer's delivery history showing verification status
    """
    volunteer_profile = request.user.volunteer_profile
    
    # Get deliveries grouped by status
    pending_verification = Donation.objects.filter(
        assigned_volunteer=volunteer_profile,
        status='VERIFICATION_PENDING'
    ).select_related('restaurant', 'target_camp').order_by('-delivered_at')
    
    verified_deliveries = Donation.objects.filter(
        assigned_volunteer=volunteer_profile,
        status='DELIVERED'
    ).select_related('restaurant', 'target_camp').order_by('-delivered_at')[:20]
    
    context = {
        'pending_verification': pending_verification,
        'verified_deliveries': verified_deliveries,
        'total_verified': Donation.objects.filter(
            assigned_volunteer=volunteer_profile,
            status='DELIVERED'
        ).count()
    }
    
    return render(request, 'volunteer/delivery_history.html', context)


@login_required(login_url='login_page')
@user_type_required('VOLUNTEER')
@require_http_methods(["POST"])
def submit_delivery_confirmation(request):
    """
    Volunteer confirms items are delivered at camp
    Triggers verification workflow
    """
    try:
        camp_id = request.POST.get('camp_id')
        
        if not camp_id:
            return JsonResponse({
                'success': False,
                'message': 'Camp ID is required'
            }, status=400)
        
        camp = get_object_or_404(DonationCamp, pk=camp_id)
        volunteer_profile = request.user.volunteer_profile
        
        with transaction.atomic():
            # Get all accepted/collected donations for this volunteer
            donations = Donation.objects.filter(
                assigned_volunteer=volunteer_profile,
                status__in=['ACCEPTED', 'COLLECTED']
            ).select_for_update()
            
            if not donations.exists():
                return JsonResponse({
                    'success': False,
                    'message': 'You have no active pickups to deliver'
                }, status=400)
            
            # Update all to VERIFICATION_PENDING
            updated_count = 0
            for donation in donations:
                donation.status = 'VERIFICATION_PENDING'
                donation.target_camp = camp
                donation.delivered_at = timezone.now()
                donation.save()
                updated_count += 1
            
            return JsonResponse({
                'success': True,
                'message': f'Delivery confirmed! {updated_count} items submitted for verification by {camp.ngo.ngo_name}',
                'items_count': updated_count,
                'camp_name': camp.name
            })
    
    except Exception as e:
        print(f"Error submitting delivery: {e}")
        return JsonResponse({
            'success': False,
            'message': f'Error: {str(e)}'
        }, status=500)
