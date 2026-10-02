"""
GrantAI Engine API - FastAPI שעוטף את מנוע הסריקה V5
Base44 קורא לזה דרך HTTP, לא מריץ Python ישירות

Endpoints:
GET  / - health
POST /scan?priority=P1 - מריץ סריקה
GET  /results - מחזיר results.json
GET  /report - מחזיר scan_report.md + html
"""

import os
import json
import subprocess
import sys
from pathlib import Path
from datetime import datetime
from fastapi import FastAPI, Query, BackgroundTasks
from fastapi.responses import JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="GrantAI Engine V5", version="5.0")

# CORS ל-Base44
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

RESULTS_PATH = Path("/app/results.json")
if not RESULTS_PATH.exists():
    RESULTS_PATH = Path("/mnt/data/results.json")

SCAN_STATUS = {"running": False, "last_scan": None, "last_priority": None}

@app.get("/")
def health():
    return {
        "status": "ok",
        "engine": "GrantAI V5 Hardened",
        "version": "5.0",
        "playwright": True,
        "serpapi": bool(os.getenv("SERPAPI_API_KEY")),
        "last_scan": SCAN_STATUS["last_scan"]
    }

def run_scan_task(priority: str):
    SCAN_STATUS["running"] = True
    try:
        # הרצת הסורק המחוסן
        cmd = [sys.executable, "/app/grantai_runner_v5_hardened.py", "--priority", priority]
        # אם הקבצים ב-/mnt/data
        if not Path("/app/grantai_runner_v5_hardened.py").exists():
            cmd = [sys.executable, "/mnt/data/grantai_runner_v5_hardened.py", "--priority", priority]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)  # 10 דקות max
        print(result.stdout)
        print(result.stderr)
        
        # יצירת דוח
        try:
            report_cmd = [sys.executable, "/app/grantai_report_v2.py"]
            if not Path("/app/grantai_report_v2.py").exists():
                report_cmd = [sys.executable, "/mnt/data/grantai_report_v2.py"]
            subprocess.run(report_cmd, capture_output=True, timeout=30)
        except:
            pass
            
    except Exception as e:
        print(f"Scan failed: {e}")
    finally:
        SCAN_STATUS["running"] = False
        SCAN_STATUS["last_scan"] = datetime.now().isoformat()
        SCAN_STATUS["last_priority"] = priority

@app.post("/scan")
def trigger_scan(
    background_tasks: BackgroundTasks,
    priority: str = Query(default="P1", description="P1 / P2 / P3 / ALL")
):
    if SCAN_STATUS["running"]:
        return JSONResponse({"status": "already_running", "message": "סריקה כבר רצה"}, status_code=409)
    
    background_tasks.add_task(run_scan_task, priority)
    return {"status": "started", "priority": priority, "message": f"סריקת {priority} התחילה ברקע, בדוק /results בעוד 2-3 דקות"}

@app.get("/results")
def get_results():
    if not RESULTS_PATH.exists():
        return JSONResponse({"status": "no_results", "message": "עדיין אין תוצאות, הרץ POST /scan"}, status_code=404)
    try:
        data = json.loads(RESULTS_PATH.read_text(encoding="utf-8"))
        return data
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

@app.get("/report")
def get_report():
    # מחזיר גם md וגם html אם קיימים
    md_path = Path("/app/scan_report.md")
    html_path = Path("/app/scan_report.html")
    if not md_path.exists():
        md_path = Path("/mnt/data/scan_report.md")
        html_path = Path("/mnt/data/scan_report.html")
    
    if not md_path.exists():
        return JSONResponse({"status": "no_report"}, status_code=404)
    
    return {
        "markdown": md_path.read_text(encoding="utf-8"),
        "html_exists": html_path.exists(),
        "scanned_at": datetime.now().isoformat()
    }

@app.get("/report.html")
def get_report_html():
    html_path = Path("/app/scan_report.html")
    if not html_path.exists():
        html_path = Path("/mnt/data/scan_report.html")
    if not html_path.exists():
        return JSONResponse({"status": "no_report"}, status_code=404)
    return FileResponse(html_path, media_type="text/html")

# Cron endpoint - Base44 או Render Cron יקראו לזה כל יום 06:00
@app.post("/cron/daily")
def cron_daily(background_tasks: BackgroundTasks):
    return trigger_scan(background_tasks, priority="P1")

@app.post("/cron/full")
def cron_full(background_tasks: BackgroundTasks):
    return trigger_scan(background_tasks, priority="ALL")
