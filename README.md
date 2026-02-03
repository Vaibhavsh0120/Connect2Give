# Connect2Give

Connect2Give is a Django web app that connects restaurants, NGOs, and volunteers to move surplus food to donation camps with maps, routing, and verification.

## Core Workflow
- Restaurants post a donation.
- Volunteers accept, collect, and deliver.
- NGOs verify deliveries and rate volunteers.

Donation statuses used in the system:
`PENDING -> ACCEPTED -> COLLECTED -> VERIFICATION_PENDING -> DELIVERED`

## Roles And Features
### Restaurants
- Post surplus food donations and track their status.
- View active NGO camps on a map.
- Send web push notifications to subscribed volunteers when a new donation is posted.

### Volunteers
- Accept pickups (up to 10 active at a time) and mark items collected.
- Get an optimized pickup route and a nearest-camp delivery route.
- See delivery history, verification status, and leaderboard ranking.
- Share live location (opt-in) so NGOs can monitor active deliveries.

### NGOs
- Create and manage donation camps.
- Register volunteers and email temporary credentials (volunteers must change password on first login).
- Verify delivered donations and provide ratings.
- View live volunteer locations on a map.

Note: Public volunteer sign-up is disabled. Volunteers are created by NGOs inside the dashboard.

## Tech Stack
- Django 5.2.7
- Django REST Framework
- MySQL (via PyMySQL)
- django-allauth (Google OAuth)
- django-environ (environment config)
- django-webpush and pywebpush (browser push)
- Leaflet + OpenStreetMap + Leaflet Routing Machine (OSRM routing)
- GeoPy (distance and routing estimates)

## Local Setup
1. Clone the repository.

```bash
git clone https://github.com/Vaibhavsh0120/Connect2Give.git
cd Connect2Give
```

2. Create a `.env` file.

```bash
# From the project root
cp .env.example .env
```

3. Create the MySQL database.

```sql
CREATE DATABASE connect2give_db;
```

4. Create and activate a virtual environment.

```bash
# Windows (PowerShell)
python -m venv connect
.\connect\Scripts\Activate.ps1

# Windows (cmd.exe)
python -m venv connect
.\connect\Scripts\activate.bat

# macOS/Linux
python3 -m venv connect
source connect/bin/activate
```

5. Install dependencies.

```bash
pip install -r requirements.txt
```

6. Run migrations.

```bash
python manage.py migrate
```

7. Create an admin user (optional).

```bash
python manage.py createsuperuser
```

8. Run the development server.

```bash
python manage.py runserver
```

Open `http://127.0.0.1:8000/`.

## Environment Variables
The app reads configuration from `.env`. Required values are listed below.

| Variable | Required | Description |
| --- | --- | --- |
| `SECRET_KEY` | Yes | Django secret key. |
| `DEBUG` | Yes | `True` or `False`. |
| `ALLOWED_HOSTS` | Yes | Comma-separated list, for example `localhost,127.0.0.1`. |
| `DB_NAME` | Yes | MySQL database name. |
| `DB_USER` | Yes | MySQL username. |
| `DB_PASSWORD` | Yes | MySQL password. |
| `DB_HOST` | Yes | MySQL host. |
| `DB_PORT` | Yes | MySQL port (default `3306`). |
| `EMAIL_BACKEND` | No | Django email backend. Use SMTP in production or `django.core.mail.backends.console.EmailBackend` in dev. |
| `EMAIL_HOST` | No | SMTP host (Gmail default is `smtp.gmail.com`). |
| `EMAIL_PORT` | No | SMTP port (587 for TLS). |
| `EMAIL_USE_TLS` | No | `True` or `False`. |
| `EMAIL_HOST_USER` | No | SMTP username. |
| `EMAIL_HOST_PASSWORD` | No | SMTP password or app password. |
| `DEFAULT_FROM_EMAIL` | No | Default From address. |
| `GOOGLE_OAUTH_CLIENT_ID` | No | Google OAuth client id. |
| `GOOGLE_OAUTH_CLIENT_SECRET` | No | Google OAuth client secret. |
| `VAPID_PUBLIC_KEY` | No | Web push public key. |
| `VAPID_PRIVATE_KEY` | No | Web push private key. |
| `VAPID_ADMIN_EMAIL` | No | Contact email for VAPID claims. |

## Optional Setup
### Google OAuth
Set the Google OAuth variables above and add this redirect URI in Google Cloud:
`http://localhost:8000/accounts/google/login/callback/`

### Web Push Notifications
Generate VAPID keys and add them to `.env`.

```bash
python generate_keys.py
```

Note: Service workers and push notifications require HTTPS in production. They work on `localhost` without HTTPS.

## Project Structure
```text
Connect2Give/
|-- food_donation_project/        # Django project settings and URLs
|-- portal/                       # Main Django app
|   |-- views/                    # Auth, NGO, restaurant, volunteer, API views
|   |-- utils/                    # Route optimization logic
|   |-- tests/                    # App tests
|-- templates/                    # Global templates (auth, NGO, restaurant, volunteer, emails)
|-- static/                       # Static assets (CSS, JS, images)
|-- media/                        # User uploads (created at runtime)
|-- staticfiles/                  # Collected static files (created by collectstatic)
|-- manage.py
|-- requirements.txt
|-- generate_keys.py
|-- .env.example
|-- README.md
```

## API Endpoints (Selected)
Most endpoints require authentication and a role-appropriate account.

- `POST /api/register/` Register a user.
- `POST /api/login/` Obtain an auth token.
- `POST /api/save-webpush-subscription/` Save a volunteer web push subscription.
- `POST /api/calculate-pickup-route/` Get an optimized multi-stop pickup route.
- `POST /api/calculate-delivery-route/` Get a delivery route to the nearest camp.
- `GET /api/volunteer-stats/` Volunteer dashboard stats.
- `GET /api/nearest-camp/` Nearest camp for delivery.
- `POST /api/update-volunteer-location/` Update live volunteer location.
- `GET /api/get-volunteers-locations/` NGO access to volunteer locations.

## Troubleshooting
- MySQL connection errors usually mean the server is not running or credentials in `.env` are wrong.
- If static files are missing in production, run `python manage.py collectstatic`.
- Password reset and volunteer invite emails require valid SMTP settings in `.env`.

## Testing
Run unit tests with:

```bash
python manage.py test
```

Note: Tests use SQLite automatically (see `food_donation_project/settings.py`).

## Contributing
1. Fork the repo.
2. Create a feature branch.
3. Commit your changes.
4. Open a pull request.

## License
This project is built for educational and social impact purposes.
