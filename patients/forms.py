import re
import uuid
import imghdr
from django import forms
from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from django.core.validators import ValidationError
from django.contrib.auth.tokens import default_token_generator
from django.core.files.base import ContentFile
from django.urls import reverse
from django.utils import timezone
from django.utils.http import urlsafe_base64_encode
from django.utils.encoding import force_bytes
from django.conf import settings

# App models
from .models import Patient

# Custom User model
User = get_user_model()

# Configurable limits
MAX_PHOTO_BYTES = 2 * 1024 * 1024  # 2 MB
ALLOWED_CONTENT_TYPES = ("image/jpeg", "image/png")
PHONE_RE = re.compile(r"^\d{7,15}$")  # 7-15 digits


class PatientForm(forms.ModelForm):
    """
    Form for Patient medical data with User personal info fields.
    Handles both Patient model + linked User data.
    """
    
    # User fields (personal info)
    first_name = forms.CharField(
        max_length=150, 
        required=False,
        widget=forms.TextInput(attrs={"class": "mc-field", "placeholder": "First Name"})
    )
    last_name = forms.CharField(
        max_length=150, 
        required=False,
        widget=forms.TextInput(attrs={"class": "mc-field", "placeholder": "Last Name"})
    )
    email = forms.EmailField(
        required=False,
        widget=forms.EmailInput(attrs={"class": "mc-field", "placeholder": "Email Address"})
    )
    phone = forms.CharField(
        max_length=20, 
        required=False,
        widget=forms.TextInput(attrs={"class": "mc-field", "placeholder": "Phone Number"})
    )
    address = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"class": "mc-textarea", "rows": 2, "placeholder": "Address"})
    )
    
    class Meta:
        model = Patient
        fields = [
            "photo",
            "date_of_birth",
            "blood_group",
            "gender",
            "emergency_contact",
            "medical_history",
        ]
        widgets = {
            "photo": forms.FileInput(attrs={"class": "mc-field", "accept": "image/*"}),
            "date_of_birth": forms.DateInput(attrs={"type": "date", "class": "mc-field"}),
            "blood_group": forms.Select(attrs={"class": "mc-field"}),
            "gender": forms.Select(attrs={"class": "mc-field"}),
            "emergency_contact": forms.TextInput(attrs={"class": "mc-field", "placeholder": "Emergency Contact"}),
            "medical_history": forms.Textarea(attrs={"class": "mc-textarea", "rows": 4}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Set max date for date_of_birth
        try:
            today = timezone.localdate().strftime("%Y-%m-%d")
            if "date_of_birth" in self.fields:
                self.fields["date_of_birth"].widget.attrs["data-max"] = today
        except Exception:
            pass
        
        # Pre-populate User fields if patient has user linked
        if self.instance and self.instance.pk and self.instance.user:
            user = self.instance.user
            self.fields['first_name'].initial = user.first_name
            self.fields['last_name'].initial = user.last_name
            self.fields['email'].initial = user.email
            self.fields['phone'].initial = getattr(user, 'phone', '')
            self.fields['address'].initial = getattr(user, 'address', '')

    def clean_email(self):
        """Validate email is unique among Users"""
        email = self.cleaned_data.get("email")
        if not email:
            return email
        
        qs = User.objects.filter(email__iexact=email)
        if self.instance and self.instance.user:
            qs = qs.exclude(pk=self.instance.user.pk)
        
        if qs.exists():
            raise ValidationError("This email is already in use by another user.")
        return email

    def clean_phone(self):
        """Validate phone number format"""
        phone = (self.cleaned_data.get("phone") or "").strip()
        if not phone:
            return phone
        normalized = re.sub(r"[ \-()]", "", phone)
        if not PHONE_RE.match(normalized):
            raise ValidationError("Enter a valid phone number (7–15 digits).")
        return normalized

    def clean_emergency_contact(self):
        """Validate emergency contact number"""
        phone = (self.cleaned_data.get("emergency_contact") or "").strip()
        if not phone:
            return phone
        normalized = re.sub(r"[ \-()]", "", phone)
        if not PHONE_RE.match(normalized):
            raise ValidationError("Enter a valid phone number (7–15 digits).")
        return normalized

    def clean_date_of_birth(self):
        """Validate date of birth is not in future"""
        dob = self.cleaned_data.get("date_of_birth")
        if not dob:
            return dob
        today = timezone.localdate()
        if dob > today:
            raise ValidationError("Date of birth cannot be in the future.")
        return dob

    def clean_photo(self):
        """Validate photo file size and type"""
        photo = self.cleaned_data.get("photo")
        if not photo:
            return photo

        # Check file size
        if hasattr(photo, "size") and photo.size > MAX_PHOTO_BYTES:
            raise ValidationError(f"Image is too large (max {MAX_PHOTO_BYTES // (1024*1024)} MB).")

        # Check content type
        content_type = getattr(photo, "content_type", None)
        if content_type and content_type not in ALLOWED_CONTENT_TYPES:
            raise ValidationError("Only JPEG and PNG images are allowed.")

        # Verify it's actually an image
        try:
            photo.seek(0)
            kind = imghdr.what(None, h=photo.read(512))
            photo.seek(0)
            if kind not in ("jpeg", "png"):
                raise ValidationError("Uploaded file doesn't look like a valid JPEG or PNG image.")
        except ValidationError:
            raise
        except Exception:
            pass

        return photo

    def save(self, commit=True, create_user=False, send_activation=False, request=None):
        """
        Save Patient and optionally create/sync linked User (role=patient).
        """
        patient = super().save(commit=False)

        # Get User data from extra fields
        first_name = self.cleaned_data.get('first_name', '')
        last_name = self.cleaned_data.get('last_name', '')
        email = self.cleaned_data.get('email', '')
        phone = self.cleaned_data.get('phone', '')
        address = self.cleaned_data.get('address', '')

        # Update existing linked user or create new one
        if patient.user:
            # Update existing user
            user = patient.user
            user.first_name = first_name
            user.last_name = last_name
            user.email = email
            if hasattr(user, 'phone'):
                user.phone = phone
            if hasattr(user, 'address'):
                user.address = address
            user.save()
        elif create_user:
            # Create new user
            if email:
                username = email.split('@')[0]
            else:
                suffix = uuid.uuid4().hex[:8]
                username = f"patient{suffix}"
            
            # Ensure unique username
            base_username = username
            counter = 1
            while User.objects.filter(username=username).exists():
                username = f"{base_username}{counter}"
                counter += 1
            
            user = User.objects.create(
                username=username,
                first_name=first_name,
                last_name=last_name,
                email=email,
                phone=phone,
                address=address,
                role="patient",
                is_active=False,  # Inactive until they set password
            )
            
            patient.user = user
            
            # Send activation email if requested
            if send_activation and request and email:
                try:
                    self.send_activation_email(user, request, patient=patient)
                except Exception as exc:
                    if settings.DEBUG:
                        print("send_activation_email failed:", repr(exc))
        
        if commit:
            patient.save()
        
        return patient

    def send_activation_email(self, user, request, patient=None):
        """Send account activation email to patient"""
        token = default_token_generator.make_token(user)
        uidb64 = urlsafe_base64_encode(force_bytes(user.pk))
        path = reverse("patient-activate", kwargs={"uidb64": uidb64, "token": token})
        activation_url = request.build_absolute_uri(path)

        patient_name = f"{user.first_name} {user.last_name}".strip() or user.username

        subject = "Activate your MediCare Pro account"
        message = f"""Hello {patient_name},

You were registered at MediCare Pro. To set your password and activate your account, click the link below:

{activation_url}

If you did not expect this email, ignore it.

Thanks,
MediCare Pro Team
"""
        send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [user.email])


class ReceptionistPatientCreateForm(forms.ModelForm):
    """
    Receptionist/Admin: Create new patient with full profile.
    Creates both User account and Patient medical record.
    """
    
    # ✅ NEW: Username field (user can enter!)
    username = forms.CharField(
        max_length=150,
        required=True,
        help_text="Patient login username (letters, numbers, dots, hyphens)",
        widget=forms.TextInput(attrs={
            "class": "form-control", 
            "placeholder": "john.doe",
            "id": "id_username"
        })
    )
    
    # User fields (personal info)
    first_name = forms.CharField(
        max_length=150,
        required=True,
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "First Name"})
    )
    last_name = forms.CharField(
        max_length=150,
        required=True,
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "Last Name"})
    )
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={"class": "form-control", "placeholder": "Email Address"})
    )
    phone = forms.CharField(
        max_length=20,
        required=True,
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "Phone Number"})
    )
    address = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"class": "form-control", "rows": 2, "placeholder": "Address"})
    )
    
    class Meta:
        model = Patient
        fields = [
            "photo",
            "date_of_birth",
            "blood_group",
            "gender",
            "emergency_contact",
            "medical_history",
        ]
        widgets = {
            "photo": forms.FileInput(attrs={"class": "form-control", "accept": "image/*"}),
            "date_of_birth": forms.DateInput(attrs={"type": "date", "class": "form-control"}),
            "blood_group": forms.Select(attrs={"class": "form-control"}),
            "gender": forms.Select(attrs={"class": "form-control"}),
            "emergency_contact": forms.TextInput(attrs={"class": "form-control", "placeholder": "Emergency Contact"}),
            "medical_history": forms.Textarea(attrs={"class": "form-control", "rows": 4, "placeholder": "Medical history..."}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Pre-populate if editing existing patient
        if self.instance and self.instance.pk and self.instance.user:
            user = self.instance.user
            self.fields['first_name'].initial = user.first_name
            self.fields['last_name'].initial = user.last_name
            self.fields['email'].initial = user.email
            self.fields['username'].initial = user.username  # ✅ NEW
            self.fields['phone'].initial = getattr(user, 'phone', '')
            self.fields['address'].initial = getattr(user, 'address', '')
    
    def clean_username(self):
        """✅ NEW: Validate username"""
        username = self.cleaned_data.get("username", "").strip().lower()
        if not username:
            raise forms.ValidationError("Username is required.")
        if len(username) < 3:
            raise forms.ValidationError("Username must be 3+ characters.")
        if not re.match(r'^[a-z0-9.-]+$', username):
            raise forms.ValidationError("Username can only contain letters, numbers, dots, and hyphens.")
        
        # Check if username exists
        qs = User.objects.filter(username__iexact=username)
        if self.instance and self.instance.user:
            qs = qs.exclude(pk=self.instance.user.pk)
        
        if qs.exists():
            raise forms.ValidationError("Username already taken.")
        
        return username
    
    def clean_email(self):
        """Validate email is unique"""
        email = self.cleaned_data.get("email", "").strip()
        if not email:
            raise forms.ValidationError("Email is required.")
        
        qs = User.objects.filter(email__iexact=email)
        if self.instance and self.instance.user:
            qs = qs.exclude(pk=self.instance.user.pk)
        
        if qs.exists():
            raise forms.ValidationError("This email is already in use.")
        return email
    
    def clean_phone(self):
        """Validate phone format"""
        phone = (self.cleaned_data.get("phone") or "").strip()
        if not phone:
            raise forms.ValidationError("Phone number is required.")
        
        normalized = re.sub(r"[ \-()]", "", phone)
        if not PHONE_RE.match(normalized):
            raise forms.ValidationError("Enter a valid phone number (7–15 digits).")
        return normalized
    
    def clean_emergency_contact(self):
        """Validate emergency contact format"""
        phone = (self.cleaned_data.get("emergency_contact") or "").strip()
        if not phone:
            return phone
        
        normalized = re.sub(r"[ \-()]", "", phone)
        if not PHONE_RE.match(normalized):
            raise forms.ValidationError("Enter a valid phone number (7–15 digits).")
        return normalized
    
    def save(self, commit=True):
        """✅ FIXED: Password = Username"""
        patient = super().save(commit=False)
        
        # Get data from form
        first_name = self.cleaned_data.get('first_name', '')
        last_name = self.cleaned_data.get('last_name', '')
        email = self.cleaned_data.get('email', '')
        username = self.cleaned_data.get('username', '').strip().lower()  # ✅ Password = Username
        phone = self.cleaned_data.get('phone', '')
        address = self.cleaned_data.get('address', '')
        
        if patient.user:
            # Update existing user
            user = patient.user
            user.first_name = first_name
            user.last_name = last_name
            user.email = email
            user.username = username
            if hasattr(user, 'phone'):
                user.phone = phone
            if hasattr(user, 'address'):
                user.address = address
            user.set_password(username)  # ✅ Password = Username
            user.save()
        else:
            # ✅ Create new user - PASSWORD = USERNAME
            user = User.objects.create_user(
                username=username,
                email=email,
                password=username,  # ✅ Password = Username (same as username!)
                first_name=first_name,
                last_name=last_name,
                phone=phone if hasattr(User._meta.get_fields(), 'phone') else None,
                address=address if hasattr(User._meta.get_fields(), 'address') else None,
                role="patient",
                is_active=True,
            )
            patient.user = user
        
        if commit:
            patient.save()
        
        # ✅ Store for view success message
        self._created_password = username  # Same as username!
        
        return patient