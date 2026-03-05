import os
import psycopg2
from psycopg2 import extras
from flask import Flask, request, render_template_string, jsonify
from datetime import datetime, timedelta

app = Flask(__name__)

# 1. 資料庫連線設定
DATABASE_URL = os.environ.get('DATABASE_URL')

def get_db_connection():
    if DATABASE_URL:
        # Render 環境下通常需要 sslmode
        conn = psycopg2.connect(DATABASE_URL, sslmode='require')
        return conn
    else:
        # 本地測試若沒設定環境變數會報錯
        raise Exception("未找到 DATABASE_URL，請在環境變數中設定")

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

# 2. 路由設定

# [功能] NFC 標籤刷入/刷出
@app.route('/nfc_update', methods=['GET'])
def nfc_update():
    sno = request.args.get('sno')
    if not sno: return "Missing sno", 400
    
    now = datetime.now()
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=extras.DictCursor)
    
    # 檢查是否有未結束的紀錄 (Check-out)
    cur.execute("SELECT id FROM NFCtag WHERE serialno = %s AND endtime IS NULL", (sno,))
    row = cur.fetchone()
    
    if row:
        cur.execute("UPDATE NFCtag SET endtime = %s WHERE id = %s", (now, row['id']))
        msg = f"OK: {sno} Checked Out"
    else:
        # 新增紀錄 (Check-in)
        cur.execute("INSERT INTO NFCtag (serialno, starttime, endtime) VALUES (%s, %s, NULL)", (sno, now))
        msg = f"OK: {sno} Checked In"
    
    conn.commit()
    cur.close()
    conn.close()
    return msg

# [頁面] 詳細清單檢視
@app.route('/view')
def view():
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=extras.DictCursor)
    cur.execute("SELECT id, serialno, starttime, endtime FROM NFCtag ORDER BY id DESC")
    rows = cur.fetchall()
    
    data = []
    for r in rows:
        diff_str = "-"
        color = "#fff9c4"  # 淺黃色 (進行中)
        if r['endtime']:
            diff = r['endtime'] - r['starttime']
            diff_str = format_duration(diff.total_seconds())
            color = "#c8e6c9"  # 淺綠色 (已完成)
            
        data.append({
            "id": r['id'], 
            "sno": r['serialno'], 
            "start": r['starttime'].strftime('%Y-%m-%d %H:%M:%S') if r['starttime'] else "-",
            "end": r['endtime'].strftime('%Y-%m-%d %H:%M:%S') if r['endtime'] else "In Progress...", 
            "duration": diff_str, 
            "color": color
        })
    cur.close()
    conn.close()

    html = '''
    <html>
        <head>
            <meta http-equiv="refresh" content="10">
            <title>NFC 監控</title>
            <style>
                body { font-family: sans-serif; background: #f4f4f9; padding: 20px; }
                table { width: 100%; border-collapse: collapse; background: white; box-shadow: 0 2px 5px rgba(0,0,0,0.1); }
                th, td { padding: 12px; border: 1px solid #ddd; text-align: center; }
                th { background-color: #333; color: white; }
                .nav { margin-bottom: 20px; }
            </style>
        </head>
        <body>
            <div class="nav">
                <a href="/stat">查看統計數據</a>
            </div>
            <h2>NFC Tag 雲端監控清單 (PostgreSQL)</h2>
            <table>
                <tr>
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

# [頁面] 數據統計與圖表介面
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
        <head>
            <title>NFC 統計</title>
            <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
        </head>
        <body style="font-family: sans-serif; padding: 20px;">
            <h2>NFC 統計數據</h2>
            <div style="border: 2px solid #333; padding: 15px; display: inline-block; margin-bottom: 20px;">
                <p>已完成總筆數：<span style="font-size: 1.5em; color: blue;">{{ count }}</span></p>
                <p>總累計工時：<span style="font-size: 1.5em; color: red;">{{ total_time }}</span></p>
            </div>
            <br>
            <a href="/view">回詳細清單</a>
            
            <div style="width: 80%; max-width: 600px; margin-top: 30px;">
                <canvas id="weeklyChart"></canvas>
            </div>

            <script>
                fetch('/api/weekly_stats')
                    .then(response => response.json())
                    .then(data => {
                        const ctx = document.getElementById('weeklyChart').getContext('2d');
                        new Chart(ctx, {
                            type: 'bar',
                            data: {
                                labels: ['週一', '週二', '週三', '週四', '週五', '週六', '週日'],
                                datasets: [{
                                    label: '本週工時 (小時)',
                                    data: data.weekly_hours,
                                    backgroundColor: 'rgba(54, 162, 235, 0.5)',
                                    borderColor: 'rgba(54, 162, 235, 1)',
                                    borderWidth: 1
                                }]
                            }
                        });
                    });
            </script>
        </body>
    </html>
    '''
    return render_template_string(html, count=count, total_time=total_time_str)

# [API] 提供圖表所需的 JSON 數據
@app.route('/api/weekly_stats')
def weekly_stats():
    try:
        today = datetime.now()
        # 取得本週一的日期 (00:00:00)
        monday = (today - timedelta(days=today.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
        
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=extras.DictCursor)
        # 只抓取有結束時間且在本週內的紀錄
        cur.execute("SELECT starttime, endtime FROM NFCtag WHERE endtime IS NOT NULL AND starttime >= %s", (monday,))
        rows = cur.fetchall()
        
        weekly_hours = [0.0] * 7
        for row in rows:
            start_dt = row['starttime']
            end_dt = row['endtime']
            
            duration_seconds = (end_dt - start_dt).total_seconds()
            weekday = start_dt.weekday() # 0=Mon, 6=Sun
            weekly_hours[weekday] += (duration_seconds / 3600.0)
            
        cur.close()
        conn.close()

        return jsonify({
            "status": "success",
            "weekly_hours": [round(h, 2) for h in weekly_hours]
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == '__main__':
    init_db()
    # Render 會自動傳入 PORT 環境變數
    port = int(os.environ.get('PORT', 8000))
    app.run(host='0.0.0.0', port=port)
