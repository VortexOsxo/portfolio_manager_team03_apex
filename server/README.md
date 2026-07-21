# Backend Setup Guide

## 1. Create and activate a virtual environment

On Windows PowerShell:

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

## 2. Install Python dependencies

```powershell
pip install -r requirements.txt
```

## 3. Configure the database credentials

Edit the settings in `flaskr/config.py` if your MySQL username, password, or database name are different:

```python
DB_CONFIG = {
    "host": "localhost",
    "user": "root",
    "password": "password",
    "database": "portfolio_db",
}
```

## 4. Create the MySQL database and table

Run the setup script:

```powershell
python .\flaskr\scripts\create_db.py
```

This will create the `portfolio_db` database and the `stocks` table.

## 5. Start the Flask backend

From the project root, run:

```powershell
flask run
```

The server should start on:

```text
http://127.0.0.1:5000
```

## 6. Interact with the app
You can launch and/or modify the interaction script from the scripts folder to send requests to the backend. This is useful for testing the API manually without needing a separate front-end client.

Run the script from the project root with:

```powershell
python .\flaskr\scripts\send_request.py
```