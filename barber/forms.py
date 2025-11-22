from django import forms
from django.contrib.auth.forms import UserCreationForm
from .models import Barber, Service, Client, Booking, Income
from datetime import datetime, timedelta, date


class BarberRegistrationForm(UserCreationForm):
    email = forms.EmailField(required=True)
    phone = forms.CharField(max_length=15, required=False)
    
    class Meta:
        model = Barber
        fields = ['username', 'email', 'phone', 'password1', 'password2']


class ServiceForm(forms.ModelForm):
    class Meta:
        model = Service
        fields = ['name', 'duration_minutes', 'price']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'duration_minutes': forms.NumberInput(attrs={'class': 'form-control', 'min': '1'}),
            'price': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0.01'}),
        }

    def __init__(self, *args, **kwargs):
        self.barber = kwargs.pop('barber', None)
        super().__init__(*args, **kwargs)

    def clean_duration_minutes(self):
        """Validate that duration is positive"""
        duration = self.cleaned_data.get('duration_minutes')
        if duration is not None and duration <= 0:
            raise forms.ValidationError('Duration must be a positive number.')
        return duration

    def clean_price(self):
        """Validate that price is positive"""
        price = self.cleaned_data.get('price')
        if price is not None and price <= 0:
            raise forms.ValidationError('Price must be a positive number.')
        return price

    def save(self, commit=True):
        instance = super().save(commit=False)
        if self.barber:
            instance.barber = self.barber
        if commit:
            instance.save()
        return instance


class ClientForm(forms.ModelForm):
    class Meta:
        model = Client
        fields = ['name', 'surname', 'phone', 'age_group', 'gender']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'surname': forms.TextInput(attrs={'class': 'form-control'}),
            'phone': forms.TextInput(attrs={'class': 'form-control'}),
            'age_group': forms.Select(attrs={'class': 'form-control'}),
            'gender': forms.Select(attrs={'class': 'form-control'}),
        }
    
    def __init__(self, *args, **kwargs):
        self.barber = kwargs.pop('barber', None)
        super().__init__(*args, **kwargs)


class BookingForm(forms.ModelForm):
    class Meta:
        model = Booking
        fields = ['client', 'service', 'appointment_date', 'appointment_time', 'is_walkin', 'client_name', 'client_phone']
        widgets = {
            'client': forms.Select(attrs={'class': 'form-control'}),
            'service': forms.Select(attrs={'class': 'form-control'}),
            'appointment_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'appointment_time': forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
            'is_walkin': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'client_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'For walk-ins without client record'}),
            'client_phone': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'For walk-ins without client record'}),
        }
    
    def __init__(self, *args, **kwargs):
        self.barber = kwargs.pop('barber', None)
        super().__init__(*args, **kwargs)
        if self.barber:
            self.fields['client'].queryset = Client.objects.filter(barber=self.barber)
            self.fields['service'].queryset = Service.objects.filter(barber=self.barber)


class IncomeForm(forms.ModelForm):
    class Meta:
        model = Income
        fields = ['client', 'service', 'amount', 'payment_method', 'is_walkin', 'client_name']
        widgets = {
            'client': forms.Select(attrs={'class': 'form-control'}),
            'service': forms.Select(attrs={'class': 'form-control'}),
            'amount': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'payment_method': forms.Select(attrs={'class': 'form-control'}),
            'is_walkin': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'client_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'For walk-ins'}),
        }
    
    def __init__(self, *args, **kwargs):
        self.barber = kwargs.pop('barber', None)
        super().__init__(*args, **kwargs)
        if self.barber:
            self.fields['client'].queryset = Client.objects.filter(barber=self.barber)
            self.fields['service'].queryset = Service.objects.filter(barber=self.barber)
            self.fields['client'].required = False


class SettingsForm(forms.ModelForm):
    class Meta:
        model = Barber
        fields = ['email', 'phone', 'work_start_time', 'work_end_time', 'sms_notifications_enabled']
        widgets = {
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'phone': forms.TextInput(attrs={'class': 'form-control'}),
            'work_start_time': forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
            'work_end_time': forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
            'sms_notifications_enabled': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class PublicBookingForm(forms.ModelForm):
    name = forms.CharField(max_length=200, widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Full Name'}))
    phone = forms.CharField(max_length=15, widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Phone Number'}))
    
    class Meta:
        model = Booking
        fields = ['service', 'appointment_date', 'appointment_time']
        widgets = {
            'service': forms.Select(attrs={'class': 'form-control'}),
            'appointment_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'appointment_time': forms.Select(attrs={'class': 'form-control'}),
        }
    
    def __init__(self, *args, **kwargs):
        self.barber = kwargs.pop('barber', None)
        super().__init__(*args, **kwargs)
        if self.barber:
            self.fields['service'].queryset = Service.objects.filter(barber=self.barber)
            
            # Set date limits
            min_date = date.today()
            max_date = min_date + timedelta(days=14)
            self.fields['appointment_date'].widget.attrs.update({
                'min': min_date.strftime('%Y-%m-%d'),
                'max': max_date.strftime('%Y-%m-%d'),
            })