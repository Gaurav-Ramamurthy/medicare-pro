
from django.db import models
from django.conf import settings
from django.utils import timezone
from django.core.exceptions import ValidationError
from patients.models import Patient

# --------- Appointments ---------
class Appointment(models.Model):
    STATUS_CHOICES = [
        ("scheduled", "Scheduled"),
        ("completed", "Completed"),
        ("cancelled", "Cancelled"),
    ]

    patient = models.ForeignKey(
        Patient,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="appointments",
    )
    doctor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="appointments",
        limit_choices_to={"role": "doctor"},
    )

    scheduled_time = models.DateTimeField()
    reason = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="scheduled")
    created_at = models.DateTimeField(auto_now_add=True)

    @property
    def is_upcoming(self):
        """Returns True if the appointment is in the future."""
        return self.scheduled_time >= timezone.now()

    @property
    def is_past(self):
        """Returns True if the appointment is already completed/time passed."""
        return self.scheduled_time < timezone.now()

    class Meta:
        ordering = ["-scheduled_time"]
        indexes = [
            models.Index(fields=["doctor", "scheduled_time"]),
            models.Index(fields=["patient", "scheduled_time"]),
        ]
        # Uncomment to enforce unique timeslots per doctor
        # constraints = [
        #     models.UniqueConstraint(
        #         fields=["doctor", "scheduled_time"],
        #         name="uniq_doctor_timeslot",
        #     )
        # ]

    def __str__(self):
        when = (
            self.scheduled_time.strftime("%Y-%m-%d %H:%M")
            if self.scheduled_time
            else "unscheduled"
        )
        return f"{self.patient} with {self.doctor} on {when}"

    def clean(self):
        if self.scheduled_time is None:
            raise ValidationError({"scheduled_time": "Scheduled time is required."})

        aware = (
            timezone.make_aware(self.scheduled_time, timezone.get_current_timezone())
            if timezone.is_naive(self.scheduled_time)
            else self.scheduled_time
        )
        if aware <= timezone.now():
            raise ValidationError({"scheduled_time": "Scheduled time must be in the future."})

    def save(self, *args, **kwargs):
        if self.scheduled_time and timezone.is_naive(self.scheduled_time):
            self.scheduled_time = timezone.make_aware(
                self.scheduled_time, timezone.get_current_timezone()
            )
        self.full_clean()
        return super().save(*args, **kwargs)
