# 使用精簡版 Python 映像
FROM python:3.10-slim

# 安裝 poppler-utils（支援 pdf2image）
RUN apt-get update && apt-get install -y poppler-utils tesseract-ocr tesseract-ocr-chi-tra

# 設定工作目錄
WORKDIR /app

# 複製專案所有檔案到容器中
COPY . .

# 安裝依賴
RUN pip install --no-cache-dir -r requirements.txt

# 開放 port（Zeabur 預設是接收 8080）
EXPOSE 8080

# 啟動 Flask 應用（注意你是 5003，但 Zeabur 預設走 8080，我們要轉一下）
CMD ["gunicorn", "-b", "0.0.0.0:8080", "app:app"]
