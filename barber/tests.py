# barber/tests.py
# This file consolidates all tests for the barber app into one place.
# You can run all tests using: python manage.py test barber.tests

from django.test import TestCase, Client as DjangoTestClient
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from datetime import date, time, datetime, timedelta
from django.core.exceptions import ValidationError
from barber.models import Barber, Service, Client, Booking, Income
from barber.forms import (
    BarberRegistrationForm, ServiceForm, ClientForm, BookingForm,
    IncomeForm, SettingsForm, PublicBookingForm
)

User = get_user_model()

# ==================== MODEL TESTS ====================

class TestBarberModel(TestCase):
    def setUp(self):
        self.barber_data = {
            'username': 'test_barber',
            'email': 'barber@example.com',
            'phone': '0123456789',
            'work_start_time': time(9, 0),
            'work_end_time': time(17, 0),
        }
        self.barber = Barber.objects.create_user(**self.barber_data)

    def test_barber_creation(self):
        self.assertEqual(self.barber.username, 'test_barber')
        self.assertEqual(self.barber.email, 'barber@example.com')
        self.assertEqual(self.barber.phone, '0123456789')
        self.assertEqual(self.barber.work_start_time, time(9, 0))
        self.assertEqual(self.barber.work_end_time, time(17, 0))
        self.assertTrue(self.barber.sms_notifications_enabled)

    def test_get_booking_url(self):
        expected_url = f"/book/{self.barber.username}"
        self.assertEqual(self.barber.get_booking_url(), expected_url)

class TestServiceModel(TestCase):
    def setUp(self):
        self.barber = Barber.objects.create_user(username='test_barber', password='testpass123')
        self.service = Service.objects.create(
            barber=self.barber,
            name='Haircut',
            duration_minutes=40,
            price=100.00
        )

    def test_service_creation(self):
        self.assertEqual(self.service.name, 'Haircut')
        self.assertEqual(self.service.barber, self.barber)
        self.assertEqual(self.service.duration_minutes, 40)
        self.assertAlmostEqual(float(self.service.price), 100.00, places=2)

    def test_unique_together_constraint(self):
        with self.assertRaises(ValidationError):
            duplicate_service = Service(
                barber=self.barber,
                name='Haircut', # Same name for same barber
                duration_minutes=30,
                price=90.00
            )
            duplicate_service.full_clean() # This should trigger the validation
            duplicate_service.save()

class TestClientModel(TestCase):
    def setUp(self):
        self.barber = Barber.objects.create_user(username='test_barber', password='testpass123')
        self.client_data = {
            'barber': self.barber,
            'name': 'John',
            'surname': 'Doe',
            'phone': '0987654321',
            'age_group': 'adult',
            'gender': 'male',
        }

    def test_client_creation(self):
        client = Client.objects.create(**self.client_data)
        self.assertEqual(client.name, 'John')
        self.assertEqual(client.surname, 'Doe')
        self.assertEqual(client.phone, '0987654321')
        self.assertEqual(client.barber, self.barber)

    def test_phone_unique_per_barber(self):
        Client.objects.create(**self.client_data)
        with self.assertRaises(ValidationError):
            duplicate_client = Client(
                barber=self.barber,
                name='Jane',
                surname='Smith',
                phone='0987654321', # Same phone for same barber
                age_group='adult',
                gender='female',
            )
            duplicate_client.full_clean() # This should trigger the validation
            duplicate_client.save()

class TestBookingModel(TestCase):
    def setUp(self):
        self.barber = Barber.objects.create_user(username='test_barber', password='testpass123')
        self.client_obj = Client.objects.create(
            barber=self.barber,
            name='John',
            surname='Doe',
            phone='0987654321',
            age_group='adult',
            gender='male',
        )
        self.service = Service.objects.create(
            barber=self.barber,
            name='Haircut',
            duration_minutes=40,
            price=100.00
        )
        self.booking_data = {
            'barber': self.barber,
            'client': self.client_obj,
            'service': self.service,
            'appointment_date': date.today(),
            'appointment_time': time(10, 0),
            'status': 'pending',
        }

    def test_booking_creation(self):
        booking = Booking.objects.create(**self.booking_data)
        self.assertEqual(booking.client, self.client_obj)
        self.assertEqual(booking.service, self.service)
        self.assertEqual(booking.status, 'pending')
        self.assertEqual(booking.appointment_date, date.today())
        self.assertEqual(booking.appointment_time, time(10, 0))

    def test_get_client_name(self):
        booking = Booking.objects.create(**self.booking_data)
        self.assertEqual(booking.get_client_name(), 'John Doe')

    def test_get_client_phone(self):
        booking = Booking.objects.create(**self.booking_data)
        self.assertEqual(booking.get_client_phone(), '0987654321')

    def test_queue_position_assignment(self):
        booking1 = Booking.objects.create(
            barber=self.barber, client=self.client_obj, service=self.service, status='waiting'
        )
        booking2 = Booking.objects.create(
            barber=self.barber, client=self.client_obj, service=self.service, status='waiting'
        )
        booking1.refresh_from_db()
        booking2.refresh_from_db()
        self.assertEqual(booking1.queue_position, 1)
        self.assertEqual(booking2.queue_position, 2)

class TestIncomeModel(TestCase):
    def setUp(self):
        self.barber = Barber.objects.create_user(username='test_barber', password='testpass123')
        self.client_obj = Client.objects.create(
            barber=self.barber,
            name='John',
            surname='Doe',
            phone='0987654321',
            age_group='adult',
            gender='male',
        )
        self.service = Service.objects.create(
            barber=self.barber,
            name='Haircut',
            duration_minutes=40,
            price=100.00
        )
        self.booking = Booking.objects.create(
            barber=self.barber,
            client=self.client_obj,
            service=self.service,
            appointment_date=date.today(),
            appointment_time=time(10, 0),
            status='completed',
        )
        self.income_data = {
            'barber': self.barber,
            'client': self.client_obj,
            'service': self.service,
            'booking': self.booking,
            'amount': 100.00,
            'payment_method': 'cash',
            'date': date.today(),
        }

    def test_income_creation(self):
        income = Income.objects.create(**self.income_data)
        self.assertEqual(income.barber, self.barber)
        self.assertEqual(income.client, self.client_obj)
        self.assertEqual(income.service, self.service)
        self.assertEqual(income.booking, self.booking)
        self.assertAlmostEqual(float(income.amount), 100.00, places=2)
        self.assertEqual(income.payment_method, 'cash')
        self.assertEqual(income.date, date.today())
        self.assertFalse(income.credit_paid)

    def test_income_with_walkin(self):
        income = Income.objects.create(
            barber=self.barber,
            client_name='Walk-in Client',
            service=self.service,
            amount=80.00,
            payment_method='card',
            is_walkin=True,
            date=date.today(),
        )
        self.assertEqual(income.client_name, 'Walk-in Client')
        self.assertTrue(income.is_walkin)

# ==================== FORM TESTS ====================

class TestBarberRegistrationForm(TestCase):
    def test_valid_form(self):
        form_data = {
            'username': 'newbarber',
            'email': 'newbarber@example.com',
            'phone': '0112233445',
            'password1': 'strongpassword123',
            'password2': 'strongpassword123',
        }
        form = BarberRegistrationForm(data=form_data)
        self.assertTrue(form.is_valid())

    def test_invalid_form_password_mismatch(self):
        form_data = {
            'username': 'newbarber',
            'email': 'newbarber@example.com',
            'phone': '0112233445',
            'password1': 'strongpassword123',
            'password2': 'differentpassword456',
        }
        form = BarberRegistrationForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn('password2', form.errors)

class TestServiceForm(TestCase):
    def setUp(self):
        self.barber = Barber.objects.create_user(username='test_barber', password='testpass123')

    def test_valid_form(self):
        form_data = {
            'name': 'Beard Trim',
            'duration_minutes': 20,
            'price': 60.00,
        }
        form = ServiceForm(data=form_data, barber=self.barber)
        self.assertTrue(form.is_valid())

    # Note: The original model does not enforce duration > 0 via full_clean()
    # It relies on database constraints. The form validation might be stricter.
    # This test assumes the form *does* validate negative duration.
    def test_invalid_form_negative_duration(self):
        form_data = {
            'name': 'Bad Service',
            'duration_minutes': -10, # Invalid
            'price': 50.00,
        }
        form = ServiceForm(data=form_data, barber=self.barber)
        # Assuming the form has custom validation or the model's clean() method handles this
        # If the model itself doesn't validate this in clean(), the form might need explicit validation.
        # For now, let's assume the form's clean_duration_minutes method or similar handles it.
        # If the current form/model doesn't fail this test, the validation logic needs to be added to the form.
        self.assertFalse(form.is_valid())
        self.assertIn('duration_minutes', form.errors)


class TestClientForm(TestCase):
    def setUp(self):
        self.barber = Barber.objects.create_user(username='test_barber', password='testpass123')

    def test_valid_form(self):
        form_data = {
            'name': 'Jane',
            'surname': 'Smith',
            'phone': '0556677889',
            'age_group': 'adult',
            'gender': 'female',
        }
        form = ClientForm(data=form_data, barber=self.barber)
        self.assertTrue(form.is_valid())

class TestBookingForm(TestCase):
    def setUp(self):
        self.barber = Barber.objects.create_user(username='test_barber', password='testpass123')
        self.client_obj = Client.objects.create(
            barber=self.barber, name='John', surname='Doe', phone='0987654321', age_group='adult', gender='male'
        )
        self.service = Service.objects.create(
            barber=self.barber, name='Haircut', duration_minutes=40, price=100.00
        )

    def test_valid_form_with_client(self):
        form_data = {
            'client': self.client_obj.id,
            'service': self.service.id,
            'appointment_date': date.today(),
            'appointment_time': time(14, 30),
            'is_walkin': False,
        }
        form = BookingForm(data=form_data, barber=self.barber)
        self.assertTrue(form.is_valid())

    def test_valid_form_for_walkin(self):
        form_data = {
            'client': '', # No client selected
            'service': self.service.id,
            'appointment_date': date.today(),
            'appointment_time': time(14, 30),
            'is_walkin': True,
            'client_name': 'Walk-in Jane',
            'client_phone': '0111222333',
        }
        form = BookingForm(data=form_data, barber=self.barber)
        self.assertTrue(form.is_valid())

class TestIncomeForm(TestCase):
    def setUp(self):
        self.barber = Barber.objects.create_user(username='test_barber', password='testpass123')
        self.client_obj = Client.objects.create(
            barber=self.barber, name='John', surname='Doe', phone='0987654321', age_group='adult', gender='male'
        )
        self.service = Service.objects.create(
            barber=self.barber, name='Haircut', duration_minutes=40, price=100.00
        )

    def test_valid_form_with_client(self):
        form_data = {
            'client': self.client_obj.id,
            'service': self.service.id,
            'amount': 100.00,
            'payment_method': 'cash',
        }
        form = IncomeForm(data=form_data, barber=self.barber)
        self.assertTrue(form.is_valid())

    def test_valid_form_for_walkin(self):
        form_data = {
            'client': '', # No client selected
            'service': self.service.id,
            'amount': 80.00,
            'payment_method': 'card',
            'is_walkin': True,
            'client_name': 'Walk-in Client',
        }
        form = IncomeForm(data=form_data, barber=self.barber)
        self.assertTrue(form.is_valid())

class TestSettingsForm(TestCase):
    def setUp(self):
        self.barber = Barber.objects.create_user(
            username='test_barber', password='testpass123', phone='0123456789',
            work_start_time=time(9, 0), work_end_time=time(17, 0)
        )

    def test_valid_form(self):
        form_data = {
            'email': 'updated@example.com',
            'phone': '0998877665',
            'work_start_time': time(8, 0),
            'work_end_time': time(18, 0),
            'sms_notifications_enabled': False,
        }
        form = SettingsForm(data=form_data, instance=self.barber)
        self.assertTrue(form.is_valid())

class TestPublicBookingForm(TestCase):
    def setUp(self):
        self.barber = Barber.objects.create_user(username='test_barber', password='testpass123')
        self.service = Service.objects.create(
            barber=self.barber, name='Haircut', duration_minutes=40, price=100.00
        )

    def test_valid_form(self):
        form_data = {
            'name': 'Public Client',
            'phone': '0334455667',
            'service': self.service.id,
            'appointment_date': date.today(),
            'appointment_time': '10:00', # Assuming time is selected from available slots
        }
        form = PublicBookingForm(data=form_data, barber=self.barber)
        self.assertTrue(form.is_valid())

    def test_invalid_form_missing_fields(self):
        form_data = {
            'name': 'Public Client',
            # 'phone' is missing
            'service': self.service.id,
            'appointment_date': date.today(),
            'appointment_time': '10:00',
        }
        form = PublicBookingForm(data=form_data, barber=self.barber)
        self.assertFalse(form.is_valid())
        self.assertIn('phone', form.errors)

# ==================== VIEW TESTS ====================

class TestViews(TestCase):
    def setUp(self):
        self.client = Client() # Django's test client - DO NOT REDEFINE ELSEWHERE IN TESTS
        self.barber = Barber.objects.create_user(
            username='test_barber',
            password='testpass123',
            email='barber@example.com',
            phone='0123456789'
        )
        self.service = Service.objects.create(
            barber=self.barber,
            name='Haircut',
            duration_minutes=40,
            price=100.00
        )
        self.client_obj = Client.objects.create(
            barber=self.barber,
            name='John',
            surname='Doe',
            phone='0987654321',
            age_group='adult',
            gender='male',
        )
        self.booking = Booking.objects.create(
            barber=self.barber,
            client=self.client_obj,
            service=self.service,
            appointment_date=date.today(),
            appointment_time=time(10, 0),
            status='pending',
        )
        self.income = Income.objects.create(
            barber=self.barber,
            client=self.client_obj,
            service=self.service,
            booking=self.booking,
            amount=100.00,
            payment_method='cash',
            date=date.today(),
        )

    def test_home_view_requires_login(self):
        response = self.client.get(reverse('home'))
        self.assertRedirects(response, f"{reverse('login')}?next={reverse('home')}")

    def test_home_view_authenticated(self):
        self.client.login(username='test_barber', password='testpass123')
        response = self.client.get(reverse('home'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Queue')

    def test_dashboard_view_requires_login(self):
        response = self.client.get(reverse('dashboard'))
        self.assertRedirects(response, f"{reverse('login')}?next={reverse('dashboard')}")

    def test_dashboard_view_authenticated(self):
        self.client.login(username='test_barber', password='testpass123')
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Dashboard')

    def test_services_list_view_authenticated(self):
        self.client.login(username='test_barber', password='testpass123')
        response = self.client.get(reverse('services_list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Haircut')

    def test_client_create_view_get_authenticated(self):
        self.client.login(username='test_barber', password='testpass123')
        response = self.client.get(reverse('client_create'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Add Client')

    def test_client_create_view_post_authenticated(self):
        self.client.login(username='test_barber', password='testpass123')
        response = self.client.post(reverse('client_create'), {
            'name': 'New',
            'surname': 'Client',
            'phone': '0112233445',
            'age_group': 'adult',
            'gender': 'male',
        })
        # Original code adds to queue, redirects to home
        self.assertRedirects(response, reverse('home'))
        self.assertTrue(Client.objects.filter(phone='0112233445').exists())

    def test_booking_create_view_get_authenticated(self):
        self.client.login(username='test_barber', password='testpass123')
        response = self.client.get(reverse('booking_create'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Add Booking')

    def test_booking_create_view_post_authenticated(self):
        self.client.login(username='test_barber', password='testpass123')
        response = self.client.post(reverse('booking_create'), {
            'client': self.client_obj.id,
            'service': self.service.id,
            'appointment_date': date.today(),
            'appointment_time': time(14, 0),
            'is_walkin': False,
        })
        self.assertRedirects(response, reverse('bookings_list'))
        self.assertTrue(Booking.objects.filter(appointment_time=time(14, 0)).exists())

    def test_income_list_view_authenticated(self):
        self.client.login(username='test_barber', password='testpass123')
        response = self.client.get(reverse('income_list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'R100.00')

    def test_credit_list_view_authenticated(self):
        Income.objects.create(
            barber=self.barber,
            client=self.client_obj,
            service=self.service,
            amount=50.00,
            payment_method='credit',
            date=date.today(),
            credit_paid=False
        )
        self.client.login(username='test_barber', password='testpass123')
        response = self.client.get(reverse('credit_list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Outstanding Credit')

    def test_settings_view_authenticated(self):
        self.client.login(username='test_barber', password='testpass123')
        response = self.client.get(reverse('settings'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Settings')

    def test_public_booking_view_get(self):
        response = self.client.get(reverse('public_booking', kwargs={'username': 'test_barber'}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Book Appointment')

    def test_public_booking_view_post(self):
        # Note: This test might trigger SMS sending logic depending on your settings.
        # Ensure sms_notifications_enabled is False for the barber or mock the SMS function.
        self.barber.sms_notifications_enabled = False
        self.barber.save()

        response = self.client.post(reverse('public_booking', kwargs={'username': 'test_barber'}), {
            'name': 'Public Client',
            'phone': '0334455667',
            'service': self.service.id,
            'appointment_date': date.today(),
            'appointment_time': '10:00', # This needs to be an available slot
        })
        # Assuming successful booking redirects to success page
        self.assertRedirects(response, reverse('booking_success'))
        # Check if booking was created
        booking_exists = Booking.objects.filter(
            client__phone='0334455667',
            appointment_time='10:00'
        ).exists()
        self.assertTrue(booking_exists)

    def test_booking_success_view(self):
        response = self.client.get(reverse('booking_success'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Booking Confirmed!')

    def test_login_view_get(self):
        response = self.client.get(reverse('login'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Login')

    def test_register_view_get(self):
        response = self.client.get(reverse('register'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Register')

    # Add more tests for other views as needed (e.g., delete, edit, detail views)
    # Remember to handle authentication for views that require it.
    # Remember to handle POST data correctly for views that process forms.
    # Consider mocking external services (like SMS) if they are called during view processing.