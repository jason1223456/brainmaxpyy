from flask import Flask, request, jsonify
from flask_cors import CORS
import psycopg2
import requests
import json
import base64
import os
from werkzeug.utils import secure_filename
import mimetypes

app = Flask(__name__)
CORS(app)

# 🔹 檔案上傳設定
UPLOAD_FOLDER = './uploads'
ALLOWED_EXTENSIONS = {'pdf', 'docx', 'txt'}
ALLOWED_MIME_TYPES = {
    'application/pdf',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    'text/plain'
}
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

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

# 🔹 OpenRouter API Key (Base64 編碼)
ENCODED_OPENROUTER_API_KEY = "c2stb3ItdjEtZjM2NmMwNGY4OGMxOTNlOTRjYTFiNzg0NWIxNjhlOTlkNzVmNjJhMTBkOTI5MjIyZGZhNTM0ZmIzMDg0YjA4Mg=="
OPENROUTER_API_KEY = base64.b64decode(ENCODED_OPENROUTER_API_KEY).decode()

OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"

# 🔹 可用模型列表
AVAILABLE_MODELS = {
    "1": "openai/gpt-4o",
    "2": "anthropic/claude-3.7-sonnet:beta",
    "3": "perplexity/sonar-deep-research",
    "4": "google/gemini-flash-1.5",
    "5": "deepseek/deepseek-r1:free"
}

def generate_copy_with_model(model, user_prompt):
    """ 使用 OpenRouter API 透過指定模型生成文案 """
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json"
    }
    
    data = {
        "model": model,
        "messages": [{"role": "user", "content": user_prompt}]
    }

    response = requests.post(OPENROUTER_API_URL, headers=headers, json=data)

    if response.status_code == 200:
        result = response.json()
        return result["choices"][0]["message"]["content"]
    else:
        print(f"❌ {model} 錯誤: {response.status_code}, {response.text}")
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
    selected_model_keys = data.get("models")  # 前端傳來的選擇模型列表 (e.g., ["1", "3", "5"])

    if not user_prompt:
        return jsonify({
            "success": False,
            "message": "請提供 prompt"
        })
    
    if not selected_model_keys:
        return jsonify({
            "success": False,
            "message": "請選擇至少一個模型"
        })

    # 取得選擇的模型列表
    selected_models = [AVAILABLE_MODELS[key] for key in selected_model_keys if key in AVAILABLE_MODELS]

    if not selected_models:
        return jsonify({
            "success": False,
            "message": "選擇的模型無效"
        })

    # 依照選擇的模型逐一請求 OpenRouter API
    generated_results = {}
    for model in selected_models:
        generated_text = generate_copy_with_model(model, user_prompt)
        generated_results[model] = generated_text or "⚠️ 生成失敗"

    return jsonify({
        "success": True,
        "message": "文案生成成功！",
        "generated_results": generated_results
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

# 🔹 讀取 test_results 資料表並執行模糊查詢
@app.route('/get_test_results', methods=['GET'])
def get_test_results():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # ✅ 加上 ORDER BY id DESC，確保最新筆資料排最前面
        cursor.execute("SELECT id, full_name, question, answer FROM test_results ORDER BY id DESC")
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
        
def allowed_file(filename, mimetype):
    ext = filename.rsplit('.', 1)[-1].lower()
    return (
        '.' in filename and
        ext in ALLOWED_EXTENSIONS and
        mimetype in ALLOWED_MIME_TYPES
    )

@app.route('/upload_file', methods=['POST'])
def upload_file():
    print("📩 收到上傳請求")
    print("📦 Headers:", dict(request.headers))

    if 'file' not in request.files:
        return jsonify({"success": False, "message": "未提供檔案"}), 400

    file = request.files['file']
    uploader = request.form.get('uploader', 'anonymous')

    if file.filename == '':
        return jsonify({"success": False, "message": "檔案名稱為空"}), 400

    original_filename = file.filename
    print(f"📝 原始檔名: {original_filename}")

    if '.' not in original_filename:
        print(f"⚠️ 檔名沒有副檔名: {original_filename}")
        return jsonify({"success": False, "message": "檔案缺少副檔名"}), 400

    # 處理檔名（保留副檔名）
    ext = original_filename.rsplit('.', 1)[1].lower()
    base = secure_filename(original_filename.rsplit('.', 1)[0])
    filename = f"{base}.{ext}"

    mimetype = file.mimetype or mimetypes.guess_type(filename)[0] or 'application/octet-stream'
    print(f"📝 處理後檔名: {filename}")
    print(f"🔍 MIME 類型: {mimetype}")

    if not allowed_file(filename, mimetype):
        return jsonify({"success": False, "message": f"不支援的檔案類型：{filename} / MIME：{mimetype}"}), 400

    try:
        file_data = file.read()
        file_size = len(file_data)
        save_path = os.path.join(UPLOAD_FOLDER, filename)

        with open(save_path, 'wb') as f:
            f.write(file_data)

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO uploaded_files (file_name, file_path, file_format, mime_type, file_size, uploader, file_data)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (filename, save_path, ext, mimetype, file_size, uploader, psycopg2.Binary(file_data)))
        conn.commit()
        cursor.close()
        conn.close()

        return jsonify({"success": True, "message": "檔案上傳成功"})

    except Exception as e:
        return jsonify({"success": False, "message": f"伺服器錯誤: {str(e)}"}), 500



if __name__ == '__main__':
    print("\n🚀 Flask 伺服器啟動中...")
    app.run(debug=True, host="0.0.0.0", port=5003)

