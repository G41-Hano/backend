# Hano
An Interactive Vocabulary Learning Platform for Hearing-Impaired Grade 3 Students.

<br>

## Backend for Hano
Uses the Django REST Framework to create the API endpoints used in the app.

### Backend Stack
- Django 5.1.7 – Core backend framework
- Django REST Framework (DRF) 3.16.0 – API layer for building RESTful endpoints

### Authentication & Security
- SimpleJWT – JWT-based authentication for API endpoints
- Cryptography & PyJWT – Handling JWT signing/verification and secure operations

### Storage & File Handling
- django-storages & boto3 – Integration with AWS S3 for file uploads & media storage

### Database Layer
- PostgreSQL via psycopg2-binary – Primary relational database used by Django ORM

### AI Integration
- google-genai – Used for integrating Google Generative AI models

## Installation:
1. Navigate to your main app folder (Hano)
```
cd Hano
```
2. Clone the repository
```
git clone https://github.com/G41-Hano/backend.git
```
3. Set up <strong>virtual environment</strong>
```
py -m venv env
```
4. Activate <strong>virtual environment</strong>
```
env\Scripts\activate
```
> <i>Note: when activating the <strong>virtual environment</strong> and an error like "execution of scripts is disabled on this system" occurs, enter:</i>
```
Set-ExecutionPolicy Unrestricted -Scope Process
```
> Then try to activate the <strong>virtual environment</strong> 
```
env\Scripts\activate
```
5. Install requirements.txt
```
pip install -r "backend/requirements.txt"
```
6. Navigate to /backend/backend and create a <strong>.env file</strong>.
7. Paste these required variables inside the .env file
```
# PostgreSQL Database URL 
DATABASE_URL=''

# Password Reset related 
PASSWORD_RESET_BASE_URL=
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=
EMAIL_HOST_PASSWORD=
DEFAULT_FROM_EMAIL=

# Encryption key
ENCRYPTION_KEY=

# Generative AI 
GEMINI_API_KEY=

# AMAZON S3 related variables
S3_ACCESS_KEY=
S3_SECRET_KEY=
S3_BUCKET_NAME=
```
> <i>Note: contact the developer for further assistance if needed</i>
8. Create badges (if a fresh new database is used)
```
python manage.py create_badges
```
9. Run the server
```
cd backend
```
```
py manage.py runserver
```

#### If you encounter "missing imports" problem, change the Python Interpreter to your <strong>virtual environment</strong>.
1. In VS Code, press ```F1``` and type:
```
Python: Select Interpreter
```
2. Click ```Enter interpreter path...```
3. Click ```Find...```
4. Navigate to ```Hano/env/Scripts``` then select ```python.exe```

### Deployment
#### Preparation:
1. Ensure that PostgreSQL database is running.
2. Environment variables should be noted.
3. [Render](https://render.com/) account must be ready.
#### Create Services on [Render](https://render.com/)
1. Go to New → Web Service
2. Provide link of [Github Repo](https://github.com/G41-Hano/backend)
3. Enter a unique name for the web service.
4. Select region of services
5. Import the Environment variables. Adjust when necessary
6. Deploy Web Service
