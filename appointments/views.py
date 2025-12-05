import re
from datetime import datetime, timedelta, time as dt_time

from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.http import Http404, JsonResponse, HttpResponseForbidden
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required, user_passes_test
from django.conf import settings
from django.db.models import Q, Count
from django.core.paginator import Paginator
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.db.models.functions import ExtractYear, ExtractMonth, ExtractDay, ExtractHour, ExtractMinute

# App models
from .models import Appointment, Patient
from patients.models import Patient

# Forms and utils
from .forms import AppointmentForm
from .utils import (
    APPOINTMENT_SLOT_MINUTES, APPOINTMENT_WORK_START_HOUR, 
    APPOINTMENT_WORK_END_HOUR, APPOINTMENT_WORK_DAYS, 
    APPOINTMENT_SEARCH_DAYS_AHEAD,
    _appointment_duration_minutes,
    _doctor_appointments_in_range,
    _slot_conflicts,
    next_available_slot_for_doctor_exact_duration
)

# Custom User model
User = get_user_model()

# Decorators (from core)
from core.decorators import receptionist_or_admin_required, is_admin, is_doctor, is_receptionist

# Status colors for calendar
STATUS_COLORS = {
    'scheduled': '#fbbf24',    # yellow
    'completed': '#10b981',    # green
    'cancelled': '#ef4444',    # red
}


# =====================================
# APPOINTMENT LIST (FUTURE)
# =====================================
@login_required
def appointment_list(request):
    """List future appointments with role-based filtering and search."""
    now = timezone.now()

    # Base queryset: future appointments with active patients
    qs = Appointment.objects.filter(
        scheduled_time__gte=now,
        patient__user__is_active=True
    ).select_related("patient__user", "doctor")

    # Role-based filtering
    role = getattr(request.user, "role", None)
    if role == "doctor":
        qs = qs.filter(doctor=request.user)
    elif role in ("receptionist", "admin"):
        pass  # All appointments
    else:
        # Patient view
        patient_obj = getattr(request.user, "patient", None) or Patient.objects.filter(user=request.user).first()
        if patient_obj:
            qs = qs.filter(patient=patient_obj)
        else:
            qs = Appointment.objects.none()

    # Date filters
    year = request.GET.get("year")
    month = request.GET.get("month")
    date_str = request.GET.get("date")

    if year:
        try:
            y_int = int(year)
            qs = qs.annotate(_y=ExtractYear("scheduled_time")).filter(_y=y_int)
        except ValueError:
            pass

    if month:
        try:
            m_int = int(month)
            qs = qs.annotate(_mon=ExtractMonth("scheduled_time")).filter(_mon=m_int)
        except ValueError:
            pass

    if date_str:
        d = parse_date(date_str)
        if d:
            tz = timezone.get_current_timezone()
            start = timezone.make_aware(datetime.combine(d, dt_time.min), tz)
            end = timezone.make_aware(datetime.combine(d, dt_time.max), tz)
            qs = qs.filter(scheduled_time__gte=start, scheduled_time__lte=end)

    # Search
    order = request.GET.get("order", "asc")
    q = (request.GET.get("q") or "").strip()

    if q:
        q_lower = q.lower()
        if "scheduled" in q_lower:
            qs = qs.filter(status="scheduled")
        elif "completed" in q_lower:
            qs = qs.filter(status="completed")
        elif "cancelled" in q_lower or "canceled" in q_lower:
            qs = qs.filter(status="cancelled")
        else:
            # Date parsing
            date_obj = None
            m_iso = re.search(r"^\s*(\d{4})[-/](\d{1,2})[-/](\d{1,2})\s*$", q)
            if m_iso:
                try:
                    date_obj = datetime(int(m_iso.group(1)), int(m_iso.group(2)), int(m_iso.group(3))).date()
                except ValueError:
                    pass
            elif m_eu := re.search(r"^\s*(\d{1,2})[-/](\d{1,2})[-/](\d{4})\s*$", q):
                try:
                    date_obj = datetime(int(m_eu.group(3)), int(m_eu.group(2)), int(m_eu.group(1))).date()
                except ValueError:
                    pass
            elif pd := parse_date(q):
                date_obj = pd

            if date_obj:
                tz = timezone.get_current_timezone()
                start_naive = datetime.combine(date_obj, dt_time.min)
                end_naive = datetime.combine(date_obj, dt_time.max)
                start = timezone.make_aware(start_naive, tz)
                end = timezone.make_aware(end_naive, tz)
                qs = qs.filter(scheduled_time__gte=start, scheduled_time__lte=end)
            else:
                qs = qs.filter(
                    Q(reason__icontains=q) |
                    Q(status__icontains=q) |
                    Q(patient__user__first_name__icontains=q) |
                    Q(patient__user__last_name__icontains=q) |
                    Q(doctor__username__icontains=q)
                )

    # Ordering
    if order == "asc":
        qs = qs.order_by("scheduled_time")
    else:
        qs = qs.order_by("-scheduled_time")

    # Pagination
    paginator = Paginator(qs, 25)
    page = request.GET.get("page", 1)
    page_obj = paginator.get_page(page)
    upcoming_count = qs.count()

    context = {
        "upcoming": page_obj.object_list,
        "is_paginated": page_obj.has_other_pages(),
        "page_obj": page_obj,
        "upcoming_count": upcoming_count,
        "date_str": date_str,
        "role": role,
        "request": request,
    }
    return render(request, "appointments/appointment_list.html", context)


# =====================================
# APPOINTMENT HISTORY (PAST)
# =====================================
@login_required
def appointment_history(request):
    """List past appointments with advanced search/filtering."""
    now = timezone.now()
    
    # PAST APPOINTMENTS ONLY
    qs = Appointment.objects.filter(
        scheduled_time__lt=now
    ).select_related("patient", "doctor")

    # Role-based restrictions
    role = getattr(request.user, "role", None)
    if role == "doctor":
        qs = qs.filter(doctor=request.user)
    elif role in ("receptionist", "admin"):
        pass
    else:
        patient_obj = getattr(request.user, "patient", None) or Patient.objects.filter(user=request.user).first()
        if patient_obj:
            qs = qs.filter(patient=patient_obj)
        else:
            qs = Appointment.objects.none()

    # Year/Month filters
    year = request.GET.get("year")
    month = request.GET.get("month")
    order = request.GET.get("order", "desc")

    if year:
        try:
            y_int = int(year)
            qs = qs.annotate(_y=ExtractYear("scheduled_time")).filter(_y=y_int)
        except ValueError:
            pass

    if month:
        try:
            m_int = int(month)
            qs = qs.annotate(_mon=ExtractMonth("scheduled_time")).filter(_mon=m_int)
        except ValueError:
            pass

    # Search handling
    q = (request.GET.get("q") or "").strip()
    if q:
        q_lower = q.lower()
        
        # Status keywords
        if "completed" in q_lower:
            qs = qs.filter(status="completed")
        elif "scheduled" in q_lower:
            qs = qs.filter(status="scheduled")
        elif "cancelled" in q_lower or "canceled" in q_lower:
            qs = qs.filter(status="cancelled")
        else:
            # Date/Time/Number parsing
            date_obj = None
            m_iso = re.search(r"^\s*(\d{4})[-/](\d{1,2})[-/](\d{1,2})\s*$", q)
            if m_iso:
                try:
                    date_obj = datetime(int(m_iso.group(1)), int(m_iso.group(2)), int(m_iso.group(3))).date()
                except ValueError:
                    pass
            elif m_eu := re.search(r"^\s*(\d{1,2})[-/](\d{1,2})[-/](\d{4})\s*$", q):
                try:
                    date_obj = datetime(int(m_eu.group(3)), int(m_eu.group(2)), int(m_eu.group(1))).date()
                except ValueError:
                    pass
            elif pd := parse_date(q):
                date_obj = pd

            if date_obj:
                tz = timezone.get_current_timezone()
                start = timezone.make_aware(datetime.combine(date_obj, dt_time.min), tz)
                end = timezone.make_aware(datetime.combine(date_obj, dt_time.max), tz)
                qs = qs.filter(scheduled_time__gte=start, scheduled_time__lte=end)
            else:
                # Time parsing hh:mm
                tm = re.search(r"^\s*(\d{1,2}):(\d{2})(?:\s*(am|pm))?\s*$", q_lower)
                if tm:
                    try:
                        hour = int(tm.group(1))
                        minute = int(tm.group(2))
                        ampm = tm.group(3)
                        if ampm:
                            if ampm == "pm" and hour < 12:
                                hour += 12
                            if ampm == "am" and hour == 12:
                                hour = 0
                        qs = qs.annotate(_h=ExtractHour("scheduled_time"), _m=ExtractMinute("scheduled_time")).filter(_h=hour, _m=minute)
                    except ValueError:
                        qs = qs.filter(
                            Q(patient__user__first_name__icontains=q) |
                            Q(patient__user__last_name__icontains=q) |
                            Q(doctor__first_name__icontains=q) |
                            Q(doctor__last_name__icontains=q) |
                            Q(status__icontains=q)
                        )
                else:
                    # Fallback text search
                    qs = qs.filter(
                        Q(patient__user__first_name__icontains=q) |
                        Q(patient__user__last_name__icontains=q) |
                        Q(patient__user__email__icontains=q) |
                        Q(doctor__first_name__icontains=q) |
                        Q(doctor__last_name__icontains=q) |
                        Q(status__icontains=q)
                    )

    # Ordering
    if order == "asc":
        qs = qs.order_by("scheduled_time")
    else:
        qs = qs.order_by("-scheduled_time")

    # Years dropdown
    years = []
    try:
        for d in Appointment.objects.filter(scheduled_time__lt=now).dates("scheduled_time", "year"):
            if d and hasattr(d, "year"):
                years.append(d.year)
    except Exception:
        years = [timezone.localdate().year]
    years = sorted(set(years), reverse=True)

    # Pagination
    paginator = Paginator(qs, 25)
    page = request.GET.get("page", 1)
    page_obj = paginator.get_page(page)

    context = {
        "history": page_obj.object_list,
        "is_paginated": page_obj.has_other_pages(),
        "page_obj": page_obj,
        "available_years": years,
    }
    return render(request, "appointments/appointment_history.html", context)


# =====================================
# CREATE/EDIT APPOINTMENT
# =====================================
@receptionist_or_admin_required
def appointment_create(request):
    """Create new appointment (receptionist/admin only)."""
    patients = Patient.objects.filter(user__isnull=False, user__is_active=True).select_related('user')
    doctors = User.objects.filter(role="doctor", is_active=True)

    initial = {}
    date_q = request.GET.get("date")
    if date_q:
        try:
            parsed = datetime.strptime(date_q, "%Y-%m-%d").date()
            initial["scheduled_date"] = parsed
        except ValueError:
            pass

    if request.method == "POST":
        form = AppointmentForm(request.POST)
        # Parse scheduled_time from split fields
        try:
            sd_raw = request.POST.get("scheduled_date", "")
            st_raw = request.POST.get("scheduled_time_field", "")
            if sd_raw and st_raw:
                sd = datetime.strptime(sd_raw, "%Y-%m-%d").date()
                try:
                    st = datetime.strptime(st_raw, "%H:%M:%S").time()
                except ValueError:
                    st = datetime.strptime(st_raw, "%H:%M").time()
                
                combined_naive = datetime.combine(sd, st)
                tz = timezone.get_current_timezone()
                combined = timezone.make_aware(combined_naive, tz)
                form.instance.scheduled_time = combined
        except ValueError:
            pass

        if form.is_valid():
            appt = form.save()
            messages.success(request, "Appointment created successfully!")
            return redirect("appointment_list")
        else:
            messages.error(request, "Please fix the errors below.")
    else:
        form = AppointmentForm(initial=initial)

    context = {
        "form": form,
        "patients": patients,
        "doctors": doctors,
        "title": "Create Appointment",
    }
    return render(request, "appointments/appointment_form.html", context)


@receptionist_or_admin_required
def appointment_edit(request, pk):
    """Edit existing appointment."""
    appt = get_object_or_404(Appointment, pk=pk)
    patients = Patient.objects.all()
    doctors = User.objects.filter(role__iexact="doctor")

    if request.method == "POST":
        form = AppointmentForm(request.POST, instance=appt)
        if form.is_valid():
            try:
                appt = form.save()
                patient_name = f"{appt.patient.first_name or ''} {appt.patient.last_name or ''}".strip() or "patient"
                messages.success(request, f"Appointment for {patient_name} updated.")
                return redirect(f"{reverse('appointment_list')}?edit_success=true&patient_name={patient_name}")
            except Exception as exc:
                messages.error(request, f"Could not save: {str(exc)}")
        else:
            for err in form.non_field_errors():
                messages.error(request, err)
    else:
        form = AppointmentForm(instance=appt)

    context = {
        "form": form,
        "editing": True,
        "appointment": appt,
        "patients": patients,
        "doctors": doctors,
        "title": "Edit Appointment",
        "now": timezone.now(),
    }
    return render(request, "appointments/appointment_form.html", context)


# =====================================
# DELETE/CANCEL APPOINTMENT
# =====================================
@receptionist_or_admin_required
def appointment_delete(request, pk):
    """Soft-delete appointment (set status='cancelled')."""
    appt = get_object_or_404(Appointment, pk=pk)

    if request.method == "POST":
        Appointment.objects.filter(pk=appt.pk).update(status="cancelled")
        messages.success(request, "Appointment cancelled (kept for history).")
        return redirect("appointment_list")

    return render(request, "appointments/appointment_confirm_delete.html", {"appointment": appt})


# =====================================
# RESCHEDULE APPOINTMENT
# =====================================
@login_required
def appointment_reschedule(request, pk):
    """Instantly reschedule to next available slot."""
    appt = get_object_or_404(Appointment.objects.select_related("doctor", "patient"), pk=pk)

    # Permissions
    role = getattr(request.user, "role", None)
    if role == "doctor" and appt.doctor != request.user:
        messages.error(request, "Not authorized to reschedule this appointment.")
        return redirect("appointment_history")
    if role not in ("admin", "receptionist", "doctor"):
        patient_obj = getattr(request.user, "patient", None)
        if not patient_obj or patient_obj != appt.patient:
            messages.error(request, "Not authorized to reschedule this appointment.")
            return redirect("appointment_history")

    duration_min = _appointment_duration_minutes(appt)
    start_from = timezone.now() + timedelta(minutes=1)
    candidate = next_available_slot_for_doctor_exact_duration(
        appt.doctor, duration_min, start_from=start_from
    )

    if not candidate:
        messages.error(request, "No available slots found.")
        return redirect("appointment_history")

    appt.scheduled_time = candidate
    appt.status = "scheduled"
    appt.save()
    messages.success(request, f"Rescheduled to {timezone.localtime(candidate).strftime('%Y-%m-%d %I:%M %p')}.")
    return redirect("appointment_history")


# =====================================
# DAILY VIEW
# =====================================
@login_required
def daily_appointments_view(request):
    """Show appointments for specific date."""
    date_str = request.GET.get("date")
    if date_str:
        d = parse_date(date_str)
        if d is None:
            raise Http404("Invalid date")
    else:
        d = timezone.localdate()

    tz = timezone.get_current_timezone()
    start = timezone.make_aware(datetime.combine(d, dt_time.min), tz)
    end = timezone.make_aware(datetime.combine(d, dt_time.max), tz)

    appointments = Appointment.objects.filter(
        scheduled_time__gte=start, scheduled_time__lte=end
    ).select_related("patient", "doctor").order_by("scheduled_time")

    context = {"appointments": appointments, "date": d, "now": timezone.now()}
    return render(request, "appointments/daily_appointments.html", context)


# =====================================
# APPOINTMENT DETAIL
# =====================================
@login_required
def appointment_detail(request, pk):
    """Appointment detail view."""
    appt = get_object_or_404(Appointment, pk=pk)
    patient = getattr(appt, 'patient', None)
    return render(request, "patients/detail.html", {"appointment": appt, "patient": patient})


# =====================================
# CALENDAR VIEWS
# =====================================
@login_required
def calendar_page(request):
    """Calendar page with upcoming appointments list."""
    now = timezone.now()
    user = request.user
    
    if hasattr(user, "role") and user.role == "patient":
        try:
            patient_instance = user.patient
            upcoming_qs = Appointment.objects.filter(
                patient=patient_instance, scheduled_time__gte=now
            ).order_by("scheduled_time")[:30]
        except Exception:
            upcoming_qs = Appointment.objects.none()
    else:
        upcoming_qs = Appointment.objects.filter(scheduled_time__gte=now).order_by("scheduled_time")[:30]

    upcoming = []
    for a in upcoming_qs:
        title = f"{a.patient.first_name} {a.patient.last_name}".strip() if a.patient else "Appointment"
        dt_obj = a.scheduled_time
        status = getattr(a, "status", "")
        color = STATUS_COLORS.get(status.lower(), "#64748b")
        
        upcoming.append({
            "id": a.pk,
            "title": title or "Appointment",
            "dt": dt_obj,
            "status": status,
            "color": color,
        })

    context = {"upcoming": upcoming}
    return render(request, "appointments/calendar.html", context)


@login_required
def calendar_events(request):
    """JSON endpoint for FullCalendar events."""
    user = request.user
    if hasattr(user, "role") and user.role == "patient":
        try:
            patient_instance = user.patient
            qs = Appointment.objects.filter(patient=patient_instance).order_by("scheduled_time")
        except Exception:
            qs = Appointment.objects.none()
    else:
        qs = Appointment.objects.select_related("patient").order_by("scheduled_time")

    events = []
    for a in qs:
        start = a.scheduled_time.isoformat() if hasattr(a, "scheduled_time") else None
        if not start:
            continue

        title = f"{a.patient.first_name} {a.patient.last_name}" if a.patient else "Appointment"
        status = getattr(a, "status", "")
        color = STATUS_COLORS.get(status.lower(), "#64748b")

        events.append({
            "id": a.pk,
            "title": title,
            "start": start,
            "allDay": False,
            "color": color,
        })
    
    return JsonResponse(events, safe=False)


# =====================================
# UTILITY FUNCTIONS
# =====================================
def _doctor_appointments_in_range(doctor, start, end, exclude_appt_id=None):
    """Get doctor's appointments in time range."""
    qs = Appointment.objects.filter(
        doctor=doctor,
        scheduled_time__lt=end,
        scheduled_time__gte=start - timedelta(days=1)
    ).exclude(status="cancelled")
    if exclude_appt_id:
        qs = qs.exclude(pk=exclude_appt_id)
    return qs


def _slot_conflicts(doctor, slot_start, slot_end, exclude_appt_id=None):
    """Check if slot conflicts with existing appointments."""
    nearby = _doctor_appointments_in_range(doctor, slot_start - timedelta(hours=1), slot_end + timedelta(hours=1), exclude_appt_id)
    for other in nearby:
        other_start = other.scheduled_time
        other_dur = _appointment_duration_minutes(other)
        other_end = other_start + timedelta(minutes=other_dur)
        if slot_start < other_end and other_start < slot_end:
            return True
    return False
