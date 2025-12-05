from django.conf import settings
from django.utils import timezone
from django.db.models import Q
from datetime import datetime, timedelta, time as _time

# --- Configurable appointment defaults ---
APPOINTMENT_SLOT_MINUTES = getattr(settings, "APPOINTMENT_SLOT_MINUTES", 30)
APPOINTMENT_WORK_START_HOUR = getattr(settings, "APPOINTMENT_WORK_START_HOUR", 9)
APPOINTMENT_WORK_END_HOUR = getattr(settings, "APPOINTMENT_WORK_END_HOUR", 17)
APPOINTMENT_WORK_DAYS = getattr(settings, "APPOINTMENT_WORK_DAYS", [0,1,2,3,4])  # Mon-Fri
APPOINTMENT_SEARCH_DAYS_AHEAD = getattr(settings, "APPOINTMENT_SEARCH_DAYS_AHEAD", 30)


def _appointment_duration_minutes(appt):
    """Return duration for an appointment in minutes."""
    duration = getattr(appt, "duration_minutes", None)
    try:
        if duration:
            return int(duration)
    except Exception:
        pass
    return int(APPOINTMENT_SLOT_MINUTES)


def _doctor_appointments_in_range(doctor, start, end, exclude_appt_id=None):
    """Return queryset of non-cancelled appointments for doctor between start/end."""
    from .models import Appointment  # Import here to avoid circular import
    qs = Appointment.objects.filter(
        doctor=doctor,
        scheduled_time__lt=end,
        scheduled_time__gte=start - timedelta(days=1)
    ).exclude(status="cancelled")
    if exclude_appt_id:
        qs = qs.exclude(pk=exclude_appt_id)
    return qs


def _slot_conflicts(doctor, slot_start, slot_end, exclude_appt_id=None):
    """Return True if any non-cancelled appointment overlaps slot."""
    nearby = _doctor_appointments_in_range(
        doctor, slot_start - timedelta(hours=1), slot_end + timedelta(hours=1), 
        exclude_appt_id=exclude_appt_id
    )
    for other in nearby:
        other_start = other.scheduled_time
        other_dur = _appointment_duration_minutes(other)
        other_end = other_start + timedelta(minutes=other_dur)
        if slot_start < other_end and other_start < slot_end:
            return True
    return False


def next_available_slot_for_doctor_exact_duration(
    doctor, duration_minutes, start_from=None, *,
    work_start_hour=APPOINTMENT_WORK_START_HOUR,
    work_end_hour=APPOINTMENT_WORK_END_HOUR,
    work_days=APPOINTMENT_WORK_DAYS,
    days_ahead=APPOINTMENT_SEARCH_DAYS_AHEAD
):
    """Find earliest available slot for exact duration without conflicts."""
    tz = timezone.get_default_timezone()
    now = timezone.localtime(timezone.now())
    cursor = timezone.localtime(start_from) if start_from else now

    if cursor.second or cursor.microsecond:
        cursor = (cursor + timedelta(minutes=1)).replace(second=0, microsecond=0)

    for day_offset in range(days_ahead + 1):
        day = (cursor + timedelta(days=day_offset)).date() if day_offset > 0 else cursor.date()
        if day.weekday() not in work_days:
            continue

        day_start_naive = datetime.combine(day, _time(hour=work_start_hour, minute=0))
        day_end_naive = datetime.combine(day, _time(hour=work_end_hour, minute=0))
        day_start = timezone.make_aware(day_start_naive, tz) if timezone.is_naive(day_start_naive) else day_start_naive
        day_end = timezone.make_aware(day_end_naive, tz) if timezone.is_naive(day_end_naive) else day_end_naive

        candidate = max(cursor, day_start) if day == cursor.date() else day_start
        if candidate.second or candidate.microsecond:
            candidate = (candidate + timedelta(minutes=1)).replace(second=0, microsecond=0)

        appts = list(_doctor_appointments_in_range(doctor, day_start, day_end))
        busy_intervals = []
        for o in appts:
            o_start = o.scheduled_time
            o_dur = _appointment_duration_minutes(o)
            o_end = o_start + timedelta(minutes=o_dur)
            if o_end <= day_start or o_start >= day_end:
                continue
            busy_intervals.append((max(o_start, day_start), min(o_end, day_end)))
        busy_intervals.sort()

        while candidate + timedelta(minutes=duration_minutes) <= day_end:
            slot_end = candidate + timedelta(minutes=duration_minutes)
            conflict = False
            for bs, be in busy_intervals:
                if candidate < be and bs < slot_end:
                    candidate = be
                    conflict = True
                    break
            if conflict:
                if candidate.second or candidate.microsecond:
                    candidate = (candidate + timedelta(minutes=1)).replace(second=0, microsecond=0)
                continue

            if not _slot_conflicts(doctor, candidate, slot_end):
                return candidate
            candidate = candidate + timedelta(minutes=1)

    return None
