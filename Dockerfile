# Dockerfile - GrantAI Engine - מוכן ל-Render / Railway / Fly.io / Cloud Run
FROM mcr.microsoft.com/playwright/python:v1.48.0-jammy

WORKDIR /app

# התקנת תלויות Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# העתקת קוד המנוע
COPY sources_full.yaml .
COPY grantai_runner_v5_hardened.py .
COPY grantai_report_v2.py .
COPY engine_api.py .

# תיקיית cache
RUN mkdir -p /app/cache

# חשיפת פורט
EXPOSE 8000

# הרצה
CMD ["uvicorn", "engine_api:app", "--host", "0.0.0.0", "--port", "8000"]
