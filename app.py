import os
import re
import hashlib
import psycopg2
from psycopg2 import extras
from flask import Flask, request, render_template_string, jsonify
from datetime import datetime, timedelta
import google.generativeai as genai
from PIL import Image
import io

app = Flask(__name__)

# ==========================================
# 1. 設定與初始化 (AI & Database)
# ==========================================
# 資料庫連線
DATABASE_URL = os.environ.get('DATABASE_URL')
# Gemini API Key
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel("gemini-1.5-flash")

def get_db_connection():
    if DATABASE_URL:
        return psycopg2.connect(DATABASE_URL, sslmode='require')
    raise Exception("Missing DATABASE_URL")

def init_db():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('''
        CREATE TABLE IF NOT EXISTS NFCtag (
            id SERIAL PRIMARY KEY,
            serialno TEXT NOT NULL,
            starttime TIMESTAMP,
            endtime TIMESTAMP,
            xp_gained INTEGER DEFAULT 0
        )
    ''')
    conn.commit()
    cur.close()
    conn.close()

# ==========================================
# 2. 路由：NFC 與 資料顯示
# ==========================================

@app.route('/')
def index():
    return "NFC Recycling System is Running! Go to /view to see data."

@app.route('/view')
def view():
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=extras.DictCursor)
    cur.execute("SELECT * FROM NFCtag ORDER BY id DESC")
    rows = cur.fetchall()
    cur.close()
    conn.close()

    html = '''
    <html>
        <head>
            <title>NFC 監控中心</title>
            <style>
                body { font-family: sans-serif; padding: 20px; background: #f0f2f5; }
                table { width: 100%; border-collapse: collapse; background: white; }
                th, td { padding: 12px; border: 1px solid #ddd; text-align: center; }
                th { background: #333; color: white; }
                .status-in { background: #fff9c4; }
                .status-done { background: #c8e6c9; }
            </style>
        </head>
        <body>
            <h2>♻️ NFC 回收監控清單</h2>
            <table>
                <tr><th>ID</th><th>序號</th><th>開始時間</th><th>結束時間</th><th>狀態</th></tr>
                {% for r in rows %}
                <tr class="{{ 'status-done' if r.endtime else 'status-in' }}">
                    <td>{{ r.id }}</td><td>{{ r.serialno }}</td>
                    <td>{{ r.starttime.strftime('%m/%d %H:%M') if r.starttime }}</td>
                    <td>{{ r.endtime.strftime('%m/%d %H:%M') if r.endtime else '進行中...' }}</td>
                    <td>{{ '已完成' if r.endtime else '處理中' }}</td>
                </tr>
                {% endfor %}
            </table>
        </body>
    </html>
    '''
    return render_template_string(html, rows=rows)

# ==========================================
# 3. 路由：AI 辨識 (API)
# ==========================================

@app.route('/api/recognize', methods=['POST'])
def api_recognize():
    if 'file' not in request.files:
        return jsonify({"error": "No file uploaded"}), 400
    
    file = request.files['file']
    img = Image.open(file.stream)
    
    prompt = "請辨識圖中回收物材質。格式：物品: (名稱), 材質: (材質)。"
    response = model.generate_content([prompt, img])
    
    return jsonify({"result": response.text})

if __name__ == '__main__':
    init_db()
    port = int(os.environ.get('PORT', 8000))
    app.run(host='0.0.0.0', port=port)
