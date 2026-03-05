import os
import psycopg2
from psycopg2 import extras
from flask import Flask, request, jsonify
from datetime import datetime

app = Flask(__name__)
DATABASE_URL = os.environ.get('DATABASE_URL')

def get_db_connection():
    # 務必確認 Render 的環境變數中有設定 DATABASE_URL
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

# 這就是 NFC 感應器要呼叫的網址
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

# 這就是你的前端專案要抓資料的網址 (JSON 格式)
@app.route('/view')
def view():
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=extras.DictCursor)
        cur.execute("SELECT id, serialno, starttime, endtime FROM NFCtag ORDER BY id DESC")
        rows = cur.fetchall()
        
        data = []
        for r in rows:
            data.append({
                "id": r['id'],
                "sno": r['serialno'],
                "start": r['starttime'].strftime('%Y-%m-%d %H:%M:%S') if r['starttime'] else None,
                "end": r['endtime'].strftime('%Y-%m-%d %H:%M:%S') if r['endtime'] else None
            })
        cur.close()
        conn.close()
        return jsonify(data) # 回傳 JSON，讓前端長條圖好處理
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# 啟動時初始化
if DATABASE_URL:
    with app.app_context():
        try: init_db()
        except: pass

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8000))
    app.run(host='0.0.0.0', port=port)
