
import uuid
import re

import re
import uuid
from django import forms
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator

# MODELS
from .models import User
from patients.models import Patient


User = get_user_model()


class RenameUsernameForm(forms.Form):
    new_username = forms.CharField(
        max_length=150,
        label="New Username",
        widget=forms.TextInput(attrs={"class": "input", "placeholder": "Enter new username"})
    )

    def __init__(self, *args, **kwargs):
        self.current_user = kwargs.pop("current_user", None)
        super().__init__(*args, **kwargs)

    def clean_new_username(self):
        username = self.cleaned_data['new_username'].strip()
        if self.current_user and username == self.current_user.username:
            raise forms.ValidationError("You are already using this username.")
        if User.objects.filter(username__iexact=username).exists():
            raise forms.ValidationError("That username is already taken.")
        return username


# -----------------------------
# OTP forms (password reset OTPs kept)
# -----------------------------
class ForgotPasswordForm(forms.Form):
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={"class": "input", "placeholder": "Registered email"}),
        label="Email",
    )

    def clean_email(self):
        """
        Normalize the email and do NOT raise if the account doesn't exist.
        The view handles non-existent emails and shows a generic response.
        """
        return self.cleaned_data["email"].strip().lower()


class VerifyOTPForm(forms.Form):
    email = forms.EmailField(widget=forms.EmailInput(attrs={"class": "input"}), label="Email")
    otp = forms.CharField(
        max_length=6,
        widget=forms.TextInput(attrs={"class": "input", "placeholder": "6-digit code"}),
        label="OTP",
    )

    def clean_otp(self):
        otp = self.cleaned_data["otp"].strip()
        if not otp.isdigit() or len(otp) != 6:
            raise forms.ValidationError("Enter the 6-digit code sent to your email.")
        return otp


class ResetPasswordForm(forms.Form):
    """Used for resetting password after OTP verification."""
    new_password1 = forms.CharField(
        label="New password",
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password", "placeholder": "New password"}),
        min_length=6,
    )
    new_password2 = forms.CharField(
        label="Confirm new password",
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password", "placeholder": "Confirm password"}),
        min_length=6,
    )

    def clean(self):
        cleaned = super().clean()
        p1 = cleaned.get("new_password1")
        p2 = cleaned.get("new_password2")
        if p1 and p2 and p1 != p2:
            raise forms.ValidationError("Passwords do not match.")
        return cleaned

# -----------------------------
# Account & profile forms
# -----------------------------
import re
from django import forms
from django.contrib.auth import get_user_model

User = get_user_model()

PHONE_RE = re.compile(r"^\d{7,15}$")


class UserProfileForm(forms.ModelForm):
    """Form to edit User personal information (name, email, phone, address)"""
    class Meta:
        model = User
        fields = [
            'first_name',
            'last_name',
            'email',
            'phone',
            'address',
            'bio',
            'profile_pic',
        ]
        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'mc-field', 'placeholder': 'First Name'}),
            'last_name': forms.TextInput(attrs={'class': 'mc-field', 'placeholder': 'Last Name'}),
            'email': forms.EmailInput(attrs={'class': 'mc-field', 'placeholder': 'Email Address'}),
            'phone': forms.TextInput(attrs={'class': 'mc-field', 'placeholder': 'Phone Number'}),
            'address': forms.Textarea(attrs={'class': 'mc-textarea', 'rows': 3, 'placeholder': 'Full Address'}),
            'bio': forms.Textarea(attrs={'class': 'mc-textarea', 'rows': 4, 'placeholder': 'Short biography'}),
            'profile_pic': forms.FileInput(attrs={'class': 'mc-field', 'accept': 'image/*'}),
        }

    def __init__(self, *args, **kwargs):
        self.user_instance = kwargs.pop('instance', None)
        super().__init__(*args, instance=self.user_instance, **kwargs)

    def clean_email(self):
        """Validate email is unique"""
        email = self.cleaned_data.get("email")
        if not email:
            return email
        
        qs = User.objects.filter(email__iexact=email)
        if self.user_instance and self.user_instance.pk:
            qs = qs.exclude(pk=self.user_instance.pk)
        
        if qs.exists():
            raise forms.ValidationError("This email is already in use by another user.")
        return email

    def clean_phone(self):
        """Validate phone number format"""
        phone = (self.cleaned_data.get("phone") or "").strip()
        if not phone:
            return phone
        normalized = re.sub(r"[ \-()]", "", phone)
        if not PHONE_RE.match(normalized):
            raise forms.ValidationError("Enter a valid phone number (7–15 digits).")
        return normalized

from django import forms
from django.contrib.auth import get_user_model

User = get_user_model()


class UserCreationForm(forms.ModelForm):
    """
    Form to create new users.
    - Admin can create: Admin, Doctor, Receptionist, Patient
    - Receptionist can create: Doctor, Patient (NOT Receptionist or Admin)
    """
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={"class": "input", "placeholder": "Enter password"}),
        label="Password",
        required=True
    )
    username = forms.CharField(
        max_length=150,
        label="Username",
        widget=forms.TextInput(attrs={"class": "input", "placeholder": "Enter username"}),
        required=True
    )
    email = forms.EmailField(
        required=False,
        widget=forms.EmailInput(attrs={"class": "input", "placeholder": "Enter email"})
    )

    class Meta:
        model = User
        fields = ['username', 'email', 'role', 'password', 'first_name', 'last_name', 'phone', 'address']
        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'input', 'placeholder': 'First Name'}),
            'last_name': forms.TextInput(attrs={'class': 'input', 'placeholder': 'Last Name'}),
            'role': forms.Select(attrs={'class': 'input'}),
            'phone': forms.TextInput(attrs={'class': 'input', 'placeholder': 'Phone Number'}),
            'address': forms.Textarea(attrs={'class': 'input', 'rows': 3, 'placeholder': 'Address'}),
        }

    def __init__(self, *args, **kwargs):
        self.current_user = kwargs.pop('current_user', None)
        super().__init__(*args, **kwargs)

        # Restrict role choices based on current user role
        if self.current_user:
            if self.current_user.role == 'reception':
                # Receptionist can only create doctor and patient
                allowed_roles = [
                    ('doctor', 'Doctor'),
                    ('patient', 'Patient'),
                ]
            elif self.current_user.role == 'admin':
                # Admin can create anyone
                allowed_roles = [
                    ('admin', 'Admin'),
                    ('doctor', 'Doctor'),
                    ('reception', 'Receptionist'),
                    ('patient', 'Patient'),
                ]
            else:
                # Default: all roles
                allowed_roles = [(choice[0], choice[1]) for choice in User.ROLE_CHOICES]
        else:
            # No current user: show all roles
            allowed_roles = [(choice[0], choice[1]) for choice in User.ROLE_CHOICES]

        self.fields['role'].widget.choices = allowed_roles

    def clean_username(self):
        """Validate username is unique"""
        username = self.cleaned_data.get('username', '').strip()
        
        if not username:
            raise forms.ValidationError("Username is required.")
        
        if self.current_user and username == self.current_user.username:
            raise forms.ValidationError("This is already your username.")
        
        if User.objects.filter(username__iexact=username).exists():
            raise forms.ValidationError("That username is already taken.")
        
        return username

    def clean_role(self):
        """
        Validate that receptionist cannot create receptionist or admin.
        This is a safety check in addition to restricting choices.
        """
        role = self.cleaned_data.get('role')
        
        if self.current_user and self.current_user.role == 'reception':
            if role in ['reception', 'admin']:
                raise forms.ValidationError(
                    "You don't have permission to create users with this role."
                )
        
        return role

    def save(self, commit=True):
        """Save user with hashed password"""
        user = super().save(commit=False)
        user.set_password(self.cleaned_data["password"])
        if commit:
            user.save()
        return user



# -----------------------------
# Admin helpers
# -----------------------------
from django import forms
from django.contrib.auth import get_user_model
import uuid
import re

User = get_user_model()
PHONE_RE = re.compile(r"^\d{7,15}$")


class AdminCreateUserForm(forms.ModelForm):
    """
    Admin: create any user (doctor/reception/patient/admin).
    Receptionist: can only create doctor and patient (NOT other receptionists).
    """
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={"class": "form-control", "placeholder": "Password"}),
        label="Password",
        required=True
    )
    
    class Meta:
        model = User
        fields = ["username", "email", "first_name", "last_name", "role", "phone", "address", "is_active"]
        widgets = {
            "username": forms.TextInput(attrs={"class": "form-control"}),
            "email": forms.EmailInput(attrs={"class": "form-control"}),
            "first_name": forms.TextInput(attrs={"class": "form-control"}),
            "last_name": forms.TextInput(attrs={"class": "form-control"}),
            "role": forms.Select(attrs={"class": "form-control"}),
            "phone": forms.TextInput(attrs={"class": "form-control"}),
            "address": forms.Textarea(attrs={"class": "form-control", "rows": 2}),
            "is_active": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }
    
    def __init__(self, *args, **kwargs):
        self.current_user = kwargs.pop('current_user', None)
        super().__init__(*args, **kwargs)
        
        # Restrict role choices based on who is creating the user
        if self.current_user:
            if self.current_user.role == 'admin':
                # Admin can create anyone
                role_choices = [
                    ("doctor", "Doctor"),
                    ("reception", "Receptionist"),
                    ("patient", "Patient"),
                    ("admin", "Admin"),
                ]
            elif self.current_user.role == 'reception':
                # Receptionist can only create doctor and patient (NOT reception or admin)
                role_choices = [
                    ("doctor", "Doctor"),
                    ("patient", "Patient"),
                ]
            else:
                # Others can't create users
                role_choices = []
        else:
            # Default: all roles
            role_choices = [
                ("doctor", "Doctor"),
                ("reception", "Receptionist"),
                ("patient", "Patient"),
                ("admin", "Admin"),
            ]
        
        self.fields['role'].widget.choices = role_choices
    
    def clean_username(self):
        username = self.cleaned_data.get('username', '').strip()
        if User.objects.filter(username__iexact=username).exists():
            raise forms.ValidationError("Username already exists.")
        return username
    
    def clean_role(self):
        """Ensure receptionist can't create receptionist or admin"""
        role = self.cleaned_data.get('role')
        
        if self.current_user and self.current_user.role == 'reception':
            if role in ['reception', 'admin']:
                raise forms.ValidationError("You don't have permission to create this role.")
        
        return role
    
    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data["password"])
        if commit:
            user.save()
        return user


class ReceptionistPatientCreateForm(forms.ModelForm):
    """
    Receptionist/Admin: Create new patient with full profile.
    Creates both User account and Patient medical record.
    """
    
    # User fields (personal info)
    first_name = forms.CharField(
        max_length=150,
        required=True,
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "First Name"})
    )
    last_name = forms.CharField(
        max_length=150,
        required=True,
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "Last Name"})
    )
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={"class": "form-control", "placeholder": "Email Address"})
    )
    phone = forms.CharField(
        max_length=20,
        required=True,
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "Phone Number"})
    )
    address = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"class": "form-control", "rows": 2, "placeholder": "Address"})
    )
    
    class Meta:
        model = Patient
        fields = [
            "photo",
            "date_of_birth",
            "blood_group",
            "gender",
            "emergency_contact",
            "medical_history",
        ]
        widgets = {
            "photo": forms.FileInput(attrs={"class": "form-control", "accept": "image/*"}),
            "date_of_birth": forms.DateInput(attrs={"type": "date", "class": "form-control"}),
            "blood_group": forms.Select(attrs={"class": "form-control"}),
            "gender": forms.Select(attrs={"class": "form-control"}),
            "emergency_contact": forms.TextInput(attrs={"class": "form-control", "placeholder": "Emergency Contact"}),
            "medical_history": forms.Textarea(attrs={"class": "form-control", "rows": 4, "placeholder": "Medical history..."}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Pre-populate if editing existing patient
        if self.instance and self.instance.pk and self.instance.user:
            user = self.instance.user
            self.fields['first_name'].initial = user.first_name
            self.fields['last_name'].initial = user.last_name
            self.fields['email'].initial = user.email
            self.fields['phone'].initial = user.phone
            self.fields['address'].initial = user.address
    
    def clean_email(self):
        """Validate email is unique"""
        email = self.cleaned_data.get("email", "").strip()
        if not email:
            raise forms.ValidationError("Email is required.")
        
        qs = User.objects.filter(email__iexact=email)
        if self.instance and self.instance.user:
            qs = qs.exclude(pk=self.instance.user.pk)
        
        if qs.exists():
            raise forms.ValidationError("This email is already in use.")
        return email
    
    def clean_phone(self):
        """Validate phone format"""
        phone = (self.cleaned_data.get("phone") or "").strip()
        if not phone:
            raise forms.ValidationError("Phone number is required.")
        
        normalized = re.sub(r"[ \-()]", "", phone)
        if not PHONE_RE.match(normalized):
            raise forms.ValidationError("Enter a valid phone number (7–15 digits).")
        return normalized
    
    def clean_emergency_contact(self):
        """Validate emergency contact format"""
        phone = (self.cleaned_data.get("emergency_contact") or "").strip()
        if not phone:
            return phone
        
        normalized = re.sub(r"[ \-()]", "", phone)
        if not PHONE_RE.match(normalized):
            raise forms.ValidationError("Enter a valid phone number (7–15 digits).")
        return normalized
    
    def save(self, commit=True):
        """Save both User and Patient"""
        patient = super().save(commit=False)
        
        # Get User data from form
        first_name = self.cleaned_data.get('first_name', '')
        last_name = self.cleaned_data.get('last_name', '')
        email = self.cleaned_data.get('email', '')
        phone = self.cleaned_data.get('phone', '')
        address = self.cleaned_data.get('address', '')
        
        if patient.user:
            # Update existing user
            user = patient.user
            user.first_name = first_name
            user.last_name = last_name
            user.email = email
            user.phone = phone
            user.address = address
            user.save()
        else:
            # Create new user account
            username = email.split('@')[0] if '@' in email else f"patient{uuid.uuid4().hex[:8]}"
            
            # Ensure unique username
            base_username = username
            counter = 1
            while User.objects.filter(username=username).exists():
                username = f"{base_username}{counter}"
                counter += 1
            
            # Create user with random password (they'll set it later)
            user = User.objects.create_user(
                username=username,
                email=email,
                first_name=first_name,
                last_name=last_name,
                phone=phone,
                address=address,
                role="patient",
                password=User.objects.make_random_password(length=12),
                is_active=False,  # Inactive until they activate via email
            )
            
            patient.user = user
        
        if commit:
            patient.save()
        
        return patient

