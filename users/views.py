from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth import get_user_model

from .models import Staff
from .forms import UserCreationForm

User = get_user_model()


@login_required
def staff_directory(request):
    """Display staff directory with admins, doctors, and receptionists."""
    admins = (
        User.objects.filter(role='admin')
        .select_related('staff')
        .order_by('first_name', 'last_name')
    )
    doctors = (
        User.objects.filter(role='doctor')
        .select_related('staff')
        .order_by('first_name', 'last_name')
    )
    receptionists = (
        User.objects.filter(role='receptionist')
        .select_related('staff')
        .order_by('first_name', 'last_name')
    )

    return render(request, 'users/staff_directory.html', {
        'admins': admins,
        'doctors': doctors,
        'receptionists': receptionists,
        'q': request.GET.get('q', ''),
        'sort': request.GET.get('sort', 'name'),
    })


@login_required
def staff_delete_view(request, pk):
    """Delete staff user (admin/superuser only)."""
    if not (request.user.is_superuser or getattr(request.user, "role", "") == "admin"):
        messages.error(request, "You don't have permission to delete staff.")
        return redirect("staff_directory")

    user = get_object_or_404(User, pk=pk)
    
    if user.role not in ["doctor", "receptionist", "admin"]:
        messages.error(request, "Only admins, doctors and receptionists can be deleted here.")
        return redirect("staff_directory")

    username = user.username
    user.delete()
    messages.success(request, f"Staff user '{username}' deleted successfully.")
    return redirect("staff_directory")


@login_required
def create_user_view(request):
    """Create new users (Admin/Receptionist only)."""
    current_user = request.user

    # Permission check
    if not getattr(current_user, "role", None) in ["admin", "receptionist"] and not current_user.is_superuser:
        messages.error(request, "You don't have permission to create users.")
        return redirect('dashboard')

    if request.method == 'POST':
        form = UserCreationForm(request.POST, request.FILES, current_user=current_user)
        if form.is_valid():
            role = form.cleaned_data.get("role")

            # Receptionist -> can only create doctors
            if getattr(current_user, "role", None) == "receptionist" and role != "doctor":
                form.add_error("role", "Receptionists can only create doctor accounts.")
                messages.error(request, "You are allowed to create only doctor users.")
            # Admin/superuser -> block patient creation
            elif (current_user.is_superuser or getattr(current_user, "role", "") == "admin") and role == "patient":
                form.add_error("role", "Patients cannot be created from this screen.")
                messages.error(request, "Use the patient registration flow to create patients.")
            else:
                user = form.save()
                messages.success(request, f"User '{user.username}' created successfully!")
                return redirect('create_user')
        else:
            messages.error(request, "Failed to create user. Please check the errors below.")
    else:
        form = UserCreationForm(current_user=current_user)

    context = {
        'form': form,
        'page_title': 'Create New User',
    }
    return render(request, 'users/user_create.html', context)


@login_required
def staff_edit_view(request, pk):
    """Edit User + Staff tables for doctor/receptionist."""
    current_user = request.user

    # Permission check
    if not (current_user.is_superuser or getattr(current_user, "role", "") in ["admin", "receptionist"]):
        messages.error(request, "No permission to edit users.")
        return redirect('staff_directory')

    user_to_edit = get_object_or_404(User, pk=pk)

    # Only doctor/receptionist editable here
    if user_to_edit.role not in ["doctor", "receptionist"]:
        messages.error(request, "Only doctor/receptionist accounts can be edited here.")
        return redirect('staff_directory')

    # Get or create Staff record
    staff, _ = Staff.objects.get_or_create(user=user_to_edit)

    if request.method == 'POST':
        # Update USER table
        username = request.POST.get('username', '').strip()
        email = request.POST.get('email', '').strip()
        first_name = request.POST.get('first_name', '').strip()
        last_name = request.POST.get('last_name', '').strip()

        if not (username and first_name and last_name):
            messages.error(request, "Username, first name and last name are required.")
            return render(request, 'users/staff_edit.html', {
                'user_to_edit': user_to_edit, 'staff': staff
            })

        # Username unique check
        if User.objects.filter(username=username).exclude(pk=pk).exists():
            messages.error(request, f"Username '{username}' is already taken.")
            return render(request, 'users/staff_edit.html', {
                'user_to_edit': user_to_edit, 'staff': staff
            })

        user_to_edit.username = username
        user_to_edit.email = email
        user_to_edit.first_name = first_name
        user_to_edit.last_name = last_name
        user_to_edit.save()

        # Update STAFF table
        staff.phone = request.POST.get('phone', staff.phone or '').strip()
        staff.address = request.POST.get('address', staff.address or '').strip()
        if 'profile_photo' in request.FILES:
            staff.profile_photo = request.FILES['profile_photo']

        # Doctor fields
        if user_to_edit.role == 'doctor':
            staff.specialization = request.POST.get('specialization', staff.specialization or '').strip()
            staff.registration_number = request.POST.get('registration_number', staff.registration_number or '').strip()
            exp_years = request.POST.get('experience_years', staff.experience_years or 0)
            staff.experience_years = int(exp_years) if exp_years else 0
            notes_value = request.POST.get('notes', '') or staff.notes or ''
            staff.notes = notes_value.strip() if notes_value else ''

        staff.save()

        messages.success(request, f"'{username}' updated!")
        return redirect('staff_directory')

    return render(request, 'users/staff_edit.html', {
        'user_to_edit': user_to_edit,
        'staff': staff
    })
