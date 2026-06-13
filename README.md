# SafeSight PPE Detection System - Django Backend

Django REST API backend for the SafeSight workplace safety monitoring system. This backend handles PPE detection using YOLOv11, WebSocket streaming for real-time monitoring, worker management, violation tracking, and reporting.

## Features

- **PPE Detection**: YOLOv11-based detection of Gloves, Helmet, Shoes, and Vest
- **WebSocket Streaming**: Real-time detection via WebSocket at `ws://localhost:8080/ws/detect/`
- **Worker Management**: CRUD operations for workers with PPE requirements
- **Violation Tracking**: Record and manage PPE violations with images
- **Alert System**: Configurable alert thresholds and delivery methods
- **Reports**: Summary, violation, compliance, and worker reports with CSV/JSON export
- **Authentication**: Simple username/password authentication

## Requirements

- Python 3.9+
- Virtual environment

## Installation

1. **Create and activate virtual environment:**
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Run migrations:**
   ```bash
   python manage.py migrate
   ```

4. **Create a superuser:**
   ```bash
   python manage.py createsuperuser
   ```

## Running the Server

### Development Server (HTTP + WebSocket)

```bash
# Run with Daphne for WebSocket support
daphne -b 0.0.0.0 -p 8000 config.asgi:application
```

Or for HTTP-only development:

```bash
python manage.py runserver 0.0.0.0:8000
```

### Production

Use Daphne or Gunicorn with systemd/supervisor for process management.

## API Endpoints

### Authentication
- `POST /api/auth/register/` - User registration
- `POST /api/auth/login/` - User login
- `POST /api/auth/logout/` - User logout
- `GET /api/auth/profile/` - Get current user profile

### Detection
- `POST /api/detection/upload/` - Upload image for PPE detection
- `GET /api/detection/records/` - Get detection records
- `GET /api/detection/violations/` - Get violation records
- `GET /api/detection/sessions/` - List detection sessions
- `POST /api/detection/sessions/create/` - Create new session
- `GET /api/detection/health/` - Health check (verifies model loaded)

### WebSocket
- `ws://localhost:8000/ws/detect/` - Real-time detection streaming

### Workers
- `GET /api/workers/` - List all workers
- `POST /api/workers/` - Add new worker
- `GET /api/workers/{id}/` - Get worker details
- `PUT /api/workers/{id}/` - Update worker
- `DELETE /api/workers/{id}/` - Delete worker
- `GET /api/workers/stats/` - Worker statistics

### Alerts
- `GET /api/alerts/config/` - Get alert configurations
- `POST /api/alerts/config/` - Create alert config
- `GET /api/alerts/history/` - Get alert history
- `POST /api/alerts/test/` - Test alert system

### Reports
- `GET /api/reports/summary/` - Safety summary stats
- `GET /api/reports/violations/` - Violation records
- `GET /api/reports/compliance/` - Compliance metrics
- `POST /api/reports/export/` - Export report (CSV/JSON)

## Detection Result Format

```json
{
  "frameId": "string",
  "detected": 0,
  "compliant": 0,
  "nonCompliant": 0,
  "detections": [
    {
      "workerId": "string|null",
      "boundingBox": {"x": 0.0, "y": 0.0, "width": 0.0, "height": 0.0},
      "ppeStatus": [
        {"type": "hardHat", "status": "compliant", "lastDetected": "ISO8601"}
      ],
      "overallStatus": "compliant|partial|nonCompliant",
      "confidence": 0.0
    }
  ]
}
```

## PPE Type Mapping

| Model Class | Label         | Flutter Type    |
|-------------|---------------|-----------------|
| 0           | Gloves        | gloves          |
| 1           | Helmet        | hardHat         |
| 2           | Person        | person          |
| 3           | Shoes         | steelToedBoots  |
| 4           | Vest          | vest            |

## Configuration

The following environment variables can be set:

- `DEBUG` - Debug mode (default: True)
- `ALLOWED_HOSTS` - Comma-separated allowed hosts
- `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT` - MySQL settings
- `USE_MYSQL` - Set to 'True' to use MySQL instead of SQLite

## Testing Model Inference

```python
from detection.services import PPEModelService

# Test with an image file
result = PPEModelService.predict('test_image.jpg')
print(result.to_dict())
```

## Project Structure

```
Backend_grad/
├── config/          # Django project configuration
│   ├── settings.py  # Settings including model path, CORS, Channels
│   ├── urls.py      # Main URL configuration
│   ├── asgi.py      # ASGI config for WebSocket
│   └── wsgi.py      # WSGI config
├── authentication/  # User authentication and profiles
├── detection/       # PPE detection core logic
│   ├── services/    # YOLO model wrapper
│   └── consumers.py # WebSocket consumer
├── workers/         # Worker management
├── alerts/          # Alert configuration and history
├── reports/         # Reporting and analytics
└── media/           # Uploaded images
```
