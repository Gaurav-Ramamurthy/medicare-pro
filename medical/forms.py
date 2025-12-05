from django import forms 
from .models import MedicalRecord

class MedicalRecordForm(forms.ModelForm):
    """
    Form for doctors to add additional notes for medical records.
    Visibility is removed; all records are visible.
    """
    class Meta:
        model = MedicalRecord
        fields = ["content"]  # only content now
        widgets = {
            "content": forms.Textarea(attrs={
                "rows": 6,
                "placeholder": "Enter additional medical notes, observations, diagnosis, etc."
            }),
        }
