from appointments.models import Appointment
from django.contrib.auth import get_user_model
from patients.models import Patient
from django.db.models import Q
from datetime import datetime, timedelta
import random

User = get_user_model()
doctors = ['deepak', 'kavya', 'mahesh', 'manish', 'rishii', 'sanjana', 'sanu', 'shruti', 'vinod']
doctor_users = [User.objects.get(username=d) for d in doctors]

patients_usernames = ['kiran', 'Tulasi', 'aaravsharma29', 'aaravsharma', 'adityasingh', 'aishadesai', 'amitkumar', 'anjali', 'aryanreddy', 'gaurav']
patients = [Patient.objects.get(user__username=u) for u in patients_usernames]

reasons = ['Routine Checkup', 'Fever', 'Diabetes Review', 'BP Check', 'Vaccination', 'Skin Consultation', 'Eye Check', 'Dental Pain', 'Stomach Ache', 'Follow-up']

print("=== TODAY + 3 DAYS | 30-MIN GAPS | DIVERSE ===")
c = 0

# Today + next 3 days
for day_offset in range(4):
    current_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=day_offset)
    print(f"\n📅 {current_date.strftime('%Y-%m-%d (%a)')}")
    
    slot_count = 0
    # 9AM-5PM, 30-min slots (8 slots max/day)
    for minute_offset in range(0, 480, 30):
        if slot_count >= 8: break
        
        hour = 9 + (minute_offset // 60)
        minute = minute_offset % 60
        scheduled_time = current_date.replace(hour=hour, minute=minute)
        
        # Random doctor/patient
        doctor = random.choice(doctor_users)
        patient = random.choice(patients)
        
        # Check conflicts
        doctor_today = Appointment.objects.filter(
            doctor=doctor, 
            scheduled_time__date=scheduled_time.date()
        ).count()
        
        patient_today = Appointment.objects.filter(
            patient=patient, 
            scheduled_time__date=scheduled_time.date()
        ).count()
        
        # No conflicts + limits
        if doctor_today < 6 and patient_today < 1:
            Appointment.objects.create(
                doctor=doctor,
                patient=patient,
                scheduled_time=scheduled_time,
                reason=random.choice(reasons),
                status='scheduled'
            )
            c += 1
            slot_count += 1
            print(f"✅ [{c:2d}] {patient.user.get_full_name()[:12]:12} | Dr.{doctor.username:<8} | {hour}:{minute:02d}")

print(f"\n🎉 {c} DIVERSE appointments created!")
print("Check: http://127.0.0.1:8000/appointments/?status=scheduled")
