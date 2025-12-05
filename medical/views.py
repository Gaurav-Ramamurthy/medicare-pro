from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from .models import MedicalRecord
from patients.models import Patient





@login_required
def medical_record_edit(request, pk):
    """Edit an existing medical record. Only admin, doctors or the author can edit."""
    rec = get_object_or_404(MedicalRecord, pk=pk, is_active=True)
    
    # Permission check
    user_role = getattr(request.user, "role", None)
    if not (request.user == rec.author or user_role in ("admin", "doctor")):
        messages.error(request, "You don't have permission to edit this record.")
        return redirect("patient_medical_records", pk=rec.patient.pk)

    if request.method == "POST":
        # Update fields
        rec.content = request.POST.get('content', '').strip()
        rec.file_description = request.POST.get('file_description', '').strip()
        
        # Handle file upload
        if 'attachment' in request.FILES:
            rec.attachment = request.FILES['attachment']
        
        rec.save()
        messages.success(request, "Medical record updated successfully.")
        return redirect("patient_medical_records", pk=rec.patient.pk)
    
    context = {
        "record": rec,
        "patient": rec.patient,
        "is_edit": True,
    }
    return render(request, "medical/medical_record_edit.html", context)


@login_required
def medical_record_delete(request, pk):
    """Soft delete a medical record."""
    rec = get_object_or_404(MedicalRecord, pk=pk, is_active=True)
    
    # Permission check
    if not (getattr(request.user, "role", None) == "admin" or request.user == rec.author):
        messages.error(request, "You don't have permission to delete this record.")
        return redirect("patient_medical_records", pk=rec.patient.pk)

    if request.method == "POST":
        # Soft delete
        rec.is_active = False
        rec.save(update_fields=["is_active"])
        messages.success(request, "Medical record deleted successfully.")
        return redirect("patient_medical_records", pk=rec.patient.pk)

    return render(request, "medical/medical_record_confirm_delete.html", {"record": rec})
