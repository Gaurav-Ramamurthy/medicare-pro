from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
import os

User = get_user_model()


class Command(BaseCommand):
    help = "Create initial superuser if none exists"

    def handle(self, *args, **options):
        # If there is already any superuser, don't create another
        if User.objects.filter(is_superuser=True).exists():
            self.stdout.write("Superuser already exists")
            return

        username = os.getenv("DJANGO_SUPERUSER_USERNAME", "admin")
        email = os.getenv("DJANGO_SUPERUSER_EMAIL", "gaurav77955@gmail.com")
        password = os.getenv("DJANGO_SUPERUSER_PASSWORD", "admin@123")

        user = User.objects.create_superuser(
            username=username,
            email=email,
            password=password,
        )

        # Ensure flags for admin access
        user.is_staff = True
        user.is_superuser = True

        # If your custom user model has a role / user_type field, set it
        if hasattr(user, "role"):
            user.role = "admin"
        if hasattr(user, "user_type"):
            user.user_type = "admin"

        user.save()

        self.stdout.write(self.style.SUCCESS(f"Superuser {username} created/updated as admin"))
