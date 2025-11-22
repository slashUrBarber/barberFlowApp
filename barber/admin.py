from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import Barber, Service, Client, Booking, Income, RegistrationRequest
from django.utils import timezone

@admin.register(Barber)
class BarberAdmin(UserAdmin):
    list_display = ['username', 'email', 'phone', 'work_start_time', 'work_end_time']
    fieldsets = UserAdmin.fieldsets + (
        ('Barber Info', {'fields': ('phone', 'work_start_time', 'work_end_time', 'sms_notifications_enabled')}),
    )

@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    list_display = ['name', 'barber', 'duration_minutes', 'price']
    list_filter = ['barber']

@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    list_display = ['name', 'surname', 'phone', 'age_group', 'gender', 'barber']
    list_filter = ['barber', 'age_group', 'gender']
    search_fields = ['name', 'surname', 'phone']

@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = ['get_client_name', 'barber', 'service', 'appointment_date', 'appointment_time', 'status']
    list_filter = ['barber', 'status', 'appointment_date', 'is_walkin']
    search_fields = ['client__name', 'client__surname', 'client_name']

@admin.register(Income)
class IncomeAdmin(admin.ModelAdmin):
    list_display = ['barber', 'amount', 'service', 'payment_method', 'date', 'is_walkin']
    list_filter = ['barber', 'payment_method', 'date', 'is_walkin']
    date_hierarchy = 'date'


@admin.register(RegistrationRequest)
class RegistrationRequestAdmin(admin.ModelAdmin):
    list_display = ['username', 'email', 'phone', 'created_at', 'approved', 'approved_by']
    list_filter = ['approved', 'created_at']
    readonly_fields = ['username', 'email', 'phone', 'created_at', 'approved', 'approved_at', 'approved_by']
    actions = ['approve_selected_requests']

    def approve_selected_requests(self, request, queryset):
        """Custom admin action to approve selected requests."""
        for reg_request in queryset.filter(approved=False):
            # Create the actual Barber user
            user = Barber.objects.create_user(
                username=reg_request.username,
                email=reg_request.email,
                phone=reg_request.phone,
            )
            # Set the password directly (it's already hashed)
            user.password = reg_request.password
            user.save()
            
            # Create default services
            Service.objects.create(barber=user, name='Haircut', duration_minutes=40, price=100)
            Service.objects.create(barber=user, name='Beard Trim', duration_minutes=15, price=50)
            Service.objects.create(barber=user, name='Trim', duration_minutes=20, price=60)
            
            # Mark the request as approved
            reg_request.approved = True
            reg_request.approved_at = timezone.now()
            reg_request.approved_by = request.user
            reg_request.save()

        self.message_user(request, f"{queryset.count()} registration request(s) approved and user accounts created.")

    approve_selected_requests.short_description = "Approve selected registration requests"