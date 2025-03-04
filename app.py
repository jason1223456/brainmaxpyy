from flask import Flask, request, jsonify
from flask_cors import CORS
import psycopg2
import requests
import json
import base64

app = Flask(__name__)
CORS(app)

# 🔹 PostgreSQL 資料庫連線設定
DB_CONFIG = {
    "dbname": "zeabur",
    "user": "root",
    "password": "MfaN1ck3P579izFWj4n8Ve6IS2d0ODwx",  # ⚠️ 修改為你的 PostgreSQL 密碼
    "host": "sfo1.clusters.zeabur.com",
    "port": "31148"
}

def get_db_connection():
    """ 建立 PostgreSQL 資料庫連線 """
    return psycopg2.connect(**DB_CONFIG)

# 🔹 使用 Base64 編碼的 Claude API Key
ENCODED_CLAUDE_API_KEY = "c2stYW50LWFwaTAzLTBUZ2JjTTVPQXJzcDlxbXVVOVk3aF8wdXVGakp4enlERXZGQk4wNjF0dlAwTDdVMnU4ei1lYWtNd2N3R3dkNGUtdVZRRkhSUmRtem9kcjBOVVB1T2dBLXk0TEhuZ0FB"

# 🔹 解碼 API Key
CLAUDE_API_KEY = base64.b64decode(ENCODED_CLAUDE_API_KEY).decode()

# 🔹 Claude API 請求函數
def generate_new_copy_with_claude(user_prompt):
    """ 使用 Claude API 生成 AI 文案 """
    url = "https://api.anthropic.com/v1/messages"

    headers = {
        "x-api-key": CLAUDE_API_KEY,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json"
    }

    data = {
        "model": "claude-3-sonnet-20240229",
        "max_tokens": 700,
        "temperature": 0.5,
        "top_p": 0.7,
        "system": "請以友善但專業的語氣回答問題，不要太熱情或冷淡。",
        "messages": [
            {"role": "user", "content": user_prompt}
        ]
    }

    response = requests.post(url, headers=headers, data=json.dumps(data))

    if response.status_code == 200:
        return response.json().get("content", "⚠️ Claude 沒有返回內容")
    else:
        print(f"❌ Claude API 錯誤: {response.status_code}, {response.text}")
        return None

# 🔹 登入 API
@app.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    username = data.get("username")
    password = data.get("password")

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT account_level, full_name FROM users WHERE username = %s AND password_hash = %s", 
                       (username, password))
        user = cursor.fetchone()

        cursor.close()
        conn.close()

        if user:
            return jsonify({
                "success": True,
                "message": "登入成功！",
                "account_level": user[0],
                "full_name": user[1]
            })
        else:
            return jsonify({
                "success": False,
                "message": "帳號或密碼錯誤！"
            })

    except Exception as e:
        return jsonify({
            "success": False,
            "message": f"伺服器錯誤: {str(e)}"
        })

# 🔹 生成 AI 文案
@app.route('/generate_copy', methods=['POST'])
def generate_copy():
    data = request.get_json()
    user_prompt = data.get("prompt")

    if not user_prompt:
        return jsonify({
            "success": False,
            "message": "請提供一個 prompt"
        })

    # 產生文案
    new_copy = generate_new_copy_with_claude(user_prompt)
    
    if new_copy:
        return jsonify({
            "success": True,
            "message": "文案生成成功！",
            "generated_copy": new_copy
        })
    else:
        return jsonify({
            "success": False,
            "message": "生成文案時發生錯誤！"
        })

# 🔹 儲存 AI 生成的文案
@app.route('/save_generated_copy', methods=['POST'])
def save_generated_copy():
    data = request.get_json()
    full_name = data.get("full_name")  
    question = data.get("question")  
    answer = data.get("answer")  

    if not full_name or not question or not answer:
        return jsonify({
            "success": False,
            "message": "缺少必要的欄位"
        })

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        insert_query = """
        INSERT INTO test_results (full_name, question, answer)
        VALUES (%s, %s, %s);
        """
        cursor.execute(insert_query, (full_name, question, answer))

        conn.commit()
        cursor.close()
        conn.close()

        return jsonify({
            "success": True,
            "message": "文案已保存成功！"
        })

    except Exception as e:
        return jsonify({
            "success": False,
            "message": f"伺服器錯誤: {str(e)}"
        })

# 🔹 讀取 test_results 資料表
@app.route('/get_test_results', methods=['GET'])
def get_test_results():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT id, full_name, question, answer FROM test_results")
        results = cursor.fetchall()

        cursor.close()
        conn.close()

        results_data = [{"id": row[0], "full_name": row[1], "question": row[2], "answer": row[3]} for row in results]

        return jsonify({
            "success": True,
            "data": results_data
        })

    except Exception as e:
        return jsonify({
            "success": False,
            "message": f"伺服器錯誤: {str(e)}"
        })

if __name__ == '__main__':
    print("\n🚀 Flask 伺服器啟動中...")
    print("🔐 Claude API Key (Base64 解碼後):", CLAUDE_API_KEY)  # ⚠️ 正式環境請移除，避免金鑰外洩！
    app.run(debug=True, host="0.0.0.0", port=5000)
