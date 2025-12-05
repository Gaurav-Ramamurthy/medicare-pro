from django.db import models
from django.conf import settings
from django.utils import timezone

class ActivityLog(models.Model):
    """Simple activity log used in admin dashboard for recent changes."""
    created_at = models.DateTimeField(default=timezone.now, db_index=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    verb = models.CharField(max_length=160)
    target_type = models.CharField(max_length=100, blank=True)  # e.g. 'Patient', 'Appointment'
    target_id = models.IntegerField(null=True, blank=True)
    extra = models.TextField(blank=True, default="")

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.verb} — {self.user} @ {self.created_at}"

    @classmethod
    def log(cls, user, verb, target=None, extra=""):
        instance = cls(
            user=user if hasattr(user, "pk") else None,
            verb=verb[:160],
            extra=extra or ""
        )
        if target is not None:
            instance.target_type = target.__class__.__name__
            instance.target_id = getattr(target, "pk", None)
        instance.save()
        return instance
