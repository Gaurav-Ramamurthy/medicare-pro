
from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()

class Staff(models.Model):
    ROLE_CHOICES = [
        ("doctor", "Doctor"),
        ("receptionist", "Receptionist"),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="staff")
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)

    specialization = models.CharField(max_length=100, blank=True, null=True)
    registration_number = models.CharField(max_length=20, blank=True, null=True)
    experience_years = models.PositiveIntegerField(blank=True, null=True)
    notes = models.TextField(blank=True, null=True)

    phone = models.CharField(max_length=20, blank=True, null=True)
    address = models.TextField(blank=True, null=True)
    profile_photo = models.ImageField(upload_to="staff_photos/", blank=True, null=True)

    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.get_full_name() or self.user.username} ({self.role})"
