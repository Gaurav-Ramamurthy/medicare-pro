# core/views.py - CLEANED & REFACTORED
import json
import logging
import secrets
from datetime import timedelta
from functools import wraps

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import (
    authenticate, get_user_model, login, logout, update_session_auth_hash
)
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.forms import (
    AuthenticationForm, PasswordChangeForm, SetPasswordForm
)
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import EmailMessage, send_mail
from django.db import transaction
from django.db.models import F, Q
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.utils import timezone
from django.utils.crypto import get_random_string
from django.views.decorators.http import require_http_methods

# Local imports
from .decorators import (
    admin_required, is_admin, is_receptionist, receptionist_or_admin_required
)
from .forms import (ForgotPasswordForm, RenameUsernameForm, VerifyOTPForm)
from .models import ContactQuery, PasswordOTP

# App models
from patients.models import Patient
# Constants
logger = logging.getLogger(__name__)
User = get_user_model()
OTP_EXPIRY_MINUTES = getattr(settings, "OTP_EXPIRY_MINUTES", 10)
OTP_MAX_ATTEMPTS = getattr(settings, "OTP_MAX_ATTEMPTS", 5)


def _parse_request_data(request):
    """Parse JSON or form data from request."""
    ct = request.META.get("CONTENT_TYPE", "")
    if "application/json" in ct:
        try:
            return json.loads(request.body.decode() or "{}")
        except Exception:
            return {}
    return request.POST


def _get_target_user_from_otp(otp):
    """Get or create User from OTP target (user or patient)."""
    if otp.user:
        return otp.user
    
    if otp.patient and otp.patient.email:
        # Try existing user first
        user = User.objects.filter(email__iexact=otp.patient.email).first()
        if user:
            return user
        
        # Create new user for patient
        base = (otp.patient.first_name or "patient").strip().lower() or "patient"
        base = "".join(ch for ch in base if ch.isalnum() or ch == "_")[:18] or "patient"
        username = base
        suffix = 1
        
        while User.objects.filter(username=username).exists():
            username = f"{base[:16]}{suffix}"
            suffix += 1
        
        temp_pw = get_random_string(24)
        user = User.objects.create_user(
            username=username,
            email=otp.patient.email,
            password=temp_pw
        )
        
        # Copy patient details
        user.first_name = otp.patient.first_name or ""
        user.last_name = otp.patient.last_name or ""
        user.save()
        logger.info(f"Created user {username} for patient {otp.patient}")
        return user
    
    return None


def _is_ajax_request(request):
    """Check if request is AJAX/JSON."""
    return (
        request.headers.get("x-requested-with") == "XMLHttpRequest" or
        "application/json" in request.META.get("CONTENT_TYPE", "")
    )


# === PASSWORD RESET FLOW ===
@require_http_methods(["GET", "POST"])
def forgot_password_request(request):
    """Handle forgot password request and send OTP."""
    if request.method == "POST":
        data = _parse_request_data(request)
        form = ForgotPasswordForm(data)
        
        if form.is_valid():
            email = form.cleaned_data["email"].strip().lower()
            user = User.objects.filter(email__iexact=email).first()
            patient = Patient.objects.filter(email__iexact=email).first() if not user else None
            
            if user or patient:
                code = f"{secrets.randbelow(10**6):06d}"
                PasswordOTP.objects.create(
                    user=user,
                    patient=patient,
                    code=code
                )
                
                if settings.DEBUG:
                    print(f"OTP for {email}: {code}")
                
                # Send email (non-blocking)
                try:
                    name = (user.get_full_name() or user.username) if user else (
                        f"{patient.first_name or ''} {patient.last_name or ''}".strip() or email
                    )
                    message = (
                        f"Hello {name},\n\n"
                        f"Your password reset code is: {code}\n"
                        f"This code expires in {OTP_EXPIRY_MINUTES} minutes.\n\n"
                        "If you did not request this, ignore this email."
                    )
                    send_mail(
                        "Your MediCare Pro password reset code",
                        message,
                        settings.DEFAULT_FROM_EMAIL,
                        [email],
                        fail_silently=True
                    )
                except Exception as e:
                    logger.error(f"OTP email failed: {e}")
            
            if _is_ajax_request(request):
                return JsonResponse({
                    "ok": True,
                    "msg": "If an account exists, a code has been sent."
                })
            messages.success(request, "If an account exists, a code has been sent.")
            return redirect(reverse("verify-otp") + f"?email={email}")
        
        if _is_ajax_request(request):
            return JsonResponse({"ok": False, "errors": form.errors}, status=400)
        messages.error(request, "Please enter a valid email.")
    
    form = ForgotPasswordForm()
    return render(request, "core/forgot_password_inline.html", {"form": form})


@require_http_methods(["GET", "POST"])
def verify_otp(request):
    """Verify OTP and set session for password reset."""
    if request.method != "POST":
        if _is_ajax_request(request):
            return JsonResponse({"ok": False, "msg": "POST required"}, status=400)
        return redirect("forgot-password")
    
    data = _parse_request_data(request)
    if "code" in data and "otp" not in data:
        data = dict(data, otp=data["code"])
    
    form = VerifyOTPForm(data)
    if not form.is_valid():
        if _is_ajax_request(request):
            return JsonResponse({"ok": False, "errors": form.errors}, status=400)
        messages.error(request, "Please provide valid email and 6-digit code.")
        return redirect("forgot-password")
    
    email = form.cleaned_data["email"].strip().lower()
    otp_value = form.cleaned_data.get("otp") or form.cleaned_data.get("code")
    
    # Find target and OTP
    user = User.objects.filter(email__iexact=email).first()
    patient = Patient.objects.filter(email__iexact=email).first() if not user else None
    
    otp_qs = PasswordOTP.objects.none()
    if user:
        otp_qs |= PasswordOTP.objects.filter(user=user, code=otp_value, is_used=False)
    if patient:
        otp_qs |= PasswordOTP.objects.filter(patient=patient, code=otp_value, is_used=False)
    
    otp_qs = otp_qs.order_by("-created_at")
    if not otp_qs.exists():
        if _is_ajax_request(request):
            return JsonResponse({"ok": False, "msg": "Invalid code"}, status=400)
        messages.error(request, "Invalid code.")
        return redirect("forgot-password")
    
    otp = otp_qs.first()
    
    # Check expiry
    now = timezone.now()
    expired = (otp.created_at + timedelta(minutes=OTP_EXPIRY_MINUTES)) < now
    if expired:
        if _is_ajax_request(request):
            return JsonResponse({"ok": False, "msg": "Code expired"}, status=400)
        messages.error(request, "Code expired. Request a new one.")
        return redirect("forgot-password")
    
    # Check attempts
    with transaction.atomic():
        otp.refresh_from_db()
        if otp.is_used:
            if _is_ajax_request(request):
                return JsonResponse({"ok": False, "msg": "Code already used"}, status=400)
            messages.error(request, "Code already used.")
            return redirect("forgot-password")
        
        PasswordOTP.objects.filter(pk=otp.pk).update(attempts=F("attempts") + 1)
        otp.refresh_from_db(fields=["attempts"])
        
        if (otp.attempts or 0) > OTP_MAX_ATTEMPTS:
            if _is_ajax_request(request):
                return JsonResponse({"ok": False, "msg": "Too many attempts"}, status=400)
            messages.error(request, "Too many attempts.")
            return redirect("forgot-password")
        
        otp.is_used = True
        otp.save(update_fields=["is_used"])
    
    # Set session
    request.session["password_reset_otp_id"] = otp.pk
    request.session["password_reset_email"] = email
    
    if _is_ajax_request(request):
        return JsonResponse({"ok": True, "msg": "Code verified successfully"})
    messages.success(request, "Code verified. Set your new password.")
    return redirect("password-reset")


@require_http_methods(["GET", "POST"])
def forgot_password_reset(request):
    """Set new password after OTP verification."""
    otp_id = request.session.get("password_reset_otp_id")
    if not otp_id:
        messages.error(request, "Please verify OTP first.")
        return redirect("forgot-password")
    
    try:
        otp = PasswordOTP.objects.get(pk=otp_id, is_used=True)
    except PasswordOTP.DoesNotExist:
        messages.error(request, "Reset session invalid. Start again.")
        for key in ["password_reset_otp_id", "password_reset_email"]:
            request.session.pop(key, None)
        return redirect("forgot-password")
    
    target_user = _get_target_user_from_otp(otp)
    if not target_user:
        messages.error(request, "No account found.")
        for key in ["password_reset_otp_id", "password_reset_email"]:
            request.session.pop(key, None)
        return redirect("forgot-password")
    
    if request.method == "POST":
        form = SetPasswordForm(user=target_user, data=request.POST)
        if form.is_valid():
            form.save()
            for key in ["password_reset_otp_id", "password_reset_email"]:
                request.session.pop(key, None)
            messages.success(request, "Password updated successfully!")
            return redirect("login")
    else:
        form = SetPasswordForm(user=target_user)
    
    return render(request, "core/forgot_password_inline.html", {
        "form": form,
        "reset_user": target_user,
        "reset_email": otp.patient.email if otp.patient else otp.user.email,
    })


# === ACCOUNT MANAGEMENT ===
@login_required
def account_settings(request):
    """Complete profile management: name, email, username, password with edit mode."""
    user = request.user
    password_form = PasswordChangeForm(user=user)
    
    if request.method == "POST":
        if 'change_password' in request.POST:
            # Handle PASSWORD CHANGE
            password_form = PasswordChangeForm(user=user, data=request.POST)
            if password_form.is_valid():
                user = password_form.save()
                update_session_auth_hash(request, user)
                messages.success(request, "Your password was changed successfully!")
                return redirect("account-settings")
            # Keep errors for modal display
    
        elif 'update_profile' in request.POST:
            # Handle PROFILE UPDATE - ALL fields including username
            first_name = request.POST.get('first_name', '').strip()
            last_name = request.POST.get('last_name', '').strip()
            email = request.POST.get('email', '').strip()
            username = request.POST.get('username', '').strip()
            phone = request.POST.get('phone', '').strip()
            address = request.POST.get('address', '').strip()
            bio = request.POST.get('bio', '').strip()
            
            # Handle profile picture upload
            profile_pic = request.FILES.get('profile_pic')
            
            errors = []
            
            # Validate required fields
            if not first_name:
                errors.append("First name is required")
            if not last_name:
                errors.append("Last name is required")
            if not email:
                errors.append("Email is required")
            elif '@' not in email:
                errors.append("Please enter a valid email address")
            elif email != user.email and User.objects.filter(email=email).exclude(pk=user.pk).exists():
                errors.append("This email is already in use by another account")
            
            # Validate username
            if not username:
                errors.append("Username is required")
            elif len(username) < 3:
                errors.append("Username must be 3+ characters")
            elif username != user.username and User.objects.filter(username=username).exclude(pk=user.pk).exists():
                errors.append("Username already taken")
            
            # Validate profile picture if uploaded
            if profile_pic:
                if profile_pic.size > 5 * 1024 * 1024:
                    errors.append("Profile picture must be less than 5MB")
                elif not profile_pic.content_type.startswith('image/'):
                    errors.append("Please upload a valid image file")
            
            if errors:
                for error in errors:
                    messages.error(request, error)
            else:
                # Update ALL fields atomically
                user.first_name = first_name
                user.last_name = last_name
                user.email = email
                user.username = username
                
                # Update custom fields if they exist on User model
                if hasattr(user, 'phone'):
                    user.phone = phone
                if hasattr(user, 'address'):
                    user.address = address
                if hasattr(user, 'bio'):
                    user.bio = bio
                if profile_pic and hasattr(user, 'profile_pic'):
                    user.profile_pic = profile_pic
                
                user.save()
                
                messages.success(request, "Profile updated successfully!")
                return redirect("account-settings")
    
    context = {
        "password_form": password_form,
        "user": user,
    }
    return render(request, "core/account_settings.html", context)


@login_required
def rename_username(request):
    """Rename username for logged-in user."""
    if request.method == "POST":
        form = RenameUsernameForm(request.POST, current_user=request.user)
        if form.is_valid():
            request.user.username = form.cleaned_data['new_username']
            request.user.save(update_fields=['username'])
            messages.success(request, "Username updated successfully.")
            return redirect('rename-username')
        messages.error(request, "Please correct the error.")
    else:
        form = RenameUsernameForm(current_user=request.user)
    
    return render(request, "core/rename_username.html", {"form": form})


@login_required
def password_manage(request):
    """Password management for logged-in users."""
    if request.method == "POST":
        form = PasswordChangeForm(user=request.user, data=request.POST)
        if form.is_valid():
            user = form.save()
            update_session_auth_hash(request, user)
            messages.success(request, "Password changed successfully.")
            return redirect("account-settings")
    else:
        form = PasswordChangeForm(user=request.user)
    
    return render(request, "core/password_manage.html", {"form": form, "mode": "change"})


# === AUTH VIEWS ===
def login_view(request):
    """User login with role-based redirects."""
    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            next_url = request.GET.get('next', 'home')
            
            if user.is_staff:
                messages.success(request, f'Welcome back, {user.get_full_name() or user.username}!')
                return redirect('reception_dashboard')
            messages.success(request, f'Welcome, {user.get_full_name() or user.username}!')
            return redirect(next_url)
        messages.error(request, 'Invalid credentials.')
    
    return render(request, 'core/login.html')


@login_required
def logout_view(request):
    """User logout."""
    logout(request)
    messages.success(request, 'Logged out successfully.')
    return redirect('home')


# === PUBLIC PAGES ===
def home(request):
    """Home page."""
    return render(request, 'core/home.html')


def landing_page(request):
    """Public landing page with contact form."""
    if request.method == 'POST':
        full_name = request.POST.get('name')
        email = request.POST.get('email')
        phone = request.POST.get('phone', '')
        message = request.POST.get('message')
        
        if full_name and email and message:
            ContactQuery.objects.create(
                full_name=full_name, email=email, phone=phone, 
                message=message, status='new'
            )
            messages.success(request, 'Message sent successfully!')
        else:
            messages.error(request, 'Please fill required fields.')
        return redirect('landing_page')
    
    return render(request, 'core/landing_page.html')


# === ADMIN VIEWS ===
def is_admin_user(user):
    return getattr(user, 'role', '') == 'admin'


@login_required
@user_passes_test(is_admin_user)
def contact_queries_list(request):
    """Admin contact queries management."""
    if request.method == 'POST':
        if request.POST.get('action') == 'delete':
            query_id = request.POST.get('delete_query_id')
            try:
                query = ContactQuery.objects.get(id=query_id)
                query.delete()
                messages.success(request, f'"{query.full_name}" deleted.')
                if _is_ajax_request(request):
                    return HttpResponse(status=204)
            except ContactQuery.DoesNotExist:
                if _is_ajax_request(request):
                    return JsonResponse({'error': 'Not found'}, status=404)
                messages.error(request, 'Query not found.')
        
        elif query_id := request.POST.get('query_id'):
            reply_message = request.POST.get('reply_message', '').strip()
            if reply_message:
                try:
                    query = ContactQuery.objects.get(id=query_id)
                    query.reply_message = reply_message
                    query.status = 'replied'
                    query.updated_at = timezone.now()
                    query.save()
                    
                    # Send reply email
                    subject = f"Re: Your MediCare Pro Query"
                    html_message = f"""
                    <div style="font-family: Arial, sans-serif; max-width: 600px;">
                        <h2 style="color: #00bcd4;">MediCare Pro Response</h2>
                        <p>Dear <strong>{query.full_name}</strong>,</p>
                        <div style="background: #f8fafc; padding: 20px; border-left: 4px solid #00bcd4;">
                            {reply_message}
                        </div>
                        <p><em>MediCare Pro Team</em></p>
                    </div>
                    """
                    
                    email = EmailMessage(
                        subject=subject, body=html_message,
                        from_email=settings.DEFAULT_FROM_EMAIL, to=[query.email]
                    )
                    email.content_subtype = "html"
                    email.send()
                    
                    messages.success(request, f'Reply sent to {query.full_name}.')
                except Exception as e:
                    logger.error(f"Reply failed: {e}")
                    messages.error(request, 'Reply saved but email failed.')
        
        return redirect('contact_queries')
    
    # List queries with filters
    queries = ContactQuery.objects.all()
    q = request.GET.get('q', '').strip()
    if q:
        queries = queries.filter(
            Q(full_name__icontains=q) | Q(email__icontains=q) |
            Q(phone__icontains=q) | Q(message__icontains=q)
        )
    
    filter_param = request.GET.get('filter', 'newest')
    if filter_param == 'new':
        queries = queries.filter(status='new').order_by('-created_at')
    elif filter_param == 'replied':
        queries = queries.filter(status='replied').order_by('-created_at')
    elif filter_param == 'oldest':
        queries = queries.order_by('created_at')
    else:
        queries = queries.order_by('-created_at')
    
    return render(request, 'core/contact_queries_list.html', {'queries': queries})


# ✅ ADD THIS COMPLETE VIEW
def check_username_availability(request):
    """AJAX endpoint to check if username is available"""
    username = request.GET.get('username', '').strip().lower()
    
    if len(username) < 3:
        return JsonResponse({'available': False, 'suggestion': f"{username}123"})
    
    if User.objects.filter(username__iexact=username).exists():
        # Suggest alternative
        base = username.replace('.', '').replace('-', '')
        suggestion = f"{base}1"
        counter = 1
        while User.objects.filter(username__iexact=suggestion).exists():
            counter += 1
            suggestion = f"{base}{counter}"
        return JsonResponse({'available': False, 'suggestion': suggestion})
    
    return JsonResponse({'available': True, 'suggestion': ''})
