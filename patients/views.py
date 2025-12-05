# Django core imports
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.hashers import make_password
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q
from django.urls import reverse
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from datetime import timedelta

# App models
from .models import Patient, PatientRequest
from appointments.models import Appointment
from medical.models import MedicalRecord, Prescription

# App forms
from .forms import ReceptionistPatientCreateForm
from medical.forms import MedicalRecordForm
# Custom User model
User = get_user_model()


def is_admin_or_receptionist(user):
    """Check if user is admin or receptionist."""
    return user.is_authenticated and (user.role == 'admin' or user.role == 'receptionist')


# =====================================
# PATIENT REGISTRATION (PUBLIC)
# =====================================
def patient_register(request):
    """Patient registration saves request (not Patient) for admin approval."""
    if request.method == 'POST':
        username = request.POST.get('username')
        email = request.POST.get('email')
        password = request.POST.get('password')
        password_confirm = request.POST.get('password_confirm')
        first_name = request.POST.get('first_name')
        last_name = request.POST.get('last_name')
        date_of_birth = request.POST.get('date_of_birth')
        gender = request.POST.get('gender')
        phone = request.POST.get('phone')
        address = request.POST.get('address')
        blood_group = request.POST.get('blood_group', '')
        emergency_contact = request.POST.get('emergency_contact', '')
        medical_history = request.POST.get('medical_history', '')
        photo = request.FILES.get('photo')

        # Validate required fields
        required_fields = [username, email, password, password_confirm, first_name, last_name, date_of_birth, gender, phone, address]
        if not all(required_fields):
            messages.error(request, 'Please fill all required fields.')
            return render(request, 'patients/patient_register.html')

        if password != password_confirm:
            messages.error(request, 'Passwords do not match!')
            return render(request, 'patients/patient_register.html')

        if User.objects.filter(username=username).exists() or PatientRequest.objects.filter(username=username).exists():
            messages.error(request, 'Username already exists or pending approval!')
            return render(request, 'patients/patient_register.html')

        if User.objects.filter(email=email).exists() or PatientRequest.objects.filter(email=email).exists():
            messages.error(request, 'Email already registered or pending approval!')
            return render(request, 'patients/patient_register.html')

        password_hash = make_password(password)

        PatientRequest.objects.create(
            username=username,
            password_hash=password_hash,
            first_name=first_name,
            last_name=last_name,
            date_of_birth=date_of_birth,
            gender=gender,
            phone=phone,
            email=email,
            address=address,
            blood_group=blood_group,
            emergency_contact=emergency_contact,
            medical_history=medical_history,
            photo=photo,
            requested_by=request.user if request.user.is_authenticated else None
        )

        messages.success(request, 'Registration request received with photo! Await admin approval.')
        return redirect('home')

    return render(request, 'patients/patient_register.html')


# =====================================
# CREATE PATIENT (Admin/Receptionist)
# =====================================
@login_required
def create_patient(request):
    """Admin/Receptionist can create new patients."""
    if request.user.role not in ['admin', 'receptionist']:
        messages.error(request, "You don't have permission to create patients.")
        return redirect('dashboard')
    
    if request.method == "POST":
        form = ReceptionistPatientCreateForm(request.POST, request.FILES)
        
        if settings.DEBUG:
            print("DEBUG: CREATE POST keys:", list(request.POST.keys()))
            print("DEBUG: CREATE FILES keys:", list(request.FILES.keys()))
        
        if form.is_valid():
            try:
                with transaction.atomic():
                    patient = form.save()
                    messages.success(request, f"✅ Patient '{patient.full_name}' created successfully!")
                    return redirect(reverse("patient_detail", args=[patient.pk]))
            except Exception as exc:
                messages.error(request, "Failed to create patient. Please try again.")
                if settings.DEBUG:
                    print("DEBUG: create_patient error:", repr(exc))
        else:
            messages.error(request, "Please correct the errors below.")
            if settings.DEBUG:
                print("DEBUG: form.errors:", form.errors)
    else:
        form = ReceptionistPatientCreateForm()
    
    context = {
        "form": form,
        "page_title": "Create New Patient",
        "submit_text": "Create Patient",
    }
    return render(request, "patients/patient_form.html", context)


# =====================================
# EDIT PATIENT
# =====================================
@login_required
def patient_edit(request, pk):
    """Admin/Receptionist can edit patient data."""
    if request.user.role not in ['admin', 'receptionist']:
        messages.error(request, "You don't have permission to edit patients.")
        return redirect('dashboard')
    
    patient = get_object_or_404(Patient, pk=pk)
    
    if request.method == "POST":
        form = ReceptionistPatientCreateForm(request.POST, request.FILES, instance=patient)
        
        if settings.DEBUG:
            print("DEBUG: EDIT POST keys:", list(request.POST.keys()))
            print("DEBUG: EDIT FILES keys:", list(request.FILES.keys()))
        
        if form.is_valid():
            try:
                with transaction.atomic():
                    patient = form.save()
                    messages.success(request, f"✅ Patient '{patient.full_name}' updated successfully!")
                    return redirect(reverse("patient_detail", args=[patient.pk]))
            except Exception as exc:
                messages.error(request, "Failed to update patient. Please try again.")
                if settings.DEBUG:
                    print("DEBUG: patient_edit error:", repr(exc))
        else:
            messages.error(request, "Please correct the errors below.")
            if settings.DEBUG:
                print("DEBUG: patient_edit form.errors:", form.errors)
    else:
        form = ReceptionistPatientCreateForm(instance=patient)
    
    context = {
        "form": form,
        "patient": patient,
        "page_title": f"Edit Patient: {patient.full_name}",
        "submit_text": "Update Patient",
    }
    return render(request, "patients/patient_form.html", context)


# =====================================
# PATIENT LIST
# =====================================
@login_required
def patient_list(request):
    """Show patient list based on user role with blood group filter + search."""
    user = request.user

    if user.role == 'patient':
        return redirect('profile')

    blood_group = request.GET.get("blood_group", "").strip()
    q = request.GET.get("q", "").strip()

    base_qs = Patient.objects.filter(user__isnull=False, user__is_active=True).select_related('user')

    if user.role == 'doctor':
        patient_ids = Appointment.objects.filter(doctor=user).values_list('patient_id', flat=True).distinct()
        patients = base_qs.filter(id__in=patient_ids)
        page_title = 'My Patients'
    elif user.role in ['admin', 'receptionist']:
        patients = base_qs
        page_title = 'All Patients'
    else:
        messages.error(request, "You don't have permission to view patient list.")
        return redirect('dashboard')

    if blood_group:
        patients = patients.filter(blood_group=blood_group)

    if q:
        patients = patients.filter(
            Q(user__first_name__icontains=q) |
            Q(user__last_name__icontains=q) |
            Q(user__email__icontains=q) |
            Q(user__phone__icontains=q) |
            Q(blood_group__icontains=q)
        )

    patients = patients.order_by('user__first_name', 'user__last_name')

    paginator = Paginator(patients, 20)
    page = request.GET.get("page")
    patients_page = paginator.get_page(page)

    context = {
        "patients": patients_page,
        "q": q,
        "page_title": page_title,
        "is_doctor": user.role == 'doctor',
        "can_create": user.role in ['admin', 'receptionist'],
    }
    return render(request, "patients/patient_list.html", context)


# =====================================
# PATIENT DETAIL
# =====================================
@login_required
def patient_detail(request, pk):
    """Show patient profile with appointments, medical records, and prescriptions."""
    user = request.user
    patient = get_object_or_404(Patient, pk=pk)
    
    # Permission checks
    if user.role == 'doctor':
        has_appointment = Appointment.objects.filter(doctor=user, patient=patient).exists()
        if not has_appointment:
            messages.error(request, "You can only view patients you have appointments with.")
            return redirect('patient_list')
    
    elif user.role == 'patient':
        if user.patient != patient:
            messages.error(request, "You can only view your own profile.")
            return redirect('profile')
    
    elif user.role not in ['admin', 'receptionist']:
        messages.error(request, "You don't have permission to view this patient.")
        return redirect('dashboard')
    
    appointments = Appointment.objects.filter(patient=patient).select_related('doctor').order_by('-scheduled_time')[:5]
    records = MedicalRecord.objects.filter(patient=patient, is_active=True).select_related('author').order_by('-created_at')[:5]
    prescriptions = Prescription.objects.filter(patient=patient).select_related('doctor').order_by('-prescribed_date')[:5]
    
    can_add_notes = user.role in ['doctor', 'admin']
    record_form = MedicalRecordForm()
    
    if request.method == "POST" and "content" in request.POST:
        if not can_add_notes:
            messages.error(request, "You don't have permission to add medical notes.")
            return redirect("patient_detail", pk=patient.pk)
        
        record_form = MedicalRecordForm(request.POST)
        if record_form.is_valid():
            try:
                with transaction.atomic():
                    rec = record_form.save(commit=False)
                    rec.patient = patient
                    rec.author = user
                    rec.is_active = True
                    rec.save()
                    messages.success(request, "✅ Medical note added successfully.")
                    return redirect(reverse("patient_detail", args=[patient.pk]))
            except Exception as exc:
                messages.error(request, "Unable to save note. Please try again.")
                if settings.DEBUG:
                    print("Failed to save MedicalRecord:", repr(exc))
        else:
            messages.error(request, "Please fix the errors below.")
            if settings.DEBUG:
                print("MedicalRecordForm errors:", record_form.errors)
    
    context = {
        "patient": patient,
        "appointments": appointments,
        "records": records,
        "prescriptions": prescriptions,
        "record_form": record_form,
        "can_add_notes": can_add_notes,
        "can_edit": user.role in ['admin', 'receptionist'],
        "is_doctor": user.role == 'doctor',
    }
    return render(request, "patients/detail.html", context)


# =====================================
# PATIENT REQUESTS (Admin/Receptionist)
# =====================================
@login_required
@user_passes_test(is_admin_or_receptionist)
def patient_requests_list(request):
    """List pending patient registration requests."""
    q = request.GET.get('q', '').strip()
    sort = request.GET.get('sort', 'newest')

    requests_qs = PatientRequest.objects.filter(status='pending')

    if q:
        requests_qs = requests_qs.filter(
            Q(first_name__icontains=q) |
            Q(last_name__icontains=q) |
            Q(username__icontains=q) |
            Q(email__icontains=q) |
            Q(phone__icontains=q)
        )

    if sort == 'oldest':
        requests_qs = requests_qs.order_by('created_at')
    else:
        requests_qs = requests_qs.order_by('-created_at')

    context = {
        'requests': requests_qs,
        'q': q,
        'sort': sort,
    }
    return render(request, 'patients/patient_requests_list.html', context)


@login_required
@user_passes_test(is_admin_or_receptionist)
def patient_request_approve(request, request_id):
    """Approve patient request and create User + Patient."""
    patient_req = get_object_or_404(PatientRequest, id=request_id, status='pending')

    if User.objects.filter(username=patient_req.username).exists():
        messages.error(request, 'Username conflicts with existing user.')
        return redirect('patient_requests_list')
    if User.objects.filter(email=patient_req.email).exists():
        messages.error(request, 'Email conflicts with existing user.')
        return redirect('patient_requests_list')

    user = User.objects.create(
        username=patient_req.username,
        email=patient_req.email,
        first_name=patient_req.first_name,
        last_name=patient_req.last_name,
    )
    user.password = patient_req.password_hash
    user.save()

    Patient.objects.create(
        user=user,
        first_name=patient_req.first_name,
        last_name=patient_req.last_name,
        date_of_birth=patient_req.date_of_birth,
        gender=patient_req.gender,
        phone=patient_req.phone,
        email=patient_req.email,
        address=patient_req.address,
        blood_group=patient_req.blood_group,
        emergency_contact=patient_req.emergency_contact,
        medical_history=patient_req.medical_history,
    )

    patient_req.status = 'approved'
    patient_req.save()

    messages.success(request, f"Patient request for {patient_req.first_name} approved and added to database.")
    return redirect('patient_requests_list')


@login_required
@user_passes_test(is_admin_or_receptionist)
def patient_request_reject(request, request_id):
    """Reject patient request."""
    patient_req = get_object_or_404(PatientRequest, id=request_id, status='pending')
    patient_req.status = 'rejected'
    patient_req.save()
    
    messages.success(request, f"❌ Patient request for {patient_req.first_name} {patient_req.last_name} rejected successfully.")
    return redirect('patient_requests_list')


# =====================================
# AJAX ACTIONS
# =====================================
@csrf_exempt
@login_required
@user_passes_test(is_admin_or_receptionist)
def ajax_patient_action(request, request_id, action):
    """AJAX approve/reject patient requests."""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST only'}, status=400)

    try:
        req = get_object_or_404(PatientRequest, id=request_id)

        if req.status != 'pending':
            return JsonResponse({'error': 'Only pending requests can be processed'}, status=400)

        if action == 'approve':
            if User.objects.filter(username=req.username).exists():
                return JsonResponse({'error': 'Username already exists.'}, status=400)
            if User.objects.filter(email=req.email).exists():
                return JsonResponse({'error': 'Email already exists.'}, status=400)

            user = User.objects.create_user(
                username=req.username,
                email=req.email,
                password=req.password_hash,
                first_name=req.first_name,
                last_name=req.last_name,
                is_active=True,
            )

            Patient.objects.create(
                user=user,
                date_of_birth=req.date_of_birth,
                gender=req.gender,
                blood_group=req.blood_group,
                emergency_contact=req.emergency_contact,
                medical_history=req.medical_history,
                photo=req.photo,
            )

            req.delete()
            return JsonResponse({
                'success': True,
                'message': 'Patient approved, user + patient created, request removed.'
            })

        elif action == 'reject':
            name = f"{req.first_name} {req.last_name}"
            req.delete()
            return JsonResponse({
                'success': True,
                'message': f'Patient request for {name} rejected and removed.'
            })

        else:
            return JsonResponse({'error': 'Invalid action'}, status=400)

    except PatientRequest.DoesNotExist:
        return JsonResponse({'error': 'Patient request not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': f'Server error: {str(e)}'}, status=500)


@login_required
def patient_delete(request, pk):
    """Admin can disable patient via AJAX."""
    if request.user.role != 'admin':
        return JsonResponse({'error': 'Only administrators can delete patients.'}, status=403)

    if request.method != "POST":
        return JsonResponse({'error': 'Method not allowed'}, status=405)

    patient = get_object_or_404(Patient, pk=pk)

    try:
        with transaction.atomic():
            if patient.user:
                patient.user.is_active = False
                patient.user.save(update_fields=['is_active'])
            return JsonResponse({'success': True})
    except Exception as exc:
        if settings.DEBUG:
            print("DEBUG patient_delete error:", repr(exc))
        return JsonResponse({'error': 'Failed to delete patient.'}, status=500)


# =====================================
# MEDICAL RECORDS & PRESCRIPTIONS
# =====================================
@login_required
def patient_medical_records(request, pk):
    """Manage patient medical records and prescriptions."""
    patient = get_object_or_404(Patient, pk=pk)

    can_add_notes = request.user.role in ['doctor', 'admin']
    is_doctor = request.user.role in ['doctor', 'admin']

    records = MedicalRecord.objects.filter(patient=patient, is_active=True).select_related('author').order_by('-created_at')
    prescriptions = Prescription.objects.filter(patient=patient).select_related('doctor').order_by('-prescribed_date')

    editable_cutoff = timezone.now() - timedelta(minutes=5)
    editable_prescription_ids = set(
        prescriptions.filter(doctor=request.user, prescribed_date__gte=editable_cutoff).values_list('id', flat=True)
    )
    editable_deadlines = {}
    now_ts = int(timezone.now().timestamp())
    for p in prescriptions:
        if p.id in editable_prescription_ids:
            deadline_ts = int(p.prescribed_date.timestamp()) + 5 * 60
            remaining = max(0, deadline_ts - now_ts)
            editable_deadlines[p.id] = remaining

    record_form = None

    if can_add_notes and request.method == 'POST' and request.POST.get('form_type') == 'record':
        content = request.POST.get('content', '').strip()
        file_description = request.POST.get('file_description', '').strip()
        attachment = request.FILES.get('attachment')

        if attachment or content or file_description:
            MedicalRecord.objects.create(
                patient=patient,
                author=request.user,
                content=content,
                file_description=file_description,
                attachment=attachment,
            )
            messages.success(request, 'Medical record added successfully.')
            return redirect('patient_medical_records', pk=patient.pk)
        else:
            messages.error(request, 'Please upload a file or add a description/note.')

    if can_add_notes and request.method == 'GET':
        record_form = MedicalRecordForm()

    if is_doctor and request.method == 'POST' and request.POST.get('form_type') == 'prescription':
        medication_name = request.POST.get('medication_name', '').strip()
        dosage = request.POST.get('dosage', '').strip()
        frequency = request.POST.get('frequency', '').strip()
        duration = request.POST.get('duration', '').strip()
        instructions = request.POST.get('instructions', '').strip()

        if medication_name and dosage and frequency and duration:
            Prescription.objects.create(
                patient=patient,
                doctor=request.user,
                medication_name=medication_name,
                dosage=dosage,
                frequency=frequency,
                duration=duration,
                instructions=instructions or None,
            )
            messages.success(request, f'Prescription for {medication_name} created successfully.')
            return redirect('patient_medical_records', pk=patient.pk)
        else:
            messages.error(request, 'Please fill all required prescription fields.')

    context = {
        'patient': patient,
        'records': records,
        'prescriptions': prescriptions,
        'can_add_notes': can_add_notes,
        'is_doctor': is_doctor,
        'record_form': record_form,
        'editable_prescription_ids': editable_prescription_ids,
        'editable_deadlines': editable_deadlines,
    }
    return render(request, 'patients/patient_medical_records.html', context)
