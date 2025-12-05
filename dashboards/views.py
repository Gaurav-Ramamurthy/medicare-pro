import json
import logging
from datetime import datetime, timedelta, time

from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.http import HttpResponseForbidden
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db.models import Count, Q
from django.utils import timezone

# App models
from patients.models import Patient
from appointments.models import Appointment
from medical.models import MedicalRecord

# Custom User model
User = get_user_model()

logger = logging.getLogger(__name__)


def get_user_role(user):
    """Get user role with multiple fallback methods."""
    if not user or not user.is_authenticated:
        return None

    # 1. Prefer explicit role attribute
    role_attr = getattr(user, "role", None)
    if role_attr:
        return role_attr.lower()

    # 2. Staff/superuser = admin
    if getattr(user, "is_superuser", False) or getattr(user, "is_staff", False):
        return "admin"

    # 3. Groups fallback
    try:
        groups = list(user.groups.values_list("name", flat=True))
        groups_lower = [g.lower() for g in groups]
        if "doctor" in groups_lower:
            return "doctor"
        if "receptionist" in groups_lower:
            return "receptionist"
    except Exception:
        pass

    return "receptionist"


def get_growth_pct_and_display(current, previous):
    """Calculate growth percentage with CSS class and icon."""
    if previous == 0:
        pct = 100.0 if current > 0 else 0.0
    else:
        pct = round(((current - previous) / previous) * 100, 1)
    
    if pct > 0:
        return f"+{pct}", "positive", "↑"
    elif pct < 0:
        return f"{pct}", "negative", "↓"
    else:
        return "0.0", "neutral", "✓"


def is_admin_user(user):
    """Check if user qualifies as admin."""
    role = get_user_role(user)
    return role == "admin" or getattr(user, "is_staff", False) or getattr(user, "is_superuser", False)


admin_required = user_passes_test(is_admin_user, login_url="login")


# =====================================
# DASHBOARD ROUTER
# =====================================
@login_required
def dashboard_router(request):
    """Single entrypoint - routes to role-specific dashboard."""
    role = get_user_role(request.user)
    if role == "admin":
        return admin_dashboard(request)
    elif role == "doctor":
        return doctor_dashboard(request)
    return reception_dashboard(request)


# =====================================
# ADMIN DASHBOARD (Full Analytics)
# =====================================
@admin_required
def admin_dashboard(request):
    """Comprehensive admin dashboard with charts and growth metrics."""
    now = timezone.now()
    today = now.date()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    today_end = now.replace(hour=23, minute=59, second=59, microsecond=999999)
    
    # Date ranges
    last_month_start = (now.replace(day=1) - timedelta(days=1)).replace(day=1)
    last_month_end = now.replace(day=1) - timedelta(days=1)
    
    # Basic totals
    appointment_count = Appointment.objects.count()
    upcoming_count = Appointment.objects.filter(status__iexact="scheduled", scheduled_time__gte=now).count()
    patient_count = Patient.objects.count()
    user_count = User.objects.filter(is_active=True).count()
    
    # Role counts
    doctor_count = User.objects.filter(role__iexact="doctor", is_active=True).count()
    receptionist_count = User.objects.filter(role__iexact="receptionist", is_active=True).count()
    admin_count = User.objects.filter(role__iexact="admin", is_active=True).count()
    
    # Today's stats
    today_appointments_count = Appointment.objects.filter(scheduled_time__range=[today_start, today_end]).count()
    completed_today = Appointment.objects.filter(
        scheduled_time__range=[today_start, today_end], status='completed'
    ).count()
    
    # Previous period comparisons
    yesterday_start = today_start - timedelta(days=1)
    yesterday_end = today_end - timedelta(days=1)
    yesterday_appointments_count = Appointment.objects.filter(
        scheduled_time__range=[yesterday_start, yesterday_end]
    ).count()
    
    prev_patient_count = Patient.objects.filter(
        created_at__range=[last_month_start, last_month_end]
    ).count()
    
    # Growth metrics
    admins_growth = get_growth_pct_and_display(admin_count, 0)  # Admin growth simplified
    doctors_growth = get_growth_pct_and_display(doctor_count, 0)
    receptionists_growth = get_growth_pct_and_display(receptionist_count, 0)
    patients_growth = get_growth_pct_and_display(patient_count, prev_patient_count)
    today_growth = get_growth_pct_and_display(today_appointments_count, yesterday_appointments_count)
    
    # Chart data
    appt_by_status = dict(Appointment.objects.values("status").annotate(count=Count("pk")))
    users_by_role = dict(User.objects.filter(is_active=True).values("role").annotate(count=Count("pk")))
    
    # Weekly appointments (current week)
    current_week_start = now - timedelta(days=now.weekday())
    current_week_start = current_week_start.replace(hour=0, minute=0, second=0, microsecond=0)
    weekly_appointments_data = []
    for i in range(7):
        day = current_week_start + timedelta(days=i)
        day_end = day + timedelta(days=1)
        count = Appointment.objects.filter(scheduled_time__range=[day, day_end]).count()
        weekly_appointments_data.append(count)
    
    # Recent items
    recent_appointments = Appointment.objects.select_related("patient", "doctor").order_by("-created_at")[:6]
    recent_patients = Patient.objects.order_by("-created_at")[:6]
    
    context = {
        'today': now,
        'now': now,
        'appointment_count': appointment_count,
        'upcoming_count': upcoming_count,
        'patient_count': patient_count,
        'user_count': user_count,
        'doctor_count': doctor_count,
        'receptionist_count': receptionist_count,
        'admin_count': admin_count,
        'today_appointments_count': today_appointments_count,
        'completed_today': completed_today,
        'admins_growth': admins_growth,
        'doctors_growth': doctors_growth,
        'receptionists_growth': receptionists_growth,
        'patients_growth': patients_growth,
        'today_growth': today_growth,
        'appt_by_status_json': json.dumps(appt_by_status),
        'users_by_role_json': json.dumps(users_by_role),
        'weekly_appointments_data': json.dumps(weekly_appointments_data),
        'recent_appointments': recent_appointments,
        'recent_patients': recent_patients,
    }
    return render(request, 'dashboards/admin_dashboard.html', context)


# =====================================
# DOCTOR DASHBOARD
# =====================================
@login_required
def doctor_dashboard(request):
    """Personal dashboard for doctors showing their appointments."""
    role = get_user_role(request.user)
    if role != "doctor":
        return HttpResponseForbidden("Access denied.")
    
    now = timezone.now()
    today = now.date()
    local_tz = timezone.get_current_timezone()
    start_of_day = timezone.make_aware(datetime.combine(today, time(0, 0)), local_tz)
    end_of_day = timezone.make_aware(datetime.combine(today, time(23, 59, 999999)), local_tz)
    
    appointments = Appointment.objects.filter(doctor=request.user)
    
    context = {
        "patient_count": Patient.objects.filter(appointments__doctor=request.user).distinct().count(),
        "appt_count": appointments.count(),
        "appts_scheduled": appointments.filter(status='scheduled').count(),
        "appts_completed": appointments.filter(status='completed').count(),
        "appts_cancelled": appointments.filter(status='cancelled').count(),
        "appts_today": appointments.filter(scheduled_time__range=(start_of_day, end_of_day)).count(),
        "appts_today_list": appointments.filter(scheduled_time__range=(start_of_day, end_of_day)).order_by("scheduled_time"),
        "appts_upcoming": appointments.filter(scheduled_time__gte=now).order_by("scheduled_time")[:12],
        "now": now,
    }
    return render(request, "dashboards/doctor_dashboard.html", context)


# =====================================
# RECEPTION DASHBOARD
# =====================================
@login_required
def reception_dashboard(request):
    """Receptionist dashboard with clinic overview."""
    now = timezone.now()
    today = now.date()
    
    # Counts
    patient_count = Patient.objects.count()
    total_appointments = Appointment.objects.count()
    todays_appointments = Appointment.objects.filter(scheduled_time__date=today).count()
    pending_appointments = Appointment.objects.filter(status="scheduled").count()
    completed_appointments = Appointment.objects.filter(status="completed").count()
    cancelled_appointments = Appointment.objects.filter(status="cancelled").count()
    
    # Growth (simplified)
    last_week = now - timedelta(days=7)
    patients_last_week = Patient.objects.filter(created_at__lte=last_week).count()
    patient_growth = round(((patient_count - patients_last_week) / patients_last_week) * 100, 1) if patients_last_week > 0 else 0
    
    context = {
        "today": now,
        "patient_count": patient_count,
        "total_appointments": total_appointments,
        "todays_appointments": todays_appointments,
        "pending_appointments": pending_appointments,
        "completed_appointments": completed_appointments,
        "cancelled_appointments": cancelled_appointments,
        "patient_growth": patient_growth,
    }
    return render(request, "dashboards/reception_dashboard.html", context)


# =====================================
# GENERAL DASHBOARD
# =====================================
@login_required
def dashboard(request):
    """Role-based appointment overview."""
    today = timezone.localdate()
    qs = Appointment.objects.filter(scheduled_time__date__gte=today).select_related("patient", "doctor")
    
    role = get_user_role(request.user)
    if role == "doctor":
        qs = qs.filter(doctor=request.user)
    elif role not in ("receptionist", "admin"):
        patient_obj = getattr(request.user, "patient", None) or Patient.objects.filter(user=request.user).first()
        qs = qs.filter(patient=patient_obj) if patient_obj else Appointment.objects.none()
    
    context = {
        "upcoming_appointments": list(qs.order_by("scheduled_time")[:10]),
        "appointment_count": qs.count(),
    }
    return render(request, "dashboards/dashboard.html", context)


# =====================================
# POST-LOGIN REDIRECT
# =====================================
@login_required
def post_login_redirect(request):
    """Redirect to role-appropriate dashboard after login."""
    role = get_user_role(request.user)
    
    if role in ("admin", "administrator"):
        return redirect('admin_dashboard')
    elif role == "doctor":
        return redirect('doctor_dashboard')
    elif role == "receptionist":
        return redirect('reception_dashboard')
    
    return redirect('dashboard')


# --- helpers ---
def is_admin(user):
    return user.is_authenticated and getattr(user, "role", "") == "admin"

def is_receptionist(user):
    return user.is_authenticated and getattr(user, "role", "") == "receptionist"