

import json
import logging
from datetime import datetime, timedelta, time

from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.http import HttpResponseForbidden
from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db.models import Count, Q
from django.utils import timezone

from core.decorators import admin_required
from core.models import User
from patients.models import Patient
from appointments.models import Appointment
from medical.models import MedicalRecord


logger = logging.getLogger(__name__)

from django.contrib.auth import get_user_model
User = get_user_model()


# ---------- helper: role detection ----------
def get_user_role(user):
    """
    Return a simple role string for the user.
    Priority:
      1) user.role attribute (if present and non-empty)
      2) staff/superuser -> 'admin'
      3) group names (Doctor/Receptionist) fallback
      4) default 'receptionist' (safe default)
    Adjust this function to your project's role storage if needed.
    """
    if not user or not user.is_authenticated:
        return None

    # prefer explicit attribute
    role_attr = getattr(user, "role", None)
    if role_attr:
        return role_attr.lower()

    # staff/superuser treated as admin
    if getattr(user, "is_superuser", False) or getattr(user, "is_staff", False):
        return "admin"

    # try groups (if you use Group names)
    try:
        groups = list(user.groups.values_list("name", flat=True))
        groups_lower = [g.lower() for g in groups]
        if "doctor" in groups_lower:
            return "doctor"
        if "receptionist" in groups_lower:
            return "receptionist"
    except Exception:
        # ignore if groups unavailable
        pass

    # default fallback
    return "receptionist"










# ---------- Admin dashboard ----------
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q
from django.utils import timezone
from datetime import datetime, timedelta
import json

from core.decorators import admin_required
import logging

logger = logging.getLogger(__name__)

def get_growth_pct_and_display(current, previous):
    """Calculate growth percentage and return formatted string, CSS class, and icon."""
    if previous == 0:
        pct = 100.0 if current > 0 else 0.0
    else:
        pct = round(((current - previous) / previous) * 100, 1)
    
    if pct > 0:
        growth_class = "positive"
        growth_icon = "↑"
        growth_str = f"+{pct}"
    elif pct < 0:
        growth_class = "negative"
        growth_icon = "↓"
        growth_str = f"{pct}"
    else:
        growth_class = "neutral"
        growth_icon = "✓"
        growth_str = "0.0"
    
    return growth_str, growth_class, growth_icon

@admin_required
def admin_dashboard(request):
    """
    Admin dashboard with real-time stats and charts.
    Only accessible to admin/staff/superuser.
    """
    now = timezone.now()
    today = now.date()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    today_end = now.replace(hour=23, minute=59, second=59, microsecond=999999)
    
    # Calculate date ranges
    last_month_start = (now.replace(day=1) - timedelta(days=1)).replace(day=1)
    last_month_end = now.replace(day=1) - timedelta(days=1)
    
    # ==========================================
    # BASIC TOTALS
    # ==========================================
    
    appointment_count = Appointment.objects.count()
    upcoming_count = Appointment.objects.filter(
        status__iexact="scheduled", 
        scheduled_time__gte=now
    ).count()
    
    patient_count = Patient.objects.count()
    
    user_count = User.objects.filter(is_active=True).count()
    
    # Role-specific counts (with fallback)
    try:
        doctor_count = User.objects.filter(role__iexact="doctor", is_active=True).count()
    except Exception:
        doctor_count = User.objects.filter(is_staff=True, is_active=True).count()
    
    try:
        receptionist_count = User.objects.filter(role__iexact="receptionist", is_active=True).count()
    except Exception:
        receptionist_count = 0
    
    try:
        admin_count = User.objects.filter(role__iexact="admin", is_active=True).count()
    except Exception:
        admin_count = User.objects.filter(is_superuser=True).count()
    
    # Today's appointments
    today_appointments = Appointment.objects.filter(
        scheduled_time__range=[today_start, today_end]
    )
    today_appointments_count = today_appointments.count()
    completed_today = today_appointments.filter(status='completed').count()
    
    # ==========================================
    # GROWTH PERCENTAGES - PREVIOUS PERIOD COUNTS
    # ==========================================
    
    # Previous month counts for roles (using date_joined for User model)
    prev_admin_count = User.objects.filter(
        role__iexact="admin", is_active=True,
        date_joined__range=[last_month_start, last_month_end]
    ).count()
    
    prev_doctor_count = User.objects.filter(
        role__iexact="doctor", is_active=True,
        date_joined__range=[last_month_start, last_month_end]
    ).count()
    
    prev_receptionist_count = User.objects.filter(
        role__iexact="receptionist", is_active=True,
        date_joined__range=[last_month_start, last_month_end]
    ).count()
    
    prev_patient_count = Patient.objects.filter(
        created_at__range=[last_month_start, last_month_end]
    ).count()
    
    # Yesterday's appointments
    yesterday_start = today_start - timedelta(days=1)
    yesterday_end = today_end - timedelta(days=1)
    yesterday_appointments_count = Appointment.objects.filter(
        scheduled_time__range=[yesterday_start, yesterday_end]
    ).count()
    
    # Appointments this month vs last month (existing logic)
    appointments_this_month = Appointment.objects.filter(
        created_at__gte=now.replace(day=1)
    ).count()
    
    appointments_last_month = Appointment.objects.filter(
        created_at__range=[last_month_start, last_month_end]
    ).count()
    
    # Calculate ALL growth percentages with classes and icons
    admins_growth_pct, admins_growth_class, admins_growth_icon = get_growth_pct_and_display(admin_count, prev_admin_count)
    doctors_growth_pct, doctors_growth_class, doctors_growth_icon = get_growth_pct_and_display(doctor_count, prev_doctor_count)
    receptionists_growth_pct, receptionists_growth_class, receptionists_growth_icon = get_growth_pct_and_display(receptionist_count, prev_receptionist_count)
    patients_growth_pct, patients_growth_class, patients_growth_icon = get_growth_pct_and_display(patient_count, prev_patient_count)
    appointments_growth_pct, appointments_growth_class, appointments_growth_icon = get_growth_pct_and_display(appointments_this_month, appointments_last_month)
    today_appointments_growth_pct, today_growth_class, today_growth_icon = get_growth_pct_and_display(today_appointments_count, yesterday_appointments_count)
    
    # ==========================================
    # APPOINTMENTS BY STATUS (for pie chart)
    # ==========================================
    
    appt_status_qs = Appointment.objects.values("status").annotate(count=Count("pk"))
    appt_by_status = {(item["status"] or "unknown"): item["count"] for item in appt_status_qs}
    
    # ==========================================
    # USERS BY ROLE (for doughnut chart)
    # ==========================================
    
    users_by_role_qs = User.objects.filter(is_active=True).values("role").annotate(count=Count("pk"))
    users_by_role = {(item["role"] or "unspecified"): item["count"] for item in users_by_role_qs}
    
    # ==========================================
    # MONTHLY APPOINTMENT STATUS DATA (for yearly stacked bar chart)
    # ==========================================
    
    year = now.year
    monthly_stats = []
    
    for month in range(1, 13):
        month_start = datetime(year, month, 1, tzinfo=timezone.get_current_timezone())
        if month == 12:
            month_end = datetime(year + 1, 1, 1, tzinfo=timezone.get_current_timezone())
        else:
            month_end = datetime(year, month + 1, 1, tzinfo=timezone.get_current_timezone())
        
        scheduled = Appointment.objects.filter(
            scheduled_time__range=[month_start, month_end],
            status='scheduled'
        ).count()
        
        completed = Appointment.objects.filter(
            scheduled_time__range=[month_start, month_end],
            status='completed'
        ).count()
        
        cancelled = Appointment.objects.filter(
            scheduled_time__range=[month_start, month_end],
            status='cancelled'
        ).count()
        
        monthly_stats.append({
            'month': month,
            'scheduled': scheduled,
            'completed': completed,
            'cancelled': cancelled
        })
    
    # ==========================================
    # PATIENT GROWTH DATA (last 4 weeks cumulative)
    # ==========================================
    
    patient_growth_data = []
    for i in range(4, 0, -1):
        week_start = now - timedelta(weeks=i)
        week_end = now - timedelta(weeks=i-1)
        
        count = Patient.objects.filter(
            created_at__range=[week_start, week_end]
        ).count()
        
        patient_growth_data.append(count)
    
    # Calculate cumulative growth
    cumulative_patients = []
    total = 0
    for count in patient_growth_data:
        total += count
        cumulative_patients.append(total)
    
    # ==========================================
    # WEEKLY APPOINTMENTS DATA
    # Show whichever week has more data (current or next)
    # ==========================================
    
    current_week_start = now - timedelta(days=now.weekday())
    current_week_start = current_week_start.replace(hour=0, minute=0, second=0, microsecond=0)
    
    current_week_data = []
    for i in range(7):
        day = current_week_start + timedelta(days=i)
        day_end = day + timedelta(days=1)
        count = Appointment.objects.filter(scheduled_time__range=[day, day_end]).count()
        current_week_data.append(count)
    
    next_week_start = current_week_start + timedelta(days=7)
    next_week_data = []
    for i in range(7):
        day = next_week_start + timedelta(days=i)
        day_end = day + timedelta(days=1)
        count = Appointment.objects.filter(scheduled_time__range=[day, day_end]).count()
        next_week_data.append(count)
    
    if sum(next_week_data) > sum(current_week_data):
        weekly_appointments_data = next_week_data
        week_label = f"Next Week ({next_week_start.strftime('%b %d')} - {(next_week_start + timedelta(days=6)).strftime('%b %d')})"
    else:
        weekly_appointments_data = current_week_data
        week_label = f"This Week ({current_week_start.strftime('%b %d')} - {(current_week_start + timedelta(days=6)).strftime('%b %d')})"
    
    logger.info(f"Showing {week_label}: {weekly_appointments_data}")
    
    # ==========================================
    # LAST 14 DAYS TIME-SERIES
    # ==========================================
    
    days = 14
    start_date = today - timedelta(days=days - 1)
    labels = []
    patients_series = []
    appts_series = []
    
    for i in range(days):
        d = start_date + timedelta(days=i)
        labels.append(d.strftime("%d %b"))
        patients_series.append(Patient.objects.filter(created_at__date=d).count())
        appts_series.append(Appointment.objects.filter(scheduled_time__date=d).count())
    
    # ==========================================
    # RECENT ITEMS
    # ==========================================
    
    recent_appointments = Appointment.objects.select_related(
        "patient", "doctor"
    ).order_by("-created_at")[:6]
    
    recent_patients = Patient.objects.order_by("-created_at")[:6]
    
    # ==========================================
    # TOP DOCTORS BY APPOINTMENT COUNT
    # ==========================================
    
    appt_per_doc_qs = Appointment.objects.values(
        "doctor__id", "doctor__first_name", "doctor__last_name"
    ).annotate(count=Count("pk")).order_by("-count")[:8]
    
    appt_per_doctor = [
        {
            "id": item.get("doctor__id"),
            "name": f"{item.get('doctor__first_name') or ''} {item.get('doctor__last_name') or ''}".strip() or "Doctor",
            "count": item.get("count", 0),
        }
        for item in appt_per_doc_qs
    ]
    
    # ==========================================
    # ADDITIONAL STATS
    # ==========================================
    
    total_staff = User.objects.filter(
        is_active=True, 
        role__in=['admin', 'doctor', 'receptionist']
    ).count()
    
    try:
        total_records = MedicalRecord.objects.count()
        recent_records = MedicalRecord.objects.filter(
            created_at__gte=now - timedelta(days=7)
        ).count()
    except:
        total_records = 0
        recent_records = 0
    
    pending_appointments = Appointment.objects.filter(status='scheduled').count()
    
    # ==========================================
    # CONTEXT DATA - ALL GROWTH VARIABLES INCLUDED
    # ==========================================
    
    context = {
        # Current date/time
        'today': now,
        'now': now,
        'week_label': week_label,
        'as_of': now.strftime("%Y-%m-%d %H:%M %Z") or now.isoformat(),
        
        # Basic totals
        'appointment_count': appointment_count,
        'upcoming_count': upcoming_count,
        'patient_count': patient_count,
        'user_count': user_count,
        
        # Role counts
        'doctor_count': doctor_count,
        'receptionist_count': receptionist_count,
        'admin_count': admin_count,
        'total_staff': total_staff,
        
        # Stat cards
        'total_admins': admin_count,
        'active_doctors': doctor_count,
        'total_receptionists': receptionist_count,
        'total_patients': patient_count,
        'total_appointments': appointment_count,
        'today_appointments_count': today_appointments_count,
        'completed_today': completed_today,
        'pending_appointments': pending_appointments,
        
        # REAL-TIME GROWTH PERCENTAGES WITH CLASSES & ICONS ✅
        'admins_growth_pct': admins_growth_pct,
        'admins_growth_class': admins_growth_class,
        'admins_growth_icon': admins_growth_icon,
        
        'doctors_growth_pct': doctors_growth_pct,
        'doctors_growth_class': doctors_growth_class,
        'doctors_growth_icon': doctors_growth_icon,
        
        'receptionists_growth_pct': receptionists_growth_pct,
        'receptionists_growth_class': receptionists_growth_class,
        'receptionists_growth_icon': receptionists_growth_icon,
        
        'patients_growth_pct': patients_growth_pct,
        'patients_growth_class': patients_growth_class,
        'patients_growth_icon': patients_growth_icon,
        
        'appointments_growth_pct': appointments_growth_pct,
        'appointments_growth_class': appointments_growth_class,
        'appointments_growth_icon': appointments_growth_icon,
        
        'today_appointments_growth_pct': today_appointments_growth_pct,
        'today_growth_class': today_growth_class,
        'today_growth_icon': today_growth_icon,
        
        # Medical records
        'total_records': total_records,
        'recent_records': recent_records,
        
        # Chart data (JSON for JavaScript)
        'patient_growth_data': json.dumps(cumulative_patients),
        'weekly_appointments_data': json.dumps(weekly_appointments_data),
        'monthly_stats': json.dumps(monthly_stats),
        'appt_by_status_json': json.dumps(appt_by_status),
        'users_by_role_json': json.dumps(users_by_role),
        'labels_json': json.dumps(labels),
        'patients_series_json': json.dumps(patients_series),
        'appts_series_json': json.dumps(appts_series),
        
        # Recent items
        'recent_appointments': recent_appointments,
        'recent_patients': recent_patients,
        'upcoming_appointments': recent_appointments[:5],
        
        # Top doctors
        'appt_per_doctor': appt_per_doctor,
    }
    
    # DEBUG: Print growth data
    print("=" * 50)
    print("DEBUG: Dashboard Growth Data")
    print("=" * 50)
    print(f"Admins: {admin_count} vs {prev_admin_count} = {admins_growth_pct}")
    print(f"Doctors: {doctor_count} vs {prev_doctor_count} = {doctors_growth_pct}")
    print(f"Receptionists: {receptionist_count} vs {prev_receptionist_count} = {receptionists_growth_pct}")
    print(f"Patients: {patient_count} vs {prev_patient_count} = {patients_growth_pct}")
    print(f"Today Appts: {today_appointments_count} vs {yesterday_appointments_count} = {today_appointments_growth_pct}")
    print("=" * 50)
    
    return render(request, 'dashboards/admin_dashboard.html', context)


# ---------- Doctor dashboard ----------

from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.http import HttpResponseForbidden
from django.shortcuts import render

from django.utils import timezone
from datetime import time

@login_required
def doctor_dashboard(request):

    print("Dashboard requested by user:", request.user.username, request.user.id)

    role = get_user_role(request.user)
    if role != "doctor" and not (request.user.is_staff or request.user.is_superuser):
        return HttpResponseForbidden("You do not have permission to view this page.")

    now = timezone.now()
    today = now.date()


    local_tz = timezone.get_current_timezone()
    # Then use:
    start_of_day = timezone.make_aware(datetime.combine(today, time(0, 0, 0)), local_tz)
    end_of_day = timezone.make_aware(datetime.combine(today, time(23, 59, 59, 999999)), local_tz)


    appointments = Appointment.objects.filter(doctor=request.user)

    patient_count = Patient.objects.filter(appointments__doctor=request.user).distinct().count()
    appt_count = appointments.count()
    appts_scheduled = appointments.filter(status='scheduled').count()
    appts_completed = appointments.filter(status='completed').count()
    appts_cancelled = appointments.filter(status='cancelled').count()

    appts_today_qs = appointments.filter(
        scheduled_time__range=(start_of_day, end_of_day)
    ).order_by("scheduled_time")
    appts_today = appts_today_qs.count()

    print(f"Today's date: {today}")
    print(f"Appointments today:", list(appts_today_qs))
    print(f"Count: {appts_today}")

    appts_upcoming = appointments.filter(scheduled_time__gte=now).order_by("scheduled_time")[:12]

    context = {
        "patient_count": patient_count,
        "appt_count": appt_count,
        "appts_scheduled": appts_scheduled,
        "appts_completed": appts_completed,
        "appts_cancelled": appts_cancelled,
        "appts_today": appts_today,
        "appts_today_list": appts_today_qs,
        "appts_upcoming": appts_upcoming,
        "now": now,
    }
    return render(request, "dashboards/doctor_dashboard.html", context)



# ---------- admin_required decorator ----------
def is_admin_user(user):
    r = get_user_role(user)
    return r == "admin" or getattr(user, "is_staff", False) or getattr(user, "is_superuser", False)


# you can use @admin_required on views
admin_required = user_passes_test(is_admin_user, login_url="login")


# ---------- Reception dashboard ----------
from datetime import datetime, timedelta
import json

from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.shortcuts import render




@login_required
def reception_dashboard(request):

    now = timezone.now()
    today = now.date()

    # ✅ FIXED: Today's appointments (entire day range)
    today_start = timezone.make_aware(datetime.combine(today, datetime.min.time()))
    today_end = timezone.make_aware(datetime.combine(today, datetime.max.time()))
    
    # BASIC COUNTS
    patient_count = Patient.objects.count()
    total_appointments = Appointment.objects.count()
    
    # ✅ FIXED: Use datetime range instead of __date lookup
    todays_appointments = Appointment.objects.filter(
        scheduled_time__range=[today_start, today_end]
    ).count()
    
    pending_appointments = Appointment.objects.filter(status="scheduled").count()
    completed_appointments = Appointment.objects.filter(status="completed").count()
    cancelled_appointments = Appointment.objects.filter(status="cancelled").count()

    # GROWTH PERCENTAGES
    last_week = now - timedelta(days=7)

    # Patient growth
    patients_last_week = Patient.objects.filter(created_at__lte=last_week).count()
    if patients_last_week > 0:
        patient_growth = round(
            ((patient_count - patients_last_week) / patients_last_week) * 100, 1
        )
    else:
        patient_growth = 100 if patient_count > 0 else 0

    # Appointment growth
    appointments_last_week = Appointment.objects.filter(
        scheduled_time__lte=last_week
    ).count()
    if appointments_last_week > 0:
        appointments_growth = round(
            ((total_appointments - appointments_last_week) / appointments_last_week) * 100, 1
        )
    else:
        appointments_growth = 100 if total_appointments > 0 else 0

    # ✅ FIXED: Yesterday's appointments comparison
    yesterday = today - timedelta(days=1)
    yesterday_start = timezone.make_aware(datetime.combine(yesterday, datetime.min.time()))
    yesterday_end = timezone.make_aware(datetime.combine(yesterday, datetime.max.time()))
    
    appointments_yesterday = Appointment.objects.filter(
        scheduled_time__range=[yesterday_start, yesterday_end]
    ).count()
    
    if appointments_yesterday > 0:
        today_growth = round(
            ((todays_appointments - appointments_yesterday) / appointments_yesterday) * 100, 1
        )
    else:
        today_growth = 100 if todays_appointments > 0 else 0

    # Pending growth
    pending_last_week = Appointment.objects.filter(
        status="scheduled", scheduled_time__lte=last_week
    ).count()
    if pending_last_week > 0:
        pending_growth = round(
            ((pending_appointments - pending_last_week) / pending_last_week) * 100, 1
        )
    else:
        pending_growth = 100 if pending_appointments > 0 else 0

    # Completed growth
    completed_last_week = Appointment.objects.filter(
        status="completed", scheduled_time__lte=last_week
    ).count()
    if completed_last_week > 0:
        completed_growth = round(
            ((completed_appointments - completed_last_week) / completed_last_week) * 100, 1
        )
    else:
        completed_growth = 100 if completed_appointments > 0 else 0

    # PATIENT GROWTH DATA (last 4 weeks)
    week_counts = []
    for i in range(4, 0, -1):
        week_start = now - timedelta(weeks=i)
        week_end = now - timedelta(weeks=i - 1)
        count = Patient.objects.filter(
            created_at__range=[week_start, week_end]
        ).count()
        week_counts.append(count)

    cumulative_patients = []
    running_total = 0
    for c in week_counts:
        running_total += c
        cumulative_patients.append(running_total)

    # WEEKLY APPOINTMENTS DATA (Mon–Sun)
    week_start = now - timedelta(days=now.weekday())
    week_start = week_start.replace(hour=0, minute=0, second=0, microsecond=0)

    weekly_appointments_data = []
    for i in range(7):
        day_start = week_start + timedelta(days=i)
        day_end = day_start + timedelta(days=1)
        count = Appointment.objects.filter(
            scheduled_time__range=[day_start, day_end]
        ).count()
        weekly_appointments_data.append(count)

    # YEARLY APPOINTMENT STATUS DATA
    year = now.year
    monthly_stats = []
    tz = timezone.get_current_timezone()

    for month in range(1, 13):
        month_start = datetime(year, month, 1, tzinfo=tz)
        if month == 12:
            month_end = datetime(year + 1, 1, 1, tzinfo=tz)
        else:
            month_end = datetime(year, month + 1, 1, tzinfo=tz)

        scheduled = Appointment.objects.filter(
            scheduled_time__range=[month_start, month_end],
            status="scheduled",
        ).count()
        completed_m = Appointment.objects.filter(
            scheduled_time__range=[month_start, month_end],
            status="completed",
        ).count()
        cancelled_m = Appointment.objects.filter(
            scheduled_time__range=[month_start, month_end],
            status="cancelled",
        ).count()

        monthly_stats.append({
            "month": month,
            "scheduled": scheduled,
            "completed": completed_m,
            "cancelled": cancelled_m,
        })

    context = {
        "today": now,
        "now": now,
        "patient_count": patient_count,
        "total_appointments": total_appointments,
        "todays_appointments": todays_appointments,
        "pending_appointments": pending_appointments,
        "completed_appointments": completed_appointments,
        "cancelled_appointments": cancelled_appointments,
        "patient_growth": patient_growth,
        "appointments_growth": appointments_growth,
        "today_growth": today_growth,
        "pending_growth": pending_growth,
        "completed_growth": completed_growth,
        "patient_growth_data": json.dumps(cumulative_patients),
        "weekly_appointments_data": json.dumps(weekly_appointments_data),
        "monthly_stats": json.dumps(monthly_stats),
    }

    return render(request, "dashboards/reception_dashboard.html", context)

# ---------- Router (single entrypoint) ----------
@login_required
def dashboard_router(request):
    """
    Route each user to the appropriate dashboard based on role.
    Use this as the main /dashboard/ url.
    """
    role = get_user_role(request.user)
    if role == "admin":
        return admin_dashboard(request)
    if role in ("receptionist"):
        return reception_dashboard(request)
    if role == "doctor":
        return doctor_dashboard(request)

    # default fallback
    return reception_dashboard(request)


@login_required
def dashboard(request):
    """
    Role-aware dashboard:
    - receptionist / admin: see all upcoming appointments
    - doctor: see their appointments
    - patient: see their own appointments (via Patient.user FK)
    """
    today = timezone.localdate()

    qs = Appointment.objects.filter(
        scheduled_time__date__gte=today
    ).select_related("patient", "doctor")  # ✅ Performance boost

    role = getattr(request.user, "role", None)
    if role == "doctor":
        qs = qs.filter(doctor=request.user)
    elif role in ("receptionist", "admin"):
        pass
    else:
        patient_obj = getattr(request.user, "patient", None)
        if not patient_obj:
            patient_obj = Patient.objects.filter(user=request.user).first()

        if patient_obj:
            qs = qs.filter(patient=patient_obj)
        else:
            qs = Appointment.objects.none()

    upcoming_appointments = list(qs.order_by("scheduled_time")[:10])
    appointment_count = qs.count()

    context = {
        "upcoming_appointments": upcoming_appointments,
        "appointment_count": appointment_count,
        "patient": patient_obj,  # ✅ ADD FOR BUTTON VISIBILITY
    }
    return render(request, "dashboards/dashboard.html", context)

# --- helpers ---
def is_admin(user):
    return user.is_authenticated and getattr(user, "role", "") == "admin"

def is_receptionist(user):
    return user.is_authenticated and getattr(user, "role", "") == "receptionist"

@login_required
def post_login_redirect(request):
    role = (getattr(request.user, "role", "") or "").strip().lower()

    if role in ("admin", "administrator"):
        return redirect(reverse('admin_dashboard'))

    if role == "doctor":
        return redirect(reverse('doctor_dashboard'))

    if role in ("receptionist"):
        return redirect(reverse('reception_dashboard'))

    # fallback home/dashboard
    return redirect(reverse('dashboard'))


