
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone
from django.contrib.auth.models import AbstractUser
from datetime import timedelta




# --------- Misc ---------
class TestTime(models.Model):
    """Small model for testing timestamps."""
    message = models.CharField(max_length=200)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.message} at {self.created_at}"

# --------- Custom User Model ---------
from django.db import models
from django.contrib.auth.models import AbstractUser

class User(AbstractUser):
    """
    Custom User model with role choices and additional fields.
    Make sure in settings.py: AUTH_USER_MODEL = 'core.User'
    """
    ROLE_CHOICES = (
        ("admin", "Admin"),
        ("doctor", "Doctor"),
        ("reception", "Receptionist"),
        ("patient", "Patient"),
    )
    
    SPECIALIST_CHOICES = (
        ("general", "General Physician"),
        ("cardiology", "Cardiologist"),
        ("dermatology", "Dermatologist"),
        ("pediatrics", "Pediatrician"),
        ("orthopedics", "Orthopedic Surgeon"),
        ("neurology", "Neurologist"),
        ("gynecology", "Gynecologist"),
        ("psychiatry", "Psychiatrist"),
        ("ophthalmology", "Ophthalmologist"),
        ("ent", "ENT Specialist"),
        ("dentistry", "Dentist"),
        ("radiology", "Radiologist"),
        ("anesthesiology", "Anesthesiologist"),
        ("pathology", "Pathologist"),
        ("surgery", "General Surgeon"),
        ("emergency", "Emergency Medicine"),
        ("oncology", "Oncologist"),
        ("urology", "Urologist"),
        ("nephrology", "Nephrologist"),
        ("gastroenterology", "Gastroenterologist"),
        ("other", "Other"),
    )
    
    # Existing field
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default="patient")
    
    # NEW FIELDS
    # Contact information
    phone = models.CharField(max_length=20, blank=True, null=True, help_text="Contact phone number")
    address = models.TextField(blank=True, null=True, help_text="Full address")
    
    # Profile details
    bio = models.TextField(blank=True, null=True, help_text="Short biography or description")
    profile_pic = models.ImageField(upload_to='profile_pics/', blank=True, null=True, help_text="Profile picture")
    
    # Doctor-specific fields
    specialist = models.CharField(
        max_length=50, 
        choices=SPECIALIST_CHOICES, 
        blank=True, 
        null=True, 
        help_text="Medical specialty (for doctors only)"
    )
    license_number = models.CharField(
        max_length=50, 
        blank=True, 
        null=True, 
        help_text="Medical license number (for doctors only)"
    )
    years_experience = models.PositiveIntegerField(
        blank=True, 
        null=True, 
        help_text="Years of medical experience (for doctors only)"
    )

    def __str__(self):
        full = f"{self.first_name} {self.last_name}".strip()
        return full if full else self.username

    @property
    def is_doctor(self):
        return self.role == "doctor"

    @property
    def is_reception(self):
        return self.role == "reception"
    
    @property
    def is_patient(self):
        return self.role == "patient"
    
    @property
    def is_admin(self):
        return self.role == "admin"
    
    def get_full_title(self):
        """Returns 'Dr. John Doe - Cardiologist' for doctors"""
        if self.is_doctor:
            name = f"Dr. {self.first_name} {self.last_name}".strip()
            if self.specialist:
                name += f" - {self.get_specialist_display()}"
            return name
        return str(self)
    
    class Meta:
        verbose_name = "User"
        verbose_name_plural = "Users"

from django.conf import settings
from django.db import models
from django.utils import timezone
from datetime import timedelta

# --------- OTPs ---------
class PasswordOTP(models.Model):
    """
    One-time password tokens that can be used for BOTH:
    - auth.User
    - Patient

    Either 'user' or 'patient' will be set.
    """
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="password_otps"
    )
    patient = models.ForeignKey(
        "patients.Patient",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="password_otps"
    )
    code = models.CharField(max_length=6)  # 6-digit OTP

    created_at = models.DateTimeField(auto_now_add=True)
    is_used = models.BooleanField(default=False)
    attempts = models.PositiveSmallIntegerField(default=0)

    class Meta:
        indexes = [
            models.Index(fields=["user", "code"]),
            models.Index(fields=["patient", "code"]),
            models.Index(fields=["created_at"]),
        ]

    def __str__(self):
        target = (
            self.user.email
            if self.user else (
                self.patient.email if self.patient else "unknown"
            )
        )
        return f"PasswordOTP<{target}> {self.code} @ {self.created_at:%Y-%m-%d %H:%M}"

    def is_expired(self, minutes: int = 15) -> bool:
        return timezone.now() > (self.created_at + timedelta(minutes=minutes))

    def mark_used(self):
        self.is_used = True
        self.save(update_fields=["is_used"])


from django.db import models

class ContactQuery(models.Model):
    STATUS_CHOICES = [
        ('new', 'New'),
        ('replied', 'Replied'),
    ]

    full_name = models.CharField(max_length=255)
    email = models.EmailField()
    phone = models.CharField(max_length=20, blank=True)
    message = models.TextField()
    reply_message = models.TextField(blank=True, null=True)  # stores last reply text
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='new')

    def __str__(self):
        return f"{self.full_name} - {self.email}"

    class Meta:
        ordering = ['-created_at']






