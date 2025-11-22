from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login, authenticate
from django.contrib import messages
from django.db.models import Sum, Count, Q
from django.utils import timezone
from django.http import JsonResponse
from datetime import datetime, timedelta, date
import uuid
from .models import Barber, Service, Client, Booking, Income, RegistrationRequest
from .forms import (
    BarberRegistrationForm, ServiceForm, ClientForm, 
    BookingForm, IncomeForm, SettingsForm, PublicBookingForm
)
from .sms import send_sms, send_booking_confirmation, send_booking_reminder
from django.db import models



@login_required
def dashboard(request):
    """Main dashboard view with stats"""
    barber = request.user
    today = timezone.now().date()
    week_start = today - timedelta(days=today.weekday())
    month_start = today.replace(day=1)

    # Income totals for current periods
    daily_income = Income.objects.filter(barber=barber, date=today).aggregate(total=Sum('amount'))['total'] or 0
    weekly_income = Income.objects.filter(barber=barber, date__gte=week_start).aggregate(total=Sum('amount'))['total'] or 0
    monthly_income = Income.objects.filter(barber=barber, date__gte=month_start).aggregate(total=Sum('amount'))['total'] or 0

    # Service counters for current periods
    daily_services = Income.objects.filter(barber=barber, date=today).values('service__name').annotate(count=Count('id'))
    weekly_services = Income.objects.filter(barber=barber, date__gte=week_start).values('service__name').annotate(count=Count('id'))
    monthly_services = Income.objects.filter(barber=barber, date__gte=month_start).values('service__name').annotate(count=Count('id'))

    # Calculate income for the previous 6 months (for the chart)
    current_month_start = today.replace(day=1)
    six_months_ago = current_month_start - timedelta(days=30*6)
    six_months_ago_start = six_months_ago.replace(day=1)

    monthly_income_last_6 = Income.objects.filter(
        barber=barber,
        date__gte=six_months_ago_start,
        date__lt=current_month_start + timedelta(days=32)
    ).extra(
        select={'month': "strftime('%%Y-%%m', date)"}
    ).values('month').annotate(
        total=Sum('amount')
    ).order_by('month')

    import calendar
    chart_labels = []
    chart_data = []
    current_iter_month = six_months_ago_start.replace(day=1)
    income_dict = {item['month']: float(item['total']) for item in monthly_income_last_6}

    while current_iter_month < current_month_start + timedelta(days=31):
        month_key = current_iter_month.strftime('%Y-%m')
        chart_labels.append(calendar.month_abbr[current_iter_month.month] + " " + current_iter_month.strftime('%y'))
        chart_data.append(income_dict.get(month_key, 0))
        if current_iter_month.month == 12:
            current_iter_month = current_iter_month.replace(year=current_iter_month.year + 1, month=1)
        else:
            current_iter_month = current_iter_month.replace(month=current_iter_month.month + 1)

    # --- New Logic for Specific Month Selection ---
    selected_month_str = request.GET.get('month', '') # Get the month from query parameters
    selected_month_income = 0
    selected_month_transactions = []
    selected_month_services = []

    if selected_month_str:
        try:
            # Parse the selected month string (e.g., '2024-11')
            selected_month_date = datetime.strptime(selected_month_str, '%Y-%m').date()
            # Calculate the start and end of the selected month
            selected_month_start = selected_month_date.replace(day=1)
            if selected_month_start.month == 12:
                selected_month_end = selected_month_start.replace(year=selected_month_start.year + 1, month=1, day=1) - timedelta(days=1)
            else:
                selected_month_end = selected_month_start.replace(month=selected_month_start.month + 1, day=1) - timedelta(days=1)

            # Query income for the selected month
            selected_month_transactions = Income.objects.filter(
                barber=barber,
                date__gte=selected_month_start,
                date__lte=selected_month_end
            ).select_related('client', 'service').order_by('-date', '-created_at')

            # Calculate total income for the selected month
            selected_month_income = selected_month_transactions.aggregate(total=Sum('amount'))['total'] or 0

            # Calculate service counts for the selected month
            selected_month_services = selected_month_transactions.values('service__name').annotate(count=Count('id'))

        except ValueError:
            # Handle invalid month string format gracefully
            messages.error(request, f"Invalid month format: {selected_month_str}. Please use YYYY-MM.")
            selected_month_str = '' # Reset to show current month's data if any error occurs

    # Today's completed services (unchanged)
    today_completed = Income.objects.filter(barber=barber, date=today).select_related('client', 'service')

    context = {
        'daily_income': daily_income,
        'weekly_income': weekly_income,
        'monthly_income': monthly_income,
        'daily_services': daily_services,
        'weekly_services': weekly_services,
        'monthly_services': monthly_services,
        'today_completed': today_completed,
        'chart_labels': chart_labels[-6:],
        'chart_data': chart_data[-6:],
        # Add new context variables for selected month
        'selected_month_str': selected_month_str,
        'selected_month_income': selected_month_income,
        'selected_month_transactions': selected_month_transactions,
        'selected_month_services': selected_month_services,
    }
    return render(request, 'barber/dashboard.html', context)


@login_required
def home(request):
    """Home page with queue and quick start buttons"""
    barber = request.user
    today = timezone.now().date()
    now = timezone.now()
    
    # Get active service (in progress)
    active_booking = Booking.objects.filter(
        barber=barber,
        status='in_progress',
        timer_started_at__isnull=False
    ).first()
    
    # Get queue - all waiting clients
    queue = Booking.objects.filter(
        barber=barber,
        status='waiting'
    ).order_by('queue_position', 'added_to_queue_at')
    
    # Add appointments that have reached their time to the queue
    pending_appointments = Booking.objects.filter(
        barber=barber,
        status__in=['pending', 'confirmed'],
        appointment_date=today,
        appointment_time__lte=now.time()
    )
    
    for appt in pending_appointments:
        appt.status = 'waiting'
        appt.save()
    
    # Refresh queue after adding appointments
    queue = Booking.objects.filter(
        barber=barber,
        status='waiting'
    ).order_by('queue_position', 'added_to_queue_at')
    
    context = {
        'active_booking': active_booking,
        'queue': queue,
    }
    
    return render(request, 'barber/home.html', context)


def register(request):
    """Barber registration - Creates a request pending admin approval."""
    if request.method == 'POST':
        form = BarberRegistrationForm(request.POST)
        if form.is_valid():
            # Get the raw password before the form clears it
            raw_password = form.cleaned_data.get('password1')

            # Hash the password for temporary storage in RegistrationRequest
            from django.contrib.auth.hashers import make_password
            hashed_password = make_password(raw_password)

            # Save the registration request
            RegistrationRequest.objects.create(
                username=form.cleaned_data['username'],
                email=form.cleaned_data['email'],
                phone=form.cleaned_data.get('phone', ''),
                password=hashed_password, # Store the hashed password
            )
            messages.success(request, 'Your registration request has been submitted. You will receive an email once approved.')
            return redirect('login') # Redirect to login page or a thank you page
    else:
        form = BarberRegistrationForm()
    return render(request, 'barber/register.html', {'form': form})


@login_required
def services_list(request):
    """List and manage services"""
    services = Service.objects.filter(barber=request.user)
    return render(request, 'barber/services_list.html', {'services': services})


@login_required
def service_create(request):
    """Create new service"""
    if request.method == 'POST':
        form = ServiceForm(request.POST, barber=request.user)
        if form.is_valid():
            service = form.save(commit=False)
            service.barber = request.user
            service.save()
            messages.success(request, 'Service created successfully!')
            return redirect('services_list')
    else:
        form = ServiceForm(barber=request.user)
    
    return render(request, 'barber/service_form.html', {'form': form})


@login_required
def service_edit(request, pk):
    """Edit service"""
    service = get_object_or_404(Service, pk=pk, barber=request.user)
    if request.method == 'POST':
        form = ServiceForm(request.POST, instance=service, barber=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, 'Service updated successfully!')
            return redirect('services_list')
    else:
        form = ServiceForm(instance=service, barber=request.user)
    
    return render(request, 'barber/service_form.html', {'form': form, 'service': service})


@login_required
def service_delete(request, pk):
    """Delete service"""
    service = get_object_or_404(Service, pk=pk, barber=request.user)
    service.delete()
    messages.success(request, 'Service deleted successfully!')
    return redirect('services_list')


@login_required
def clients_list(request):
    """List all clients"""
    clients = Client.objects.filter(barber=request.user)
    return render(request, 'barber/clients_list.html', {'clients': clients})


@login_required
def client_create(request):
    """Create new client and add to queue"""
    if request.method == 'POST':
        form = ClientForm(request.POST, barber=request.user)
        if form.is_valid():
            client = form.save(commit=False)
            client.barber = request.user
            client.save()
            
            # Add to queue
            Booking.objects.create(
                barber=request.user,
                client=client,
                status='waiting',
                is_walkin=True
            )
            
            messages.success(request, f'{client.name} {client.surname} added to queue!')
            return redirect('home')
    else:
        form = ClientForm(barber=request.user)
    
    return render(request, 'barber/client_form.html', {'form': form, 'quick_start': True})


@login_required
def client_detail(request, pk):
    """View client details and history"""
    client = get_object_or_404(Client, pk=pk, barber=request.user)
    bookings = Booking.objects.filter(client=client).order_by('-appointment_date', '-appointment_time')
    income_records = Income.objects.filter(client=client).order_by('-date')
    
    context = {
        'client': client,
        'bookings': bookings,
        'income_records': income_records,
    }
    
    return render(request, 'barber/client_detail.html', context)


@login_required
def client_delete(request, pk):
    """Delete client"""
    client = get_object_or_404(Client, pk=pk, barber=request.user)
    client_name = f"{client.name} {client.surname}"
    client.delete()
    messages.success(request, f'{client_name} deleted successfully!')
    return redirect('clients_list')


@login_required
def bookings_list(request):
    """List all bookings"""
    status_filter = request.GET.get('status', '')
    date_filter = request.GET.get('date', '')
    
    bookings = Booking.objects.filter(barber=request.user)
    
    if status_filter:
        bookings = bookings.filter(status=status_filter)
    
    if date_filter:
        bookings = bookings.filter(appointment_date=date_filter)
    
    return render(request, 'barber/bookings_list.html', {'bookings': bookings})


@login_required
def booking_create(request):
    """Create new booking (for walk-ins or manual entry)"""
    if request.method == 'POST':
        form = BookingForm(request.POST, barber=request.user)
        if form.is_valid():
            booking = form.save(commit=False)
            booking.barber = request.user
            booking.status = 'confirmed'
            
            # Generate cancellation token
            booking.cancellation_token = str(uuid.uuid4())
            
            booking.save()
            messages.success(request, 'Booking created successfully!')
            return redirect('bookings_list')
    else:
        form = BookingForm(barber=request.user)
    
    return render(request, 'barber/booking_form.html', {'form': form})


@login_required
def booking_start(request, pk):
    """Start service timer"""
    booking = get_object_or_404(Booking, pk=pk, barber=request.user)
    booking.status = 'in_progress'
    booking.timer_started_at = timezone.now()
    booking.save()
    messages.success(request, 'Timer started!')
    return redirect('dashboard')

@login_required
def booking_complete(request, pk):
    """Complete booking and record income - simplified to just ask payment method"""
    booking = get_object_or_404(Booking, pk=pk, barber=request.user)
    
    if request.method == 'POST':
        payment_method = request.POST.get('payment_method')
        
        # Auto-record income
        income = Income.objects.create(
            barber=request.user,
            client=booking.client,
            service=booking.service,
            booking=booking,
            amount=booking.service.price,
            payment_method=payment_method,
            is_walkin=booking.is_walkin,
            date=timezone.now().date()
        )
        
        # If no client record, use booking client name
        if not income.client and booking.client_name:
            income.client_name = booking.client_name
            income.save()
        
        # Complete booking
        booking.status = 'completed'
        booking.timer_ended_at = timezone.now()
        booking.save()
        
        messages.success(request, f'Service completed! R{booking.service.price} recorded.')
        return redirect('home')
    
    return render(request, 'barber/booking_complete.html', {'booking': booking})


@login_required
def select_existing_client(request):
    """Select existing client to add to queue"""
    search_query = request.GET.get('search', '')
    
    if request.method == 'POST':
        client_id = request.POST.get('client_id')
        client = get_object_or_404(Client, pk=client_id, barber=request.user)
        
        # Add to queue
        Booking.objects.create(
            barber=request.user,
            client=client,
            status='waiting',
            is_walkin=True
        )
        
        messages.success(request, f'{client.name} {client.surname} added to queue!')
        return redirect('home')
    
    clients = Client.objects.filter(barber=request.user)
    
    # Search functionality
    if search_query:
        clients = clients.filter(
            models.Q(name__icontains=search_query) |
            models.Q(surname__icontains=search_query) |
            models.Q(phone__icontains=search_query)
        )
    
    clients = clients.order_by('surname', 'name')
    
    return render(request, 'barber/select_client.html', {
        'clients': clients,
        'search_query': search_query
    })

@login_required
def start_service_from_queue(request, booking_id):
    """Start service for person in queue"""
    booking = get_object_or_404(Booking, pk=booking_id, barber=request.user, status='waiting')
    services = Service.objects.filter(barber=request.user)
    
    # Check if first in queue
    first_in_queue = Booking.objects.filter(
        barber=request.user,
        status='waiting'
    ).order_by('queue_position', 'added_to_queue_at').first()
    
    if booking != first_in_queue:
        messages.error(request, 'Can only start the first person in queue!')
        return redirect('home')
    
    if request.method == 'POST':
        service_id = request.POST.get('service')
        service = get_object_or_404(Service, pk=service_id, barber=request.user)
        
        booking.service = service
        booking.status = 'in_progress'
        booking.timer_started_at = timezone.now()
        booking.save()
        
        messages.success(request, f'Service started for {booking.get_client_name()}!')
        return redirect('home')
    
    return render(request, 'barber/start_service.html', {'booking': booking, 'services': services})


@login_required
def remove_from_queue(request, booking_id):
    """Remove person from queue"""
    booking = get_object_or_404(Booking, pk=booking_id, barber=request.user, status='waiting')
    
    client_name = booking.get_client_name()
    booking.status = 'removed'
    booking.save()
    
    # Reorder queue
    remaining_queue = Booking.objects.filter(
        barber=request.user,
        status='waiting'
    ).order_by('queue_position', 'added_to_queue_at')
    
    for idx, item in enumerate(remaining_queue, start=1):
        item.queue_position = idx
        item.save()
    
    messages.success(request, f'{client_name} removed from queue!')
    return redirect('home')


@login_required
def income_list(request):
    """List all income records"""
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')
    
    income_records = Income.objects.filter(barber=request.user)
    
    if date_from:
        income_records = income_records.filter(date__gte=date_from)
    if date_to:
        income_records = income_records.filter(date__lte=date_to)
    
    total = income_records.aggregate(total=Sum('amount'))['total'] or 0
    
    context = {
        'income_records': income_records,
        'total': total,
    }
    
    return render(request, 'barber/income_list.html', context)


@login_required
def credit_list(request):
    """List all clients who used credit this month"""
    today = timezone.now().date()
    month_start = today.replace(day=1)
    
    # Get all credit transactions for this month (both paid and unpaid)
    credit_transactions = Income.objects.filter(
        barber=request.user,
        payment_method='credit',
        date__gte=month_start
    ).select_related('client', 'service').order_by('credit_paid', '-date')
    
    # Calculate total credit owed per client (ONLY unpaid transactions)
    from django.db.models import Sum
    credit_summary = Income.objects.filter(
        barber=request.user,
        payment_method='credit',
        credit_paid=False,
        date__gte=month_start
    ).values('client', 'client__name', 'client__surname', 'client__phone').annotate(
        total_owed=Sum('amount'),
        unpaid_count=Count('id')  # Only count unpaid transactions
    ).order_by('-total_owed')
    
    # Total outstanding credit (only unpaid)
    total_credit = Income.objects.filter(
        barber=request.user,
        payment_method='credit',
        credit_paid=False,
        date__gte=month_start
    ).aggregate(total=Sum('amount'))['total'] or 0
    
    # Count paid and unpaid separately
    paid_count = Income.objects.filter(
        barber=request.user,
        payment_method='credit',
        credit_paid=True,
        date__gte=month_start
    ).count()
    
    unpaid_count = Income.objects.filter(
        barber=request.user,
        payment_method='credit',
        credit_paid=False,
        date__gte=month_start
    ).count()
    
    context = {
        'credit_transactions': credit_transactions,
        'credit_summary': credit_summary,
        'total_credit': total_credit,
        'month_start': month_start,
        'paid_count': paid_count,
        'unpaid_count': unpaid_count,
    }
    
    return render(request, 'barber/credit_list.html', context)

@login_required
def income_create(request):
    """Record income (for walk-ins without booking)"""
    if request.method == 'POST':
        form = IncomeForm(request.POST, barber=request.user)
        if form.is_valid():
            income = form.save(commit=False)
            income.barber = request.user
            income.date = timezone.now().date()
            income.save()
            messages.success(request, 'Income recorded successfully!')
            return redirect('income_list')
    else:
        form = IncomeForm(barber=request.user)
    
    return render(request, 'barber/income_form.html', {'form': form})


@login_required
def settings_view(request):
    """Settings page"""
    if request.method == 'POST':
        form = SettingsForm(request.POST, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, 'Settings updated successfully!')
            return redirect('settings')
    else:
        form = SettingsForm(instance=request.user)
    
    booking_url = request.build_absolute_uri(f'/book/{request.user.username}')
    
    return render(request, 'barber/settings.html', {'form': form, 'booking_url': booking_url})


# Public booking view
def public_booking(request, username):
    """Public booking page for clients"""
    barber = get_object_or_404(Barber, username=username)
    services = Service.objects.filter(barber=barber)
    
    if request.method == 'POST':
        form = PublicBookingForm(request.POST, barber=barber)
        if form.is_valid():
            booking = form.save(commit=False)
            booking.barber = barber
            booking.status = 'pending'
            booking.cancellation_token = str(uuid.uuid4())
            
            # Get or create client
            client, created = Client.objects.get_or_create(
                barber=barber,
                phone=form.cleaned_data['phone'],
                defaults={
                    'name': form.cleaned_data['name'].split()[0],
                    'surname': ' '.join(form.cleaned_data['name'].split()[1:]) if len(form.cleaned_data['name'].split()) > 1 else '',
                    'age_group': 'adult',
                    'gender': 'other',
                }
            )
            
            booking.client = client
            booking.client_name = form.cleaned_data['name']
            booking.client_phone = form.cleaned_data['phone']
            
            booking.save()
            
            # Send SMS confirmation
            if barber.sms_notifications_enabled:
                send_booking_confirmation(booking)
            
            messages.success(request, 'Booking created successfully! You will receive a confirmation SMS.')
            return redirect('booking_success')
    else:
        form = PublicBookingForm(barber=barber)
    
    # Get available time slots
    selected_date = request.GET.get('date')
    selected_service_id = request.GET.get('service')
    available_slots = []
    
    if selected_date and selected_service_id:
        try:
            date_obj = datetime.strptime(selected_date, '%Y-%m-%d').date()
            service = Service.objects.get(pk=selected_service_id, barber=barber)
            
            # Generate time slots
            current_time = datetime.combine(date_obj, barber.work_start_time)
            end_time = datetime.combine(date_obj, barber.work_end_time)
            
            while current_time < end_time:
                slot_time = current_time.time()
                
                # Check if slot is available
                slot_end = current_time + timedelta(minutes=service.duration_minutes)
                
                overlapping = Booking.objects.filter(
                    barber=barber,
                    appointment_date=date_obj,
                    status__in=['pending', 'confirmed', 'in_progress']
                ).exclude(appointment_time__gte=slot_end.time()).exclude(
                    appointment_time__lte=slot_time
                )
                
                if not overlapping.exists():
                    available_slots.append(slot_time.strftime('%H:%M'))
                
                current_time += timedelta(minutes=30)  # 30-minute increments
        except:
            pass
    
    context = {
        'barber': barber,
        'services': services,
        'form': form,
        'available_slots': available_slots,
    }
    
    return render(request, 'barber/public_booking.html', context)


def booking_success(request):
    """Booking success page"""
    return render(request, 'barber/booking_success.html')


def booking_cancel(request, token):
    """Cancel booking via token"""
    booking = get_object_or_404(Booking, cancellation_token=token)
    
    if request.method == 'POST':
        booking.status = 'cancelled'
        booking.save()
        messages.success(request, 'Booking cancelled successfully!')
        return redirect('booking_cancelled')
    
    return render(request, 'barber/booking_cancel.html', {'booking': booking})


def booking_cancelled(request):
    """Booking cancelled confirmation"""
    return render(request, 'barber/booking_cancelled.html')


@login_required
def mark_credit_paid(request, income_id):
    """Mark a credit transaction as paid"""
    income = get_object_or_404(Income, pk=income_id, barber=request.user, payment_method='credit')
    income.credit_paid = True
    income.credit_paid_date = timezone.now().date()
    income.save()
    
    client_name = income.client.name if income.client else income.client_name
    messages.success(request, f'Credit payment from {client_name} marked as paid!')
    return redirect('credit_list')


def get_available_slots_ajax(request, username):
    """AJAX view to return available time slots for a given date and service."""
    from django.http import JsonResponse
    from django.shortcuts import get_object_or_404
    from django.utils import timezone
    from datetime import datetime, timedelta
    from .models import Barber, Service, Booking

    # Get the barber
    barber = get_object_or_404(Barber, username=username)

    # Get date and service ID from GET parameters
    selected_date_str = request.GET.get('date')
    selected_service_id = request.GET.get('service')

    available_slots = []

    if selected_date_str and selected_service_id:
        try:
            date_obj = datetime.strptime(selected_date_str, '%Y-%m-%d').date()
            service = Service.objects.get(pk=selected_service_id, barber=barber)

            # Generate time slots (similar logic to public_booking)
            current_time = datetime.combine(date_obj, barber.work_start_time)
            end_time = datetime.combine(date_obj, barber.work_end_time)

            while current_time.time() < end_time.time():
                slot_time = current_time.time()
                slot_end = current_time + timedelta(minutes=service.duration_minutes)

                # Check for overlapping bookings
                overlapping = Booking.objects.filter(
                    barber=barber,
                    appointment_date=date_obj,
                    status__in=['pending', 'confirmed', 'in_progress']
                ).exclude(appointment_time__gte=slot_end.time()).exclude(
                    appointment_time__lt=slot_time # Changed from <= to < for inclusivity check
                )

                if not overlapping.exists():
                    available_slots.append(slot_time.strftime('%H:%M'))

                current_time += timedelta(minutes=30)  # 30-minute increments
        except (ValueError, Service.DoesNotExist):
            # Handle invalid date format or service not found
            pass

    # Return JSON response
    return JsonResponse({'available_slots': available_slots})


def register(request):
    """Barber registration - Creates a request pending admin approval."""
    if request.method == 'POST':
        form = BarberRegistrationForm(request.POST)
        if form.is_valid():
            # Get the raw password before the form clears it
            raw_password = form.cleaned_data.get('password1')

            # Hash the password for temporary storage in RegistrationRequest
            # Note: This is slightly less secure than Django's default hashing flow,
            # but acceptable for this temporary storage scenario.
            # Consider using make_password from django.contrib.auth.hashers
            from django.contrib.auth.hashers import make_password
            hashed_password = make_password(raw_password)

            # Save the registration request
            RegistrationRequest.objects.create(
                username=form.cleaned_data['username'],
                email=form.cleaned_data['email'],
                phone=form.cleaned_data.get('phone', ''),
                password=hashed_password, # Store the hashed password
            )
            messages.success(request, 'Your registration request has been submitted. You will receive an email once approved.')
            return redirect('login') # Redirect to login page or a thank you page
    else:
        form = BarberRegistrationForm()
    return render(request, 'barber/register.html', {'form': form})