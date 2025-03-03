from flask import Flask, request, jsonify
from flask_cors import CORS
import psycopg2
import os
import requests
import json

app = Flask(__name__)
CORS(app)

# PostgreSQL 資料庫連線設定
DB_CONFIG = {
    "dbname": "zeabur",
    "user": "root",
    "password": "MfaN1ck3P579izFWj4n8Ve6IS2d0ODwx",  # 修改為你的 PostgreSQL 密碼
    "host": "sfo1.clusters.zeabur.com",
    "port": "31148"
}

def get_db_connection():
    return psycopg2.connect(**DB_CONFIG)

# 呼叫 Claude API 生成新文案
def generate_new_copy_with_claude(user_prompt):
    """使用 Claude API 生成新的促銷文案"""
    url = "https://api.anthropic.com/v1/messages"

    headers = {
        "x-api-key": "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",  # 替換為你的 Claude API Key
        "anthropic-version": "2023-06-01",
        "content-type": "application/json"
    }

    data = {
        "model": "claude-3-5-sonnet-20241022",
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

@app.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    username = data.get("username")
    password = data.get("password")

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT account_level, full_name FROM users WHERE username = %s AND password_hash = %s", (username, password))
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

# 新增保存文案的路由
@app.route('/save_generated_copy', methods=['POST'])
def save_generated_copy():
    data = request.get_json()
    full_name = data.get("full_name")
    print(full_name)# 使用者名稱
    question = data.get("question")  # 使用者輸入的問題
    answer = data.get("answer")  # AI 生成的回應

    if not full_name or not question or not answer:
        return jsonify({
            "success": False,
            "message": "缺少必要的欄位"
        })

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # 插入資料到 saved_results 資料表
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
# 讀取 test_results 資料表
@app.route('/get_test_results', methods=['GET'])
def get_test_results():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # 查詢 test_results 資料表中的所有資料
        cursor.execute("SELECT id, full_name, question, answer FROM test_results")
        results = cursor.fetchall()

        cursor.close()
        conn.close()

        # 格式化資料
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
    app.run(debug=True)
