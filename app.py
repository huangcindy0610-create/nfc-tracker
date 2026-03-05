import os
import re
import psycopg2
from psycopg2 import extras
from flask import Flask, request, render_template_string, jsonify
from datetime import datetime, timedelta
import google.generativeai as genai
from PIL import Image

app = Flask(__name__)

# --- 1. 初始化與環境變數 ---
DATABASE_URL = os.environ.get('DATABASE_URL')
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")

if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel("gemini-1.5-flash")

def get_db_connection():
    return psycopg2.connect(DATABASE_URL, sslmode='require')

def init_db():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('''
        CREATE TABLE IF NOT EXISTS NFCtag (
            id SERIAL PRIMARY KEY,
            serialno TEXT NOT NULL,
            starttime TIMESTAMP,
            endtime TIMESTAMP
        )
    ''')
    conn.commit()
    cur.close()
    conn.close()

# --- 2. 路由定義 (確保唯一性) ---

# 首頁 (驗證伺服器是否活著)
@app.route('/')
def home():
    return "<h1>NFC 系統運行中</h1><p>查看資料請至: <a href='/view'>/view</a></p>"

# 路由 1：顯示詳細清單 (HTML 頁面)
@app.route('/view')
def view_page():
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=extras.DictCursor)
    cur.execute("SELECT * FROM NFCtag ORDER BY id DESC")
    rows = cur.fetchall()
    cur.close()
    conn.close()

    data = []
    for r in rows:
        duration = "-"
        color = "#fff9c4"
        if r['endtime']:
            diff = r['endtime'] - r['starttime']
            duration = str(diff).split(".")[0] # 格式化時間差
            color = "#c8e6c9"
        data.append({
            "id": r['id'], "sno": r['serialno'],
            "start": r['starttime'].strftime('%Y-%m-%d %H:%M:%S'),
            "end": r['endtime'].strftime('%Y-%m-%d %H:%M:%S') if r['endtime'] else "進行中",
            "duration": duration, "color": color
        })

    html = '''
    <html><body style="font-family:sans-serif; padding:20px;">
        <h2>♻️ NFC 回收監控清單</h2>
        <table border="1" style="width:100%; border-collapse:collapse; text-align:center;">
            <tr style="background:#333; color:white;"><th>ID</th><th>序號</th><th>開始</th><th>結束</th><th>時長</th></tr>
            {% for item in data %}
            <tr style="background-color: {{ item.color }};">
                <td>{{ item.id }}</td><td>{{ item.sno }}</td><td>{{ item.start }}</td><td>{{ item.end }}</td><td>{{ item.duration }}</td>
            </tr>
            {% endfor %}
        </table>
        <br><a href="/stat">查看統計圖表</a>
    </body></html>
    '''
    return render_template_string(html, data=data)

# 路由 2：NFC 刷卡更新 (由硬體/手機呼叫)
@app.route('/nfc_update')
def nfc_update():
    sno = request.args.get('sno')
    if not sno: return "Missing sno", 400
    now = datetime.now()
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=extras.DictCursor)
    cur.execute("SELECT id FROM NFCtag WHERE serialno = %s AND endtime IS NULL", (sno,))
    row = cur.fetchone()
    if row:
        cur.execute("UPDATE NFCtag SET endtime = %s WHERE id = %s", (now, row['id']))
        msg = "Checkout OK"
    else:
        cur.execute("INSERT INTO NFCtag (serialno, starttime) VALUES (%s, %s)", (sno, now))
        msg = "Checkin OK"
    conn.commit()
    cur.close()
    conn.close()
    return msg

# 路由 3：統計 API (給圖表用)
@app.route('/api/weekly_stats')
def weekly_stats():
    # ... 這裡放你原本計算 weekly_hours 的邏輯 ...
    return jsonify({"status": "success", "weekly_hours": [0,0,0,0,0,0,0]})

# --- 3. 啟動伺服器 ---
if __name__ == '__main__':
    init_db()
    port = int(os.environ.get('PORT', 8000))
    app.run(host='0.0.0.0', port=port)
