from flask import Flask, request, jsonify
from flask_cors import CORS
import psycopg2
import requests
import json
import base64
import os
from werkzeug.utils import secure_filename
import mimetypes
import io
from pdf2image import convert_from_path
import pytesseract
import subprocess
import google.generativeai as genai
print("poppler path:", subprocess.getoutput("which pdftoppm"))
print("poppler version:", subprocess.getoutput("pdftoppm -v"))
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
ENCODED_OPENROUTER_API_KEY = "c2stb3ItdjEtMjA4M2VlZDllYWZiMjIyNTkxMzBjMjg4YjAyMGY1MDM2YTMwMzk2MGE2ZDUwYzg3MjdmOGVjNDVkMDc5MDNmZQ=="
OPENROUTER_API_KEY = base64.b64decode(ENCODED_OPENROUTER_API_KEY).decode()

OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"

# 🔹 可用模型列表
AVAILABLE_MODELS = {
    "1": "deepseek/deepseek-r1:free",
    "2": "google/gemini-flash-2.5",
    "3": "anthropic/claude-sonnet-4",
    "4": "anthropic/claude-sonnet-3.7",
    "5": "openai/gpt-4o",
    "6": "google/gemini-2.0-flash-exp:free"
}

def generate_copy_with_model(model, user_prompt):
    """ 使用 OpenRouter API 透過指定模型生成文案，並去除＊號 """
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
        content = result["choices"][0]["message"]["content"]
        # 移除＊號和*
        clean_content = content.replace("＊", "").replace("*", "")
        return clean_content
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

    selected_models = [AVAILABLE_MODELS[key] for key in selected_model_keys if key in AVAILABLE_MODELS]

    if not selected_models:
        return jsonify({
            "success": False,
            "message": "選擇的模型無效"
        })

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

# 🔹 讀取 test_results 資料表
@app.route('/get_test_results', methods=['GET'])
def get_test_results():
    try:
        search_query = request.args.get('q', '').strip()

        conn = get_db_connection()
        cursor = conn.cursor()
        
        if search_query:
            # 使用LIKE做模糊搜尋，這裡示範對 full_name、question、answer 三欄做搜尋
            sql = """
            SELECT id, full_name, question, answer
            FROM test_results
            WHERE full_name LIKE %s OR question LIKE %s OR answer LIKE %s
            ORDER BY id DESC
            """
            like_query = f"%{search_query}%"
            cursor.execute(sql, (like_query, like_query, like_query))
        else:
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

# 🔹 檔案上傳 API
@app.route('/upload_file', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({"success": False, "message": "未提供檔案"}), 400

    file = request.files['file']
    uploader = request.form.get('uploader', 'anonymous')

    if file.filename == '':
        return jsonify({"success": False, "message": "檔案名稱為空"}), 400

    original_filename = file.filename

    if '.' not in original_filename:
        return jsonify({"success": False, "message": "檔案缺少副檔名"}), 400
    ext = original_filename.rsplit('.', 1)[1].lower()
    base = secure_filename(original_filename.rsplit('.', 1)[0])
    filename = f"{base}.{ext}"

    mimetype = file.mimetype or mimetypes.guess_type(filename)[0] or 'application/octet-stream'

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
          INSERT INTO uploaded_files (file_name, file_path, file_format, mime_type, file_size, uploader, file_data, scanned_text, ai_generated_text)
          VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
         """, (filename, save_path, ext, mimetype, file_size, uploader, psycopg2.Binary(file_data), "", ""))

        conn.commit()
        cursor.close()
        conn.close()

        return jsonify({"success": True, "message": "檔案上傳成功"})

    except Exception as e:
        return jsonify({"success": False, "message": f"伺服器錯誤: {str(e)}"}), 500

def allowed_file(filename, mimetype):
    allowed_extensions = {'pdf', 'png', 'jpg', 'jpeg', 'txt'}
    allowed_mimetypes = {
        'application/pdf',
        'image/png',
        'image/jpeg',
        'text/plain'
    }

    ext = filename.rsplit('.', 1)[1].lower()
    return ext in allowed_extensions and mimetype in allowed_mimetypes


# 🔹 PDF OCR 掃描 API
@app.route('/scan_pdf_ocr/<int:file_id>', methods=['GET'])
def scan_pdf_ocr(file_id):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT file_data, file_format FROM uploaded_files WHERE id = %s", (file_id,))
        row = cursor.fetchone()
        cursor.close()
        conn.close()

        if not row:
            return jsonify({"success": False, "message": "找不到該檔案"}), 404

        file_data, file_format = row
        if file_format != 'pdf':
            return jsonify({"success": False, "message": "非 PDF 檔案，無法掃描"}), 400

        # 寫暫存PDF檔案
        temp_pdf_path = f"./temp_{file_id}.pdf"
        with open(temp_pdf_path, 'wb') as f:
            f.write(file_data)

        # PDF轉圖片
        pages = convert_from_path(temp_pdf_path)

        full_text = ""
        for page in pages:
            text = pytesseract.image_to_string(page, lang='chi_tra+eng')
            full_text += text + "\n\n"

        # 刪除暫存檔
        os.remove(temp_pdf_path)

        return jsonify({"success": True, "content": full_text})

    except Exception as e:
        return jsonify({"success": False, "message": f"伺服器錯誤: {str(e)}"}), 500


# 🔹 儲存掃描後編輯文字 API
@app.route('/save_scanned_text', methods=['POST'])
def save_scanned_text():
    data = request.get_json()
    file_id = data.get("file_id")
    scanned_text = data.get("scanned_text")

    if not file_id or scanned_text is None:
        return jsonify({"success": False, "message": "缺少 file_id 或 scanned_text"}), 400

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE uploaded_files SET scanned_text = %s WHERE id = %s", (scanned_text, file_id))
        conn.commit()
        cursor.close()
        conn.close()

        return jsonify({"success": True, "message": "掃描文字已更新"})

    except Exception as e:
        return jsonify({"success": False, "message": f"伺服器錯誤: {str(e)}"}), 500
@app.route('/list_uploaded_files', methods=['GET'])
def list_uploaded_files():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        # 加入 scanned_text 欄位
        cursor.execute("SELECT id, file_name, file_format, uploader, scanned_text, ai_generated_text FROM uploaded_files ORDER BY id DESC")
        files = cursor.fetchall()
        cursor.close()
        conn.close()

        files_list = [
            {
                "id": row[0],
                "file_name": row[1],
                "file_format": row[2],
                "uploader": row[3],
                "scanned_text": row[4] if row[4] else "",
                "ai_generated_text": row[5] if row[5] else ""
            }
            for row in files
        ]

        return jsonify({"success": True, "data": files_list})

    except Exception as e:
        return jsonify({"success": False, "message": f"伺服器錯誤: {str(e)}"})


@app.route('/save_ai_result', methods=['POST'])
def save_ai_text():
    data = request.get_json()
    file_id = data.get("file_id")
    ai_generated_text = data.get("ai_generated_text")

    if not file_id or ai_generated_text is None:
        return jsonify({"success": False, "message": "缺少 file_id 或 ai_generated_text"}), 400

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE uploaded_files SET ai_generated_text = %s WHERE id = %s", (ai_generated_text, file_id))
        conn.commit()
        cursor.close()
        conn.close()

        return jsonify({"success": True, "message": "AI 文字已更新"})

    except Exception as e:
        return jsonify({"success": False, "message": f"伺服器錯誤: {str(e)}"}), 500
def generate_with_google_gemini(prompt: str) -> str | None:
    ENCODED_GOOGLE_API_KEY = "QUl6YVN5RE9XMnlRX0pUbENoejhTR012SHdReXlEeEM1RVNsQUpB"

    try:
        api_key = base64.b64decode(ENCODED_GOOGLE_API_KEY).decode()
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(model_name="gemini-1.5-flash")
        
        prompt_with_language = prompt + "\n\n請用繁體中文回答，且回答中不要出現＊號或星號。"
        
        response = model.generate_content(prompt_with_language)
        text = response.candidates[0].content.parts[0].text
        
        # 移除＊號和*
        clean_text = text.replace("＊", "").replace("*", "")
        
        return clean_text
    except Exception as e:
        print(f"❌ Google Gemini 生成失敗: {e}")
        return None


@app.route('/google_generate', methods=['POST'])
def google_generate():
    data = request.get_json()
    prompt = data.get("prompt")

    if not prompt:
        return jsonify({"success": False, "message": "缺少 prompt"}), 400

    result = generate_with_google_gemini(prompt)
    if result:
        return jsonify({"success": True, "result": result})
    else:
        return jsonify({"success": False, "message": "生成失敗"}), 500
if __name__ == '__main__':
    print("\n🚀 Flask 伺服器啟動中...")
    app.run(debug=True, host="0.0.0.0", port=5003)

