# portal/views/trust_score_views.py
"""
Trust Score & Verification Protocol Dashboard Views
"""

from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods

from ..models import VolunteerProfile, VolunteerTrustScore, Donation
from ..decorators import user_type_required


@login_required(login_url='login_page')
@user_type_required('VOLUNTEER')
def volunteer_trust_dashboard(request):
    """
    Volunteer's personal trust score and verification dashboard
    """
    volunteer_profile = request.user.volunteer_profile
    
    # Get or create trust score
    trust_score, created = VolunteerTrustScore.objects.get_or_create(volunteer=volunteer_profile)
    
    # Get recent deliveries
    recent_deliveries = Donation.objects.filter(
        assigned_volunteer=volunteer_profile
    ).order_by('-delivered_at')[:10]
    
    # Get verification statistics
    verified_count = Donation.objects.filter(
        assigned_volunteer=volunteer_profile,
        status='DELIVERED'
    ).count()
    
    pending_verification = Donation.objects.filter(
        assigned_volunteer=volunteer_profile,
        status='VERIFICATION_PENDING'
    ).count()
    
    rejected_count = Donation.objects.filter(
        assigned_volunteer=volunteer_profile,
        status='COLLECTED',
        verification_count__gt=0
    ).count()
    
    context = {
        'volunteer': volunteer_profile,
        'trust_score': trust_score,
        'recent_deliveries': recent_deliveries,
        'verified_count': verified_count,
        'pending_verification': pending_verification,
        'rejected_count': rejected_count,
        'trust_percentage': int(trust_score.trust_score),
        'badges': trust_score.badges
    }
    
    return render(request, 'volunteer/trust_dashboard.html', context)


@login_required(login_url='login_page')
@user_type_required('VOLUNTEER')
def volunteer_verification_stats(request):
    """
    API endpoint for volunteer's verification statistics
    """
    try:
        volunteer_profile = request.user.volunteer_profile
        trust_score, created = VolunteerTrustScore.objects.get_or_create(volunteer=volunteer_profile)
        
        # Calculate percentages
        verification_rate = (trust_score.verified_deliveries / trust_score.total_deliveries * 100) if trust_score.total_deliveries > 0 else 0
        
        return JsonResponse({
            'success': True,
            'trust_score': {
                'score': round(trust_score.trust_score, 1),
                'total_deliveries': trust_score.total_deliveries,
                'verified_deliveries': trust_score.verified_deliveries,
                'rejected_deliveries': trust_score.rejected_deliveries,
                'verification_rate': round(verification_rate, 1),
                'average_rating': round(trust_score.average_rating, 2),
                'badges': trust_score.badges
            }
        })
    
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': str(e)
        }, status=500)


@login_required(login_url='login_page')
@user_type_required('NGO')
def ngo_volunteer_trust_profiles(request):
    """
    NGO's view of their volunteers' trust scores and ratings
    """
    ngo_profile = request.user.ngo_profile
    
    # Get all volunteers registered with this NGO
    volunteers = ngo_profile.volunteers.all().select_related('user')
    
    # Get their trust scores
    volunteer_stats = []
    for volunteer in volunteers:
        trust_score = VolunteerTrustScore.objects.filter(volunteer=volunteer).first()
        
        if trust_score:
            volunteer_stats.append({
                'volunteer': volunteer,
                'trust_score': trust_score.trust_score,
                'total_deliveries': trust_score.total_deliveries,
                'verified_deliveries': trust_score.verified_deliveries,
                'average_rating': trust_score.average_rating,
                'badges': trust_score.badges
            })
    
    # Sort by trust score descending
    volunteer_stats.sort(key=lambda x: x['trust_score'], reverse=True)
    
    context = {
        'ngo_profile': ngo_profile,
        'volunteer_stats': volunteer_stats
    }
    
    return render(request, 'ngo/volunteer_trust_profiles.html', context)


@login_required(login_url='login_page')
@user_type_required('NGO')
def donation_verification_analytics(request):
    """
    NGO analytics on donation verification rates and volunteer performance
    """
    ngo_profile = request.user.ngo_profile
    
    # Get all donations delivered to this NGO's camps
    all_donations = Donation.objects.filter(
        target_camp__ngo=ngo_profile
    )
    
    verified_donations = all_donations.filter(is_verified=True).count()
    pending_donations = all_donations.filter(status='VERIFICATION_PENDING').count()
    rejected_donations = all_donations.filter(verification_count__gt=0, is_verified=False).count()
    
    total_donations = all_donations.count()
    
    # Calculate metrics
    verification_rate = (verified_donations / total_donations * 100) if total_donations > 0 else 0
    average_rating = sum([d.rating for d in all_donations if d.rating]) / all_donations.filter(rating__isnull=False).count() if all_donations.filter(rating__isnull=False).count() > 0 else 0
    
    # Get top rated volunteers
    top_volunteers = VolunteerTrustScore.objects.filter(
        volunteer__registered_ngos=ngo_profile
    ).order_by('-average_rating')[:5]
    
    context = {
        'ngo_profile': ngo_profile,
        'verified_donations': verified_donations,
        'pending_donations': pending_donations,
        'rejected_donations': rejected_donations,
        'total_donations': total_donations,
        'verification_rate': round(verification_rate, 1),
        'average_rating': round(average_rating, 2),
        'top_volunteers': top_volunteers
    }
    
    return render(request, 'ngo/verification_analytics.html', context)
