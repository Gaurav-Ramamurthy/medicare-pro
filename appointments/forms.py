import datetime
from django import forms
from django.utils import timezone
from django.conf import settings
from django.contrib.auth import get_user_model
from .models import Appointment
from patients.models import Patient
User = get_user_model()


# -----------------------------
# Appointment form
# -----------------------------
class AppointmentForm(forms.ModelForm):
    """
    Expose separate date and time inputs while storing a single
    datetime in Appointment.scheduled_time.
    """
    scheduled_date = forms.DateField(
        required=True,
        widget=forms.DateInput(attrs={"type": "date", "class": "input"}),
        label="Date",
    )
    scheduled_time_field = forms.TimeField(
        required=True,
        widget=forms.TimeInput(attrs={"type": "time", "class": "input"}),
        label="Time",
    )

    scheduled_time = forms.DateTimeField(required=False, widget=forms.HiddenInput())

    class Meta:
        model = Appointment
        fields = ["patient", "doctor", "reason", "status", "scheduled_time"]
        widgets = {
            "patient": forms.Select(attrs={"class": "input"}),
            "doctor": forms.Select(attrs={"class": "input"}),
            "reason": forms.Textarea(attrs={"class": "textarea", "rows": 3}),
            "status": forms.Select(attrs={"class": "select"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        if "patient" in self.fields:
            self.fields["patient"].empty_label = "Select patient"
            # Filter queryset to active patients only
            self.fields["patient"].queryset = Patient.objects.filter(
                user__isnull=False,
                user__is_active=True
            ).select_related('user')

        if "doctor" in self.fields:
            self.fields["doctor"].empty_label = "Select doctor"
            try:
                if hasattr(User, "role"):
                    self.fields["doctor"].queryset = User.objects.filter(role__iexact="doctor", is_active=True)
            except Exception:
                pass

        if self.instance and getattr(self.instance, "scheduled_time", None):
            dt = self.instance.scheduled_time
            if timezone.is_aware(dt):
                dt = timezone.localtime(dt)
            self.initial["scheduled_date"] = dt.date()
            self.initial["scheduled_time_field"] = dt.time().replace(microsecond=0)
            self.initial["scheduled_time"] = dt

    def clean(self):
        cleaned = super().clean()
        sd = cleaned.get("scheduled_date")
        st = cleaned.get("scheduled_time_field")
        doctor = cleaned.get("doctor")

        if sd is None or st is None:
            return cleaned

        combined_naive = datetime.datetime.combine(sd, st)

        if settings.USE_TZ:
            tz = timezone.get_current_timezone()
            combined = timezone.make_aware(combined_naive, tz) if timezone.is_naive(combined_naive) else combined_naive
            now = timezone.now()
        else:
            combined = combined_naive
            now = datetime.datetime.now()

        if combined <= now:
            self.add_error(None, "Scheduled time must be in the future.")
            cleaned["scheduled_time"] = combined
            try:
                self.instance.scheduled_time = combined
            except Exception:
                pass
            return cleaned

        if not doctor:
            self.add_error("doctor", "Please select a doctor.")
            cleaned["scheduled_time"] = combined
            try:
                self.instance.scheduled_time = combined
            except Exception:
                pass
            return cleaned

        window = datetime.timedelta(minutes=30)
        start, end = combined - window, combined + window

        qs = Appointment.objects.filter(
            doctor=doctor,
            status__iexact="scheduled",
            scheduled_time__range=(start, end),
        )
        if self.instance and getattr(self.instance, "pk", None):
            qs = qs.exclude(pk=self.instance.pk)

        if qs.exists():
            self.add_error(None, "Sorry — this doctor already has an appointment around that time. Please choose another slot.")
            return cleaned

        cleaned["scheduled_time"] = combined
        self._scheduled_datetime = combined
        try:
            self.instance.scheduled_time = combined
        except Exception:
            pass

        return cleaned

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.scheduled_time = getattr(self, "_scheduled_datetime", getattr(instance, "scheduled_time", None))
        if commit:
            instance.save()
            if hasattr(self, "save_m2m"):
                self.save_m2m()
        return instance