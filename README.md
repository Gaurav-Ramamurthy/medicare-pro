# 🏥 MediCare Pro — Healthcare Management System
A full-featured Healthcare Management System built using **Python, Django, MySQL**, and a modular multi-app architecture. The system manages **patients, doctors, appointments, medical records, dashboards, authentication, and more**.

---

## 📌 Project Overview
MediCare Pro is designed for hospitals & clinics to efficiently manage day-to-day operations, including:
- Patient Registration & Profiles
- Doctor Management
- Appointment Booking & Scheduling
- Medical Records & Reports
- Staff Login & Role-Based Access (Admin, Doctor, Reception)
- Interactive Dashboards
- Media File Management
- Secure Authentication System

---

## 🚀 Tech Stack
| Layer | Technology |
|------|------------|
| Backend | Django 5+ |
| Database | MySQL |
| Frontend | HTML, CSS, JS |
| Styling | Custom CSS (inside `/static/`) |
| Package Manager | pip |
| Deployment Support | Vercel (`vercel.json` included) |

---

## 📂 Project Folder Structure
medicare-pro/
│── .env
│── .gitignore
│── manage.py
│── requirements.txt
│── vercel.json
│── media/
│── static/
│── generate_diverse.py
│── pytest.ini
│
├── appointments/
├── core/
├── dashboards/
├── medical/
├── medicare/ # Main Django project settings
├── patients/
├── users/
└── ...

yaml
Copy code

### 📌 Important Apps
| App | Purpose |
|-----|---------|
| **core** | Base models & utilities |
| **users** | Authentication, roles, permissions |
| **patients** | Patient registration & management |
| **appointments** | Booking, calendar, scheduling |
| **medical** | Medical history, prescriptions |
| **dashboards** | Role-based dashboards |
| **medicare** | Project settings, URLs |

---

## 🛠️ Installation Guide

### 1️⃣ Clone the Project
```bash
git clone <repository-url>
cd medicare-pro
2️⃣ Create Virtual Environment
bash
Copy code
python -m venv .venv
3️⃣ Activate Virtual Environment
Windows (CMD):

bash
Copy code
.venv\Scripts\activate
4️⃣ Install Dependencies
bash
Copy code
pip install -r requirements.txt
⚙️ Environment Variables
Your .env file must contain:

ini
Copy code
SECRET_KEY=your_secret_key
DEBUG=True
DB_NAME=medicare
DB_USER=root
DB_PASSWORD=yourpassword
DB_HOST=127.0.0.1
DB_PORT=3306
🗄️ Database Setup (MySQL)
1️⃣ Create Database
sql
Copy code
CREATE DATABASE medicare;
2️⃣ Apply Migrations
bash
Copy code
python manage.py migrate
3️⃣ Create Superuser
bash
Copy code
python manage.py createsuperuser
▶️ Run the Development Server
bash
Copy code
python manage.py runserver
Visit:
👉 http://127.0.0.1:8000/

🔑 User Roles Supported
Admin — Full access

Doctor — Appointments, patient medical records

Receptionist — Patient registration, appointment booking

Roles are managed inside the users app.

🖼️ Media & Static Files
Uploads → /media/
Static → /static/

For production:

bash
Copy code
python manage.py collectstatic
🌐 Deployment (Vercel Ready)
The project includes:

pgsql
Copy code
vercel.json
Deploy:

bash
Copy code
vercel --prod
🧪 Testing
Configured via pytest.ini:

bash
Copy code
pytest
📦 Requirements
Install all dependencies:

bash
Copy code
pip install -r requirements.txt
