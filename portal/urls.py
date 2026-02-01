# portal/urls.py
from django.urls import path
from django.contrib.auth import views as auth_views
from . import views
from .views import verification_views, tracking_views, trust_score_views

urlpatterns = [
    # --- Service Worker URL ---
    path('sw.js', views.serve_sw, name='sw'),

    # --- Main Site & Auth URLs ---
    path('', views.index, name='index'),
    path('register/step-1/', views.register_step_1, name='register_step_1'),
    path('register/step-2/', views.register_step_2, name='register_step_2'),
    path('login/', views.login_page, name='login_page'),
    path('logout/', views.logout_view, name='logout'),
    path('force-password-change/', views.force_password_change, name='force_password_change'),
    path('api/check-username/', views.check_username_availability, name='check_username'),
    
    # --- Password Reset URLs ---
    path('password-reset/', 
         auth_views.PasswordResetView.as_view(
             template_name='auth/password_reset.html',
             email_template_name='auth/password_reset_email.html',
             subject_template_name='auth/password_reset_subject.txt',
         ), 
         name='password_reset'),
    path('password-reset/done/', 
         auth_views.PasswordResetDoneView.as_view(
             template_name='auth/password_reset_done.html'
         ), 
         name='password_reset_done'),
    path('password-reset-confirm/<uidb64>/<token>/', 
         auth_views.PasswordResetConfirmView.as_view(
             template_name='auth/password_reset_confirm.html'
         ), 
         name='password_reset_confirm'),
    path('password-reset-complete/', 
         auth_views.PasswordResetCompleteView.as_view(
             template_name='auth/password_reset_complete.html'
         ), 
         name='password_reset_complete'),
    
    # --- Google OAuth Callback ---
    path('accounts/google/login/callback/', views.google_callback, name='google_callback'),
    
    # --- Account Security URLs ---
    path('account/link-google/', views.link_google_account, name='link_google_account'),
    path('account/unlink-google/', views.unlink_google_account, name='unlink_google_account'),
    path('account/set-password/', views.set_password_after_google, name='set_password_after_google'),
    
    # --- Restaurant Dashboard URLs ---
    path('dashboard/restaurant/', views.restaurant_dashboard, name='restaurant_dashboard'),
    path('dashboard/restaurant/donations/', views.restaurant_donations, name='restaurant_donations'),
    path('dashboard/restaurant/profile/', views.restaurant_profile, name='restaurant_profile'),
    path('dashboard/restaurant/settings/', views.restaurant_settings, name='restaurant_settings'),

    # --- NGO Dashboard URLs ---
    path('dashboard/ngo/', views.ngo_dashboard_overview, name='ngo_dashboard_overview'),
    path('dashboard/ngo/camps/', views.ngo_manage_camps, name='ngo_manage_camps'),
    path('dashboard/ngo/volunteers/', views.ngo_manage_volunteers, name='ngo_manage_volunteers'),
    path('dashboard/ngo/register-volunteer/', views.ngo_register_volunteer, name='ngo_register_volunteer'),
    path('dashboard/ngo/reset-volunteer-password/<int:volunteer_id>/', views.ngo_reset_volunteer_password, name='ngo_reset_volunteer_password'),
    path('dashboard/ngo/profile/', views.ngo_profile, name='ngo_profile'),
    path('dashboard/ngo/settings/', views.ngo_settings, name='ngo_settings'),

    # --- Volunteer Dashboard URLs ---
    path('dashboard/volunteer/', views.volunteer_dashboard, name='volunteer_dashboard'),
    path('dashboard/volunteer/pickups/', views.volunteer_pickups, name='volunteer_pickups'),
    path('dashboard/volunteer/deliveries/', views.volunteer_deliveries, name='volunteer_deliveries'),
    path('dashboard/volunteer/manage-pickups/', views.volunteer_manage_pickups, name='volunteer_manage_pickups'),  # Legacy redirect
    path('dashboard/volunteer/profile/', views.volunteer_profile, name='volunteer_profile'),
    path('dashboard/volunteer/settings/', views.volunteer_settings, name='volunteer_settings'),
    # NOTE: volunteer_manage_camps removed - volunteers cannot self-register with NGOs
    
    # --- Route Optimization APIs ---
    path('api/calculate-pickup-route/', views.calculate_pickup_route, name='calculate_pickup_route'),
    path('api/calculate-delivery-route/', views.calculate_delivery_route, name='calculate_delivery_route'),
    path('api/volunteer-stats/', views.get_volunteer_stats, name='volunteer_stats'),
    path('api/nearest-camp/', views.get_nearest_camp, name='get_nearest_camp'),
    
    # --- Action URLs ---
    # NOTE: register_with_ngo and unregister_from_ngo removed - volunteers are only linked to their creating NGO
    path('donation/accept/<int:donation_id>/', views.accept_donation, name='accept_donation'),
    path('donation/collected/<int:donation_id>/', views.mark_as_collected, name='mark_as_collected'),
    path('donation/cancel-pickup/<int:donation_id>/', views.cancel_pickup, name='cancel_pickup'),
    path('donation/deliver/to/<int:camp_id>/', views.mark_as_delivered, name='mark_as_delivered'),
    path('camp/complete/<int:camp_id>/', views.mark_camp_as_completed, name='mark_camp_as_completed'),
    path('donation/confirm_delivery/<int:donation_id>/', views.confirm_delivery, name='confirm_delivery'),

    # --- API URLs ---
    path('api/register/', views.RegisterAPIView.as_view(), name='api_register'),
    path('api/login/', views.LoginAPIView.as_view(), name='api_login'),
    path('api/save-webpush-subscription/', views.save_webpush_subscription, name='save_webpush_subscription'),
    
    # --- Gamification URLs ---
    path('donation/rate/<int:donation_id>/', views.rate_donation, name='rate_donation'),
    path('leaderboard/', views.volunteer_leaderboard, name='volunteer_leaderboard'),
    
    # --- Verification & Trust Protocol URLs ---
    path('dashboard/ngo/verifications/', verification_views.ngo_pending_verifications, name='ngo_pending_verifications'),
    path('donation/verify/<int:donation_id>/', verification_views.verify_and_approve_donation, name='verify_donation'),
    path('donation/reject/<int:donation_id>/', verification_views.reject_donation_verification, name='reject_donation'),
    path('donation/verify-detail/<int:donation_id>/', verification_views.donation_verification_detail, name='verify_donation_detail'),
    path('volunteer/delivery-history/', verification_views.volunteer_delivery_history, name='volunteer_delivery_history'),
    path('donation/submit-delivery/', verification_views.submit_delivery_confirmation, name='submit_delivery_confirmation'),
    
    # --- Real-Time Geolocation Tracking URLs ---
    path('api/update-volunteer-location/', tracking_views.update_volunteer_location, name='update_volunteer_location'),
    path('dashboard/volunteer/active-tracking/', tracking_views.volunteer_active_tracking, name='volunteer_active_tracking'),
    path('dashboard/ngo/volunteer-locations/', tracking_views.ngo_volunteer_locations, name='ngo_volunteer_locations'),
    path('api/get-volunteers-locations/', tracking_views.get_volunteers_locations_api, name='get_volunteers_locations_api'),
    path('volunteer/location-privacy/', tracking_views.volunteer_location_privacy_settings, name='volunteer_location_privacy'),
    
    # --- Trust Score & Verification Protocol URLs ---
    path('dashboard/volunteer/trust-score/', trust_score_views.volunteer_trust_dashboard, name='volunteer_trust_dashboard'),
    path('api/volunteer-verification-stats/', trust_score_views.volunteer_verification_stats, name='volunteer_verification_stats'),
    path('dashboard/ngo/volunteer-trust-profiles/', trust_score_views.ngo_volunteer_trust_profiles, name='ngo_volunteer_trust_profiles'),
    path('dashboard/ngo/verification-analytics/', trust_score_views.donation_verification_analytics, name='donation_verification_analytics'),
]
