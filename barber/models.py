# barber/models.py

from django.db import models
from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError
from django.utils import timezone
from datetime import timedelta
import uuid

# --- Define the Barber model FIRST ---
class Barber(AbstractUser):
    """Custom user model for barbers"""
    phone = models.CharField(max_length=15, blank=True)
    work_start_time = models.TimeField(default='08:00')
    work_end_time = models.TimeField(default='18:00')
    sms_notifications_enabled = models.BooleanField(default=True)

    def get_booking_url(self):
        return f"/book/{self.username}"

    class Meta:
        verbose_name = 'Barber'
        verbose_name_plural = 'Barbers'

# --- Define other models that reference Barber ---
class Service(models.Model):
    """Services offered by barbers"""
    barber = models.ForeignKey(Barber, on_delete=models.CASCADE, related_name='services')
    name = models.CharField(max_length=100)
    duration_minutes = models.IntegerField(help_text="Duration in minutes")
    price = models.DecimalField(max_digits=10, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']
        unique_together = ['barber', 'name']

    def __str__(self):
        return f"{self.name} ({self.duration_minutes}min - R{self.price})"

class Client(models.Model):
    """Client information"""
    AGE_GROUPS = [
        ('child', 'Child'),
        ('teen', 'Teen'),
        ('adult', 'Adult'),
        ('senior', 'Senior'),
    ]
    GENDER_CHOICES = [
        ('male', 'Male'),
        ('female', 'Female'),
        ('other', 'Other'),
    ]
    barber = models.ForeignKey(Barber, on_delete=models.CASCADE, related_name='clients')
    name = models.CharField(max_length=100)
    surname = models.CharField(max_length=100)
    phone = models.CharField(max_length=15)
    age_group = models.CharField(max_length=10, choices=AGE_GROUPS)
    gender = models.CharField(max_length=10, choices=GENDER_CHOICES)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['surname', 'name']
        unique_together = ['barber', 'phone']

    def __str__(self):
        return f"{self.name} {self.surname} - {self.phone}"

    def clean(self):
        # Ensure phone is unique per barber (only if barber is set)
        if self.barber_id:
            if Client.objects.filter(barber=self.barber, phone=self.phone).exclude(pk=self.pk).exists():
                raise ValidationError({'phone': 'A client with this phone number already exists.'})

class Booking(models.Model):
    """Appointment bookings"""
    STATUS_CHOICES = [
        ('waiting', 'Waiting'),
        ('pending', 'Pending'),
        ('confirmed', 'Confirmed'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
        ('removed', 'Removed'),
    ]
    barber = models.ForeignKey(Barber, on_delete=models.CASCADE, related_name='bookings')
    client = models.ForeignKey(Client, on_delete=models.SET_NULL, null=True, blank=True, related_name='bookings')
    service = models.ForeignKey(Service, on_delete=models.SET_NULL, null=True, blank=True, related_name='bookings')
    # For walk-ins or quick bookings
    client_name = models.CharField(max_length=200, blank=True)
    client_phone = models.CharField(max_length=15, blank=True)
    appointment_date = models.DateField(null=True, blank=True)
    appointment_time = models.TimeField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='waiting')
    is_walkin = models.BooleanField(default=False)
    # Queue management
    queue_position = models.IntegerField(default=0)
    added_to_queue_at = models.DateTimeField(auto_now_add=True)
    timer_started_at = models.DateTimeField(null=True, blank=True)
    timer_ended_at = models.DateTimeField(null=True, blank=True)
    sms_confirmation_sent = models.BooleanField(default=False)
    sms_reminder_sent = models.BooleanField(default=False)
    cancellation_token = models.CharField(max_length=100, blank=True, null=True, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['queue_position', 'added_to_queue_at']

    def __str__(self):
        client_info = self.client if self.client else self.client_name
        return f"{client_info} - {self.get_status_display()}"

    def get_client_name(self):
        return f"{self.client.name} {self.client.surname}" if self.client else self.client_name

    def get_client_phone(self):
        return self.client.phone if self.client else self.client_phone

    def save(self, *args, **kwargs):
        # Auto-assign queue position if waiting
        if self.status == 'waiting' and not self.queue_position:
            max_position = Booking.objects.filter(
                barber=self.barber,
                status='waiting'
            ).aggregate(models.Max('queue_position'))['queue_position__max'] or 0
            self.queue_position = max_position + 1
        super().save(*args, **kwargs)

class Income(models.Model):
    """Income tracking"""
    PAYMENT_METHODS = [
        ('cash', 'Cash'),
        ('card', 'Card'),
        ('eft', 'EFT'),
        ('credit', 'Credit'),
        ('other', 'Other'),
    ]
    barber = models.ForeignKey(Barber, on_delete=models.CASCADE, related_name='income_records')
    client = models.ForeignKey(Client, on_delete=models.SET_NULL, null=True, blank=True)
    service = models.ForeignKey(Service, on_delete=models.SET_NULL, null=True, blank=True)
    booking = models.OneToOneField(Booking, on_delete=models.SET_NULL, null=True, blank=True, related_name='income_record')
    # For walk-ins
    client_name = models.CharField(max_length=200, blank=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    payment_method = models.CharField(max_length=10, choices=PAYMENT_METHODS)
    is_walkin = models.BooleanField(default=False)
    # Credit tracking
    credit_paid = models.BooleanField(default=False)
    credit_paid_date = models.DateField(null=True, blank=True)
    date = models.DateField(default=timezone.now)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date', '-created_at']

    def __str__(self):
        client_info = self.client if self.client else self.client_name
        return f"R{self.amount} - {client_info} - {self.date}"

# --- Define RegistrationRequest AFTER all other models ---
class RegistrationRequest(models.Model):
    """Model to store registration requests pending admin approval"""
    username = models.CharField(max_length=150, unique=True)
    email = models.EmailField(unique=True)
    phone = models.CharField(max_length=15, blank=True)
    password = models.CharField(max_length=128) # Store hashed password
    created_at = models.DateTimeField(auto_now_add=True)
    approved = models.BooleanField(default=False)
    approved_at = models.DateTimeField(null=True, blank=True)
    # Use string reference to avoid the 'User' name error during initial load
    # This refers back to the Barber model as the custom user model
    approved_by = models.ForeignKey('Barber', on_delete=models.SET_NULL, null=True, blank=True, related_name='approved_requests')

    def __str__(self):
        status = "Approved" if self.approved else "Pending"
        return f"{self.username} - {status}"

    class Meta:
        verbose_name = 'Registration Request'
        verbose_name_plural = 'Registration Requests'
        ordering = ['-created_at']

# --- DO NOT define User = get_user_model() here if Barber is the user model ---
# The User alias is typically used in views.py or forms.py, not models.py
# when the model itself is the custom user model.