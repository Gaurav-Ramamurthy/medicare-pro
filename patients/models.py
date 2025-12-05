from django.db import models
from django.conf import settings


# STATUS CHOICES
STATUS_CHOICES = [
    ('pending', 'Pending'), 
    ('approved', 'Approved'), 
    ('rejected', 'Rejected')
]


class Patient(models.Model):
    """
    Patient medical profile - stores ONLY patient-specific medical data.
    Personal info (name, email, phone, address) stored in linked User model.
    """
    # Link to User (authentication & personal info)
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        null=True, 
        blank=True,
        related_name='patient'
    )
    
    # PATIENT-SPECIFIC FIELDS (medical data only)
    photo = models.ImageField(upload_to='patient_photos/', null=True, blank=True)
    date_of_birth = models.DateField(null=True, blank=True)
    blood_group = models.CharField(
        max_length=10, null=True, blank=True, choices=[
            ('A+', 'A+'), ('A-', 'A-'),
            ('B+', 'B+'), ('B-', 'B-'),
            ('AB+', 'AB+'), ('AB-', 'AB-'),
            ('O+', 'O+'), ('O-', 'O-'),
        ]
    )
    gender = models.CharField(
        max_length=10, null=True, blank=True, choices=[
            ('male', 'Male'), 
            ('female', 'Female'), 
            ('other', 'Other')
        ]
    )
    emergency_contact = models.CharField(
        max_length=15, null=True, blank=True, 
        help_text="Emergency contact phone number"
    )
    medical_history = models.TextField(
        null=True, 
        blank=True, 
        help_text="Allergies, chronic conditions, past surgeries, etc."
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        if self.user:
            return f"{self.user.first_name} {self.user.last_name}".strip() or self.user.username
        return f"Patient {self.pk}"
    
    # Properties to access User data
    @property
    def first_name(self):
        """Access first name from linked User"""
        return self.user.first_name if self.user else ""
    
    @property
    def last_name(self):
        """Access last name from linked User"""
        return self.user.last_name if self.user else ""
    
    @property
    def full_name(self):
        """Get full name from User"""
        if self.user:
            return f"{self.user.first_name} {self.user.last_name}".strip() or self.user.username
        return ""
    
    @property
    def email(self):
        """Access email from linked User"""
        return self.user.email if self.user else ""
    
    @property
    def phone(self):
        """Access phone from linked User"""
        return getattr(self.user, 'phone', '') if self.user else ""
    
    @property
    def address(self):
        """Access address from linked User"""
        return getattr(self.user, 'address', '') if self.user else ""
    
    @property
    def age(self):
        """Calculate age from date of birth"""
        if self.date_of_birth:
            from datetime import date
            today = date.today()
            return today.year - self.date_of_birth.year - (
                (today.month, today.day) < (self.date_of_birth.month, self.date_of_birth.day)
            )
        return None
    
    class Meta:
        verbose_name = "Patient"
        verbose_name_plural = "Patients"


class PatientRequest(models.Model):
    """
    Patient registration requests - pending approval by admin/receptionist.
    Creates User + Patient records upon approval.
    """
    status = models.CharField(
        max_length=20, 
        choices=STATUS_CHOICES, 
        default='pending'
    )

    # Basic info fields (same as Patient + auth fields)
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    date_of_birth = models.DateField()
    gender = models.CharField(max_length=20)
    phone = models.CharField(max_length=20)
    email = models.EmailField()
    address = models.TextField()
    blood_group = models.CharField(max_length=10, blank=True)
    emergency_contact = models.CharField(max_length=20, blank=True)
    medical_history = models.TextField(blank=True)

    # Authentication fields
    username = models.CharField(max_length=150, unique=True)
    password_hash = models.CharField(max_length=128)  # Store hashed pw temporarily

    # Patient photo field
    photo = models.ImageField(upload_to='patient_photos/', blank=True, null=True)

    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        null=True, 
        blank=True, 
        on_delete=models.SET_NULL,
        related_name='submitted_patient_requests'
    )

    def __str__(self):
        return f"{self.first_name} {self.last_name} ({self.status})"
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Patient Request'
        verbose_name_plural = 'Patient Requests'
