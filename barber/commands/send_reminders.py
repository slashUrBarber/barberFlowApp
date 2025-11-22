from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import datetime, timedelta
from barber.models import Booking
from barber.sms import send_booking_reminder

class Command(BaseCommand):
    help = 'Send SMS reminders for appointments starting in exactly 10 minutes'
    
    def handle(self, *args, **kwargs):
        now = timezone.now()
        
        # Calculate exact time 10 minutes from now
        reminder_time = now + timedelta(minutes=10)
        
        # Get all bookings for today that haven't been reminded yet
        bookings = Booking.objects.filter(
            appointment_date=now.date(),
            status__in=['pending', 'confirmed'],
            sms_reminder_sent=False
        )
        
        count = 0
        for booking in bookings:
            # Combine appointment date and time to get full datetime
            appointment_datetime = datetime.combine(
                booking.appointment_date, 
                booking.appointment_time
            )
            appointment_datetime = timezone.make_aware(appointment_datetime)
            
            # Calculate time difference in minutes
            time_diff = (appointment_datetime - now).total_seconds() / 60
            
            # Send reminder if appointment is between 9-11 minutes away
            # (gives 2-minute window for cron job execution)
            if 9 <= time_diff <= 11:
                if booking.barber.sms_notifications_enabled:
                    if send_booking_reminder(booking):
                        count += 1
                        self.stdout.write(
                            self.style.SUCCESS(
                                f'Sent reminder for {booking.get_client_name()} - '
                                f'Appointment at {booking.appointment_time}'
                            )
                        )
        
        self.stdout.write(
            self.style.SUCCESS(f'Total reminders sent: {count}')
        )