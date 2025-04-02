# Hano
An Interactive Vocabulary Learning Platform for Hearing-Impaired Grade 3 Students.

## Backend for Hano
Uses the Django REST Framework to create the API endpoints used in the app.

### Installation:
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
6. Navigate to /backend/backend and create a <strong>.env file<strong>.
7. Paste this inside the .env file
```
DATABASE_URL=''
```
> <i>Note: contact the developer for the URL to the database</i>
8. Run the server
```
cd backend
```
```
py manage.py runserver
```

