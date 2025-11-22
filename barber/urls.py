from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

urlpatterns = [
    # Authentication
    path('register/', views.register, name='register'),
    path('login/', auth_views.LoginView.as_view(template_name='barber/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    
    # Home and Dashboard
    path('', views.home, name='home'),
    path('dashboard/', views.dashboard, name='dashboard'),
    
    # Queue management
    path('queue/start/<int:booking_id>/', views.start_service_from_queue, name='start_service_from_queue'),
    path('queue/remove/<int:booking_id>/', views.remove_from_queue, name='remove_from_queue'),
    
    # Quick start workflow
    path('client/new/', views.client_create, name='client_create'),
    path('client/existing/', views.select_existing_client, name='select_existing_client'),
    
    # Services
    path('services/', views.services_list, name='services_list'),
    path('services/create/', views.service_create, name='service_create'),
    path('services/<int:pk>/edit/', views.service_edit, name='service_edit'),
    path('services/<int:pk>/delete/', views.service_delete, name='service_delete'),
    
    # Clients
    path('clients/', views.clients_list, name='clients_list'),
    path('clients/<int:pk>/', views.client_detail, name='client_detail'),
    path('clients/<int:pk>/delete/', views.client_delete, name='client_delete'),
    
    # Bookings
    path('bookings/', views.bookings_list, name='bookings_list'),
    path('bookings/create/', views.booking_create, name='booking_create'),
    path('bookings/<int:pk>/start/', views.booking_start, name='booking_start'),
    path('bookings/<int:pk>/complete/', views.booking_complete, name='booking_complete'),
    
    # Income
    path('income/', views.income_list, name='income_list'),
    path('income/create/', views.income_create, name='income_create'),
    path('income/credit/', views.credit_list, name='credit_list'),
    path('income/credit/<int:income_id>/paid/', views.mark_credit_paid, name='mark_credit_paid'),
    
    # Settings
    path('settings/', views.settings_view, name='settings'),
    
    # Public booking
    path('book/<str:username>/', views.public_booking, name='public_booking'),
    path('booking/success/', views.booking_success, name='booking_success'),
    path('cancel/<str:token>/', views.booking_cancel, name='booking_cancel'),
    path('booking/cancelled/', views.booking_cancelled, name='booking_cancelled'),
    path('book/<str:username>/get_slots/', views.get_available_slots_ajax, name='get_available_slots_ajax'),
    path('booking/success/', views.booking_success, name='booking_success'),
]