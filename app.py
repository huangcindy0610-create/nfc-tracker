# 這是應該放在 recycling-project-1 的正確程式碼
import os
import psycopg2
from psycopg2 import extras
from flask import Flask, request, render_template_string
from datetime import datetime

app = Flask(__name__)
DATABASE_URL = os.environ.get('DATABASE_URL')

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

# 路由 1: 讓 NFC 感應器更新資料
@app.route('/nfc_update', methods=['GET'])
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
        msg = f"OK: {sno} Checked Out"
    else:
        cur.execute("INSERT INTO NFCtag (serialno, starttime, endtime) VALUES (%s, %s, NULL)", (sno, now))
        msg = f"OK: {sno} Checked In"
    conn.commit()
    cur.close()
    conn.close()
    return msg

# 路由 2: 提供數據介面 (這就是你要找的 /view)
@app.route('/view')
def view():
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=extras.DictCursor)
    cur.execute("SELECT id, serialno, starttime, endtime FROM NFCtag ORDER BY id DESC")
    rows = cur.fetchall()
    
    data = []
    for r in rows:
        diff_str = "-"
        if r['endtime']:
            diff = r['endtime'] - r['starttime']
            m, s = divmod(int(diff.total_seconds()), 60)
            h, m = divmod(m, 60)
            diff_str = f"{h:02}:{m:02}:{s:02}"
            
        data.append({
            "id": r['id'], "sno": r['serialno'], 
            "start": r['starttime'].strftime('%Y-%m-%d %H:%M:%S') if r['starttime'] else "-",
            "end": r['endtime'].strftime('%Y-%m-%d %H:%M:%S') if r['endtime'] else "In Progress...", 
            "duration": diff_str
        })
    cur.close()
    conn.close()
    
    # 這裡回傳簡單的 HTML 或 JSON 供前端讀取
    return {"status": "success", "data": data} 

if DATABASE_URL:
    with app.app_context():
        try:
            init_db()
        except:
            pass

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8000))
    app.run(host='0.0.0.0', port=port)
