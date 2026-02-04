# Connect2Give 🌍🤝

[![Live Demo](https://img.shields.io/badge/LIVE_DEMO-Click_Here-success?style=for-the-badge&logo=pythonanywhere)](https://vaibhav0120.pythonanywhere.com/)


[![Django](https://img.shields.io/badge/Django-5.2-092E20?style=for-the-badge&logo=django)](https://www.djangoproject.com/)
[![Python](https://img.shields.io/badge/Python-3.10-3776AB?style=for-the-badge&logo=python)](https://www.python.org/)
[![Bootstrap](https://img.shields.io/badge/Bootstrap-5-7952B3?style=for-the-badge&logo=bootstrap)](https://getbootstrap.com/)

**Connect2Give** is a comprehensive food donation platform connecting Restaurants, NGOs, and Volunteers to efficiently redistribute surplus food. It features real-time routing, role-based dashboards, and a tiered verification system.

## 🚀 Live Demo
**Watch it live here:** [https://vaibhav0120.pythonanywhere.com/](https://vaibhav0120.pythonanywhere.com/)

---

## 🌟 Core Workflow
1.  **Restaurants** post surplus food donations.
2.  **Volunteers** accept pickups, get optimized routes, and collect food.
3.  **Volunteers** deliver to the nearest NGO Camp.
4.  **NGOs** verify the delivery digitally and rate the volunteer.

**Donation Lifecycle:**
`PENDING` → `ACCEPTED` → `COLLECTED` → `VERIFICATION_PENDING` → `DELIVERED`

---

## 👥 Roles & Features

### 🍽️ Restaurants
*   **Donation Management:** Post food details, quantity, and pickup location.
*   **Web Push Notifications:** Notify nearby volunteers instantly.
*   **Impact Tracking:** View history of contributions.

### 🚴 Volunteers
*   **Smart Routing:** Route optimization for multi-stop pickups (via Leaflet & OSRM).
*   **Camp Locator:** Auto-suggests the nearest active donation camp.
*   **Gamification:** Earn badges and climb the leaderboard.
*   **Live Tracking:** Share real-time location with NGOs during deliveries.

### 🏢 NGOs
*   **Camp Management:** Create and manage donation collection points.
*   **Digital Verification:** Verify deliveries with a click (no paperwork).
*   **Volunteer Management:** Register and manage volunteer accounts.
*   **Live Monitoring:** Track volunteer locations on an interactive map.

---

## 🛠️ Tech Stack
*   **Backend:** Django 5.2, Django REST Framework
*   **Database:** MySQL (Production), SQLite (Dev)
*   **Auth:** Django Allauth (Google OAuth)
*   **Maps & Routing:** Leaflet.js, OpenStreetMap, Leaflet Routing Machine, GeoPy
*   **Real-time:** Django Channels (WebSocket capabilities), Web Push API
*   **Frontend:** HTML5, CSS3, JavaScript (ES6+), Bootstrap
*   **Deployment:** PythonAnywhere

---

## ⚙️ Local Installation

**1. Clone the repository**
```bash
git clone https://github.com/Vaibhavsh0120/Connect2Give.git
cd Connect2Give
```

**2. Setup Virtual Environment**
```bash
# Windows
python -m venv venv
.\venv\Scripts\activate

# Mac/Linux
python3 -m venv venv
source venv/bin/activate
```

**3. Install Dependencies**
```bash
pip install -r requirements.txt
```

**4. Configure Environment**
Copy `.env.example` to `.env` and configure your keys (Database, Google OAuth, Email).

**5. Database Setup**
```bash
python manage.py migrate
python manage.py createsuperuser
```

**6. Run Server**
```bash
python manage.py runserver
```
Visit `http://127.0.0.1:8000`

---

## 🧪 Deployment (PythonAnywhere)
This project is configured for deployment on PythonAnywhere.
1.  Clone repo to PythonAnywhere.
2.  Create virtualenv with Python 3.10.
3.  Install requirements.txt
4.  Configure Web Tab (Static/Media mappings are crucial).
5.  Set environment variables in `.env`.

---

## 📜 License
This project is built for educational and social impact purposes.
