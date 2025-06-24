import os
import hmac
import hashlib
import time
import requests
from urllib.parse import urlencode
from flask import Flask, request, jsonify
from flask_cors import CORS  # 引用 CORS
from dotenv import load_dotenv

# 從 .env 文件載入環境變數 (本地測試用)
load_dotenv()

app = Flask(__name__)

# **== CORS 設定更新 ==**
# 更新 CORS 設定，更明確地允許所有來源對 /api/ 路徑的請求。
# 這能更穩定地解決跨域請求問題。
CORS(app, resources={r"/api/*": {"origins": "*"}})

# 從環境變數讀取您的露天 API 金鑰
API_KEY = os.getenv('RUTEN_API_KEY')
SECRET_KEY = os.getenv('RUTEN_SECRET_KEY')
SALT_KEY = os.getenv('RUTEN_SALT_KEY')

BASE_URL = "https://partner.ruten.com.tw"

def generate_signature(url_path: str, timestamp: str) -> str:
    """生成 HMAC-SHA256 簽章"""
    if not all([SALT_KEY, SECRET_KEY]):
        raise ValueError("缺少 SALT_KEY 或 SECRET_KEY 環境變數")

    sign_string = f"{SALT_KEY}{url_path}{timestamp}"
    signature = hmac.new(
        SECRET_KEY.encode('utf-8'),
        sign_string.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    return signature

@app.route('/api/ruten', methods=['GET'])
def ruten_proxy():
    """
    代理 API 端點，接收前端請求，並安全地呼叫露天 API
    """
    if not all([API_KEY, SECRET_KEY, SALT_KEY]):
        return jsonify({"message": "錯誤：伺服器未設定露天 API 憑證"}), 500

    # 從前端請求的 URL 參數中獲取目標端點和參數
    endpoint = request.args.get('endpoint')
    if not endpoint:
        return jsonify({"message": "錯誤：未提供目標 'endpoint' 參數"}), 400

    # 組合露天 API 的完整 URL
    params = {k: v for k, v in request.args.items() if k != 'endpoint'}
    query_string = urlencode(params)
    full_url = f"{BASE_URL}{endpoint}?{query_string}"

    # 產生簽章
    timestamp = str(int(time.time()))
    try:
        signature = generate_signature(full_url, timestamp)
    except ValueError as e:
        return jsonify({"message": str(e)}), 500

    headers = {
        'X-RT-Key': API_KEY,
        'X-RT-Timestamp': timestamp,
        'X-RT-Authorization': signature
    }

    try:
        # 向真正的露天 API 發送請求
        response = requests.get(full_url, headers=headers, timeout=20)
        response.raise_for_status()  # 如果回應狀態碼是 4xx 或 5xx，則拋出異常
        
        # 將露天 API 的回應直接回傳給前端
        return jsonify(response.json())

    except requests.exceptions.HTTPError as e:
        try:
            error_details = e.response.json()
            message = error_details.get('error_msg', '露天 API 回傳錯誤')
        except:
            message = str(e)
        return jsonify({"message": f"API 請求錯誤: {message}", "status_code": e.response.status_code}), e.response.status_code
        
    except requests.exceptions.RequestException as e:
        return jsonify({"message": f"請求露天 API 時發生網路錯誤: {str(e)}"}), 503

@app.route('/')
def index():
    return "Ruten API Proxy is running."

# 本地測試時，可以直接執行此檔案
# python app.py
if __name__ == '__main__':
    app.run(debug=True, port=5001)

