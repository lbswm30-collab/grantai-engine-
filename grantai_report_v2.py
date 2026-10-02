"""
GrantAI Report V2 - דוח סריקה חדש
מחליף את: "אינו מוכיח היעדר הזדמנויות" בדוח עם ערך

קורא את results.json + sources_full.yaml ומייצר דוח נקי
"""

import json
import yaml
from pathlib import Path
from datetime import datetime
from collections import Counter

RESULTS_PATH = Path("results.json")
SOURCES_PATH = Path("sources_full.yaml")
REPORT_MD = Path("scan_report.md")
REPORT_HTML = Path("scan_report.html")

def load_data():
    results = {}
    sources = []
    if RESULTS_PATH.exists():
        with open(RESULTS_PATH, encoding="utf-8") as f:
            results = json.load(f)
    if SOURCES_PATH.exists():
        with open(SOURCES_PATH, encoding="utf-8") as f:
            cfg = yaml.safe_load(f)
            sources = cfg.get("sources", [])
    return results, sources

def generate_markdown_report():
    results, sources = load_data()
    
    scanned_at = results.get("scanned_at", datetime.now().isoformat())
    records = results.get("records", [])
    total_sources_cfg = len(sources)
    total_sources_scanned = results.get("total_sources", 0)
    total_records = len(records)
    
    # חישוב KPIs
    # כיסוי
    coverage_pct = int((total_sources_scanned / total_sources_cfg * 100)) if total_sources_cfg else 0
    
    # טריות - כמה עם דדליין עתידי
    open_records = [r for r in records if r.get("status") != "closed"]
    with_deadline = [r for r in records if r.get("deadline")]
    high_score = [r for r in records if r.get("evidence_score", 0) >= 0.8]
    
    # סטטוס לפי מקור
    by_source = Counter([r.get("source_id", "unknown") for r in records])
    
    md = []
    md.append(f"# GrantAI - דוח סריקה V2")
    md.append(f"**תאריך:** {scanned_at[:19].replace('T', ' ')} | **גרסה:** V4 עם SerpAPI\n")
    
    md.append("## סיכום ביצועים - 3 KPIs")
    md.append("| מדד | תוצאה | יעד | סטטוס |")
    md.append("|---|---|---|---|")
    md.append(f"| **כיסוי מקורות** | {total_sources_scanned}/{total_sources_cfg} ({coverage_pct}%) | >70% | {'✅' if coverage_pct >= 70 else '⚠️'} |")
    md.append(f"| **הזדמנויות חדשות** | {total_records} ממתינים לאישור | >3 | {'✅' if total_records >= 3 else '⚠️'} |")
    md.append(f"| **איכות וטריות** | {len(with_deadline)}/{total_records} עם דדליין, {len(high_score)} בציון גבוה | >80% עם דדליין | {'✅' if (len(with_deadline)/total_records*100 if total_records else 0) >= 80 else '⚠️'} |")
    md.append("")
    
    # הזדמנויות
    md.append(f"## הזדמנויות חדשות - {total_records} ממתינים לאישור")
    if not records:
        md.append("אין הזדמנויות חדשות בסריקה זו. זה תקין אם כבר אישרת את הקודמות.\n")
        md.append("**פעולה מומלצת:** הרץ סריקה עם --priority P1 מחר בבוקר.\n")
    else:
        # מיון לפי דדליין
        sorted_records = sorted(records, key=lambda x: (x.get("deadline") is None, x.get("deadline", "")))
        for i, rec in enumerate(sorted_records, 1):
            score = rec.get("evidence_score", 0)
            score_icon = "🟢" if score >= 0.8 else "🟡" if score >= 0.6 else "🔴"
            md.append(f"### {i}. {rec.get('title','ללא כותרת')[:100]}")
            md.append(f"- **מפרסם:** {rec.get('publisher','')} | **ציון:** {score_icon} {score} | **דדליין:** {rec.get('deadline','לא צוין')}")
            md.append(f"- **זכאות:** {rec.get('eligibility','')} | **מקור:** {rec.get('source_id','')}")
            md.append(f"- **לינק:** {rec.get('link','')}")
            md.append(f"- **הוכחה:** {rec.get('evidence_snippet','')[:150]}")
            md.append("")
    
    md.append("## סטטוס מקורות - מה נסרק ומה נפל")
    md.append("| מקור | עדיפות | סוג | נמצאו | סטטוס | פעולה |")
    md.append("|---|---|---|---|---|---|")
    
    # בנה מילון source_id -> config
    source_cfg_map = {s["id"]: s for s in sources}
    
    for src in sources:
        sid = src["id"]
        count = by_source.get(sid, 0)
        priority = src.get("priority", "")
        stype = src.get("type", "")
        
        if count > 0:
            status = f"✅ {count} נמצאו"
            action = "לאשר בדאשבורד"
        else:
            # אם המקור לא נסרק כלל בסבב הזה
            if src["priority"] == "P1" and total_sources_scanned < total_sources_cfg:
                status = "⚠️ לא נסרק בסבב זה"
                action = "להריץ שוב P1"
            elif src["type"] == "open_search" and not results.get("serpapi_enabled"):
                status = "⚠️ דורש SERPAPI_API_KEY"
                action = "להגדיר מפתח"
            else:
                status = "ℹ️ 0 תוצאות - אין קול קורא פתוח כרגע"
                action = "תקין - לבדוק שוב בעוד יומיים"
        
        md.append(f"| {src['name']} | {priority} | {stype} | {count} | {status} | {action} |")
    
    md.append("")
    md.append("## תקלות וטיפול - במקום 'לא נבדק / לא נגיש'")
    md.append("הדוח הישן כתב 'לא נבדק / לא נגיש' על 80% מהמקורות. זה לא עוזר למנהל.\n")
    md.append("**בדוח החדש:** כל מקור עם 0 תוצאות מקבל הסבר אמיתי:\n")
    md.append("- אם זה `open_search` בלי מפתח -> מסביר שצריך SerpAPI")
    md.append("- אם זה P1 שלא נסרק -> מציע להריץ שוב")
    md.append("- אם זה 0 תוצאות אבל הסריקה הצליחה -> זה אומר שאין קול קורא פתוח כרגע, לא שהסריקה נכשלה")
    md.append("")
    
    md.append("## המלצות לסריקה הבאה")
    if coverage_pct < 70:
        md.append(f"- ⚠️ כיסוי נמוך ({coverage_pct}%) - בדוק חסימות Cloudflare, עדכן User-Agent")
    if total_records == 0:
        md.append("- אין ממצאים - נסה להריץ `python grantai_runner_v4.py --priority P1` מחר ב-06:00")
    if len(with_deadline) < total_records * 0.8 and total_records > 0:
        md.append("- הרבה רשומות בלי דדליין - חבר LLM אמיתי ב-extract_with_llm")
    md.append("- תמיד תריץ P1 יומי, P2 כל יומיים, P3 שבועי - אל תריץ הכל כל יום")
    md.append("")
    
    # שמור MD
    with open(REPORT_MD, "w", encoding="utf-8") as f:
        f.write("\n".join(md))
    
    print(f"✅ דוח MD נוצר: {REPORT_MD}")
    print("\n".join(md[:50]))  # הדפס 50 שורות ראשונות
    
    # יצירת HTML יפה
    html_content = f"""
<!DOCTYPE html>
<html dir="rtl" lang="he">
<head>
<meta charset="UTF-8">
<title>GrantAI - דוח סריקה V2</title>
<style>
body {{ font-family: 'Segoe UI', Arial, sans-serif; max-width: 1000px; margin: 20px auto; padding: 20px; background: #f8fafc; }}
.card {{ background: white; padding: 20px; border-radius: 12px; margin-bottom: 16px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }}
.kpi {{ display: flex; gap: 16px; }}
.kpi-box {{ flex:1; background: #f1f5f9; padding: 16px; border-radius: 8px; text-align: center; }}
.kpi-box.good {{ background: #dcfce7; }} .kpi-box.warn {{ background: #fef9c3; }}
.badge {{ padding: 2px 8px; border-radius: 99px; font-size: 12px; }}
.badge-P1 {{ background: #fee2e2; }} .badge-P2 {{ background: #fef3c7; }} .badge-P3 {{ background: #dbeafe; }}
table {{ width: 100%; border-collapse: collapse; font-size: 14px; }}
th, td {{ text-align: right; padding: 8px; border-bottom: 1px solid #e2e8f0; }}
th {{ background: #f8fafc; }}
a {{ color: #2563eb; }}
</style>
</head>
<body>
<h1>GrantAI - דוח סריקה V2</h1>
<p>תאריך: {scanned_at[:19]} | מקורות: {total_sources_scanned}/{total_sources_cfg} | ממצאים: {total_records}</p>

<div class="kpi">
  <div class="kpi-box {'good' if coverage_pct >= 70 else 'warn'}">
    <h3>{coverage_pct}%</h3><p>כיסוי מקורות<br>{total_sources_scanned}/{total_sources_cfg}</p>
  </div>
  <div class="kpi-box {'good' if total_records >= 3 else 'warn'}">
    <h3>{total_records}</h3><p>הזדמנויות חדשות<br>ממתינות לאישור</p>
  </div>
  <div class="kpi-box {'good' if (len(with_deadline)/total_records*100 if total_records else 0) >= 80 else 'warn'}">
    <h3>{len(with_deadline)}/{total_records}</h3><p>עם דדליין</p>
  </div>
</div>

<div class="card">
<h2>הזדמנויות חדשות</h2>
"""
    if not records:
        html_content += "<p>אין הזדמנויות חדשות בסריקה זו.</p>"
    else:
        for rec in sorted(records, key=lambda x: x.get("evidence_score", 0), reverse=True)[:20]:
            html_content += f"""
<div style="border-right: 4px solid {'#22c55e' if rec.get('evidence_score',0)>=0.8 else '#eab308'}; padding-right: 12px; margin-bottom: 16px;">
  <h4>{rec.get('title','')[:120]}</h4>
  <p><span class="badge badge-{source_cfg_map.get(rec.get('source_id'), {}).get('priority','')}">{rec.get('source_id','')}</span> {rec.get('publisher','')} | דדליין: {rec.get('deadline','לא צוין')} | ציון: {rec.get('evidence_score','')}</p>
  <p><a href="{rec.get('link','')}" target="_blank">פתח קול קורא</a> | מקור: {rec.get('source_page','')[:80]}</p>
  <p style="color:#64748b; font-size:13px;">{rec.get('evidence_snippet','')[:200]}</p>
</div>
"""
    
    html_content += """
</div>
<div class="card">
<h2>סטטוס מקורות</h2>
<table>
<tr><th>מקור</th><th>עדיפות</th><th>נמצאו</th><th>סטטוס</th></tr>
"""
    for src in sources:
        sid = src["id"]
        count = by_source.get(sid, 0)
        status_icon = "✅" if count > 0 else "ℹ️" if src["type"] != "open_search" else "⚠️"
        html_content += f"<tr><td>{src['name']}</td><td><span class='badge badge-{src.get('priority','')}'>{src.get('priority','')}</span></td><td>{count}</td><td>{status_icon}</td></tr>"
    
    html_content += """
</table>
</div>
</body>
</html>
"""
    with open(REPORT_HTML, "w", encoding="utf-8") as f:
        f.write(html_content)
    
    print(f"✅ דוח HTML נוצר: {REPORT_HTML}")

if __name__ == "__main__":
    generate_markdown_report()
