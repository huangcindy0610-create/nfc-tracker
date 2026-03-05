import os
from flask import Flask, render_template_string, jsonify
# ... 其他 import ...

app = Flask(__name__)

# 首頁 (測試用)
@app.route('/')
def home():
    return "<h1>伺服器運行中</h1><p>請訪問 <a href='/view'>/view</a> 查看清單</p>"

# 你的主要檢視頁面
@app.route('/view')
def view():
    # 這裡放你原本顯示表格的邏輯
    return "這裡是 View 頁面 (資料庫連接成功)"

# 如果你有 API 需求，請換個名字，不要再用 /view
@app.route('/api/stats')
def get_stats():
    return jsonify({"status": "ok"})

if __name__ == '__main__':
    # 這裡確保資料庫有初始化
    # init_db() 
    port = int(os.environ.get('PORT', 8000))
    app.run(host='0.0.0.0', port=port)
