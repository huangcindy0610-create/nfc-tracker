import os
import psycopg2
from psycopg2 import extras
from flask import Flask, request, render_template_string
from datetime import datetime

app = Flask(__name__)

# 獲取資料庫連線路徑 (Render 會提供 DATABASE_URL)
DATABASE_URL = os.environ.get('DATABASE_URL')

def get_db_connection():
    # 如果有 DATABASE_URL 就連 PostgreSQL，否則報錯
    if DATABASE_URL:
        conn = psycopg2.connect(DATABASE_URL, sslmode='require')
        return conn
    else:
        raise Exception("未找到 DATABASE_URL，請在 Render 設定中建立 PostgreSQL 資料庫")

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

def format_duration(seconds):
    if seconds is None: return "-"
    seconds = int(seconds)
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60
    return f"{hours:02}:{minutes:02}:{secs:02}"

@app.route('/nfc_update', methods=['GET'])
def nfc_update():
    sno = request.args.get('sno')
    if not sno: return "Missing sno", 400
    
    now = datetime.now()
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=extras.DictCursor)
    
    # 檢查是否有未結束的紀錄
    cur.execute("SELECT id FROM NFCtag WHERE serialno = %s AND endtime IS NULL", (sno,))
    row = cur.fetchone()
    
    if row:
        cur.execute("UPDATE NFCtag SET endtime = %s WHERE id = %s", (now, row['id']))
        msg = f"OK: {sno} Checked Out"
    else:
        cur.execute("INSERT INTO NFCtag (serialno, starttime, endtime) VALUES (%s, %s, NULL)", (sno, now))
        msg = f"OK: {sno} Checked In"
    
    conn.commit()
    cur.close()
    conn.close()
    return msg

@app.route('/view')
def view():
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=extras.DictCursor)
    cur.execute("SELECT id, serialno, starttime, endtime FROM NFCtag ORDER BY id DESC")
    rows = cur.fetchall()
    
    data = []
    for r in rows:
        diff_str = "-"
        color = "yellow"
        if r['endtime']:
            diff = r['endtime'] - r['starttime']
            diff_str = format_duration(diff.total_seconds())
            color = "lightgreen"
            
        data.append({
            "id": r['id'], "sno": r['serialno'], 
            "start": r['starttime'].strftime('%Y-%m-%d %H:%M:%S') if r['starttime'] else "-",
            "end": r['endtime'].strftime('%Y-%m-%d %H:%M:%S') if r['endtime'] else "In Progress...", 
            "duration": diff_str, "color": color
        })
    cur.close()
    conn.close()

    html = '''
    <html>
        <head><meta http-equiv="refresh" content="5">
        <style>
            table { width: 100%; border-collapse: collapse; font-family: sans-serif; }
            th, td { padding: 10px; border: 1px solid #ccc; text-align: center; }
        </style>
        </head>
        <body>
            <h2>NFC Tag 雲端監控清單 (PostgreSQL)</h2>
            <table>
                <tr style="background-color: #333; color: white;">
                    <th>ID</th><th>Serial No</th><th>Start Time</th><th>End Time</th><th>Duration</th>
                </tr>
                {% for item in data %}
                <tr style="background-color: {{ item.color }};">
                    <td>{{ item.id }}</td><td>{{ item.sno }}</td><td>{{ item.start }}</td>
                    <td>{{ item.end }}</td><td><b>{{ item.duration }}</b></td>
                </tr>
                {% endfor %}
            </table>
        </body>
    </html>
    '''
    return render_template_string(html, data=data)

@app.route('/stat')
def stat():
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=extras.DictCursor)
    cur.execute("SELECT starttime, endtime FROM NFCtag WHERE endtime IS NOT NULL")
    rows = cur.fetchall()
    
    total_seconds = 0
    for r in rows:
        total_seconds += (r['endtime'] - r['starttime']).total_seconds()
    
    total_time_str = format_duration(total_seconds)
    count = len(rows)
    cur.close()
    conn.close()

    html = '''
    <html>
        <head><meta http-equiv="refresh" content="5"></head>
        <body style="font-family: sans-serif; padding: 20px;">
            <h2>NFC 統計數據</h2>
            <div style="border: 2px solid #333; padding: 15px; display: inline-block;">
                <p>已完成總筆數：<span style="font-size: 1.5em; color: blue;">{{ count }}</span></p>
                <p>總累計工時：<span style="font-size: 1.5em; color: red;">{{ total_time }}</span></p>
            </div>
            <br><br><a href="/view">查看詳細清單</a>
        </body>
    </html>
    '''
    return render_template_string(html, count=count, total_time=total_time_str)

# --- 啟動邏輯修正 ---

# 建立一個函式來初始化，避免全域變數報錯導致 Gunicorn 崩潰
@app.before_request
def initialize():
    # 這裡確保只會執行一次
    if not hasattr(app, '_db_initialized'):
        init_db()
        app._db_initialized = True

if __name__ == '__main__':
    # 這是給本地測試用的
    port = int(os.environ.get('PORT', 8000))
    app.run(host='0.0.0.0', port=port)
