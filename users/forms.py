from django import forms
from django.contrib.auth import get_user_model

User = get_user_model()


class UserCreationForm(forms.ModelForm):
    """
    Form to create new users.
    - Admin can create: Admin, Doctor, Receptionist, Patient
    - Receptionist can create: Doctor, Patient (NOT Receptionist or Admin)
    """
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={"class": "input", "placeholder": "Enter password"}),
        label="Password",
        required=True
    )
    username = forms.CharField(
        max_length=150,
        label="Username",
        widget=forms.TextInput(attrs={"class": "input", "placeholder": "Enter username"}),
        required=True
    )
    email = forms.EmailField(
        required=False,
        widget=forms.EmailInput(attrs={"class": "input", "placeholder": "Enter email"})
    )

    class Meta:
        model = User
        fields = ['username', 'email', 'role', 'password', 'first_name', 'last_name', 'phone', 'address']
        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'input', 'placeholder': 'First Name'}),
            'last_name': forms.TextInput(attrs={'class': 'input', 'placeholder': 'Last Name'}),
            'role': forms.Select(attrs={'class': 'input'}),
            'phone': forms.TextInput(attrs={'class': 'input', 'placeholder': 'Phone Number'}),
            'address': forms.Textarea(attrs={'class': 'input', 'rows': 3, 'placeholder': 'Address'}),
        }

    def __init__(self, *args, **kwargs):
        self.current_user = kwargs.pop('current_user', None)
        super().__init__(*args, **kwargs)

        # Restrict role choices based on current user role
        if self.current_user:
            if self.current_user.role == 'reception':
                # Receptionist can only create doctor and patient
                allowed_roles = [
                    ('doctor', 'Doctor'),
                    ('patient', 'Patient'),
                ]
            elif self.current_user.role == 'admin':
                # Admin can create anyone
                allowed_roles = [
                    ('admin', 'Admin'),
                    ('doctor', 'Doctor'),
                    ('reception', 'Receptionist'),
                    ('patient', 'Patient'),
                ]
            else:
                # Default: all roles
                allowed_roles = [(choice[0], choice[1]) for choice in User.ROLE_CHOICES]
        else:
            # No current user: show all roles
            allowed_roles = [(choice[0], choice[1]) for choice in User.ROLE_CHOICES]

        self.fields['role'].widget.choices = allowed_roles

    def clean_username(self):
        """Validate username is unique"""
        username = self.cleaned_data.get('username', '').strip()
        
        if not username:
            raise forms.ValidationError("Username is required.")
        
        if self.current_user and username == self.current_user.username:
            raise forms.ValidationError("This is already your username.")
        
        if User.objects.filter(username__iexact=username).exists():
            raise forms.ValidationError("That username is already taken.")
        
        return username

    def clean_role(self):
        """
        Validate that receptionist cannot create receptionist or admin.
        This is a safety check in addition to restricting choices.
        """
        role = self.cleaned_data.get('role')
        
        if self.current_user and self.current_user.role == 'reception':
            if role in ['reception', 'admin']:
                raise forms.ValidationError(
                    "You don't have permission to create users with this role."
                )
        
        return role

    def save(self, commit=True):
        """Save user with hashed password"""
        user = super().save(commit=False)
        user.set_password(self.cleaned_data["password"])
        if commit:
            user.save()
        return user
