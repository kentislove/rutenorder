import os
import hmac
import hashlib
import time
import requests
from urllib.parse import urlencode
from flask import Flask, request, jsonify
from dotenv import load_dotenv

# 從 .env 文件載入環境變數 (本地測試用)
load_dotenv()

app = Flask(__name__)

# **== CORS 最終修正 v2 ==**
# 手動附加 CORS 標頭，這是最可靠的跨域解決方案。
@app.after_request
def after_request(response):
    """在每個請求後附加 CORS 標頭"""
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization,X-RT-Key,X-RT-Timestamp,X-RT-Authorization')
    response.headers.add('Access-Control-Allow-Methods', 'GET,POST,PUT,DELETE,OPTIONS')
    return response

# 從環境變數讀取您的露天 API 金鑰
API_KEY = os.getenv('RUTEN_API_KEY')
SECRET_KEY = os.getenv('RUTEN_SECRET_KEY')
SALT_KEY = os.getenv('RUTEN_SALT_KEY')

# 增加啟動日誌，確認環境變數是否成功載入
print("--- Ruten Proxy Service Starting (v3 - Final) ---")
print(f"RUTEN_API_KEY loaded: {'Yes' if API_KEY else 'No - PLEASE CHECK RENDER ENV VARS'}")
print(f"RUTEN_SECRET_KEY loaded: {'Yes' if SECRET_KEY else 'No - PLEASE CHECK RENDER ENV VARS'}")
print(f"RUTEN_SALT_KEY loaded: {'Yes' if SALT_KEY else 'No - PLEASE CHECK RENDER ENV VARS'}")
print("------------------------------------")


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

@app.route('/api/ruten', methods=['GET', 'OPTIONS']) # **<-- KEY CHANGE: Added 'OPTIONS'**
def ruten_proxy():
    """
    代理 API 端點，接收前端請求，並安全地呼叫露天 API
    """
    # **== KEY CHANGE: Handle preflight 'OPTIONS' request ==**
    if request.method == 'OPTIONS':
        # 回傳一個空的成功回應，讓瀏覽器的 preflight check 通過
        return '', 200

    # -- The rest of the function handles the 'GET' request --
    endpoint = request.args.get('endpoint')
    print(f"==> Received GET request for endpoint: {endpoint}")

    if not all([API_KEY, SECRET_KEY, SALT_KEY]):
        print("[ERROR] Server API credentials are not set.")
        return jsonify({"message": "錯誤：伺服器未設定露天 API 憑證"}), 500

    if not endpoint:
        print(f"[ERROR] 'endpoint' parameter is missing.")
        return jsonify({"message": "錯誤：未提供目標 'endpoint' 參數"}), 400

    params = {k: v for k, v in request.args.items() if k != 'endpoint'}
    query_string = urlencode(params)
    full_url = f"{BASE_URL}{endpoint}?{query_string}"

    timestamp = str(int(time.time()))
    try:
        signature = generate_signature(full_url, timestamp)
    except ValueError as e:
        print(f"[ERROR] Signature generation failed: {e}")
        return jsonify({"message": str(e)}), 500

    headers = {
        'X-RT-Key': API_KEY,
        'X-RT-Timestamp': timestamp,
        'X-RT-Authorization': signature
    }

    try:
        print(f"--> Forwarding request to Ruten: {full_url}")
        response = requests.get(full_url, headers=headers, timeout=20)
        response.raise_for_status()
        
        print(f"<-- Received response from Ruten, status: {response.status_code}")
        return jsonify(response.json())

    except requests.exceptions.HTTPError as e:
        print(f"[ERROR] HTTP Error from Ruten: {e}")
        try:
            error_details = e.response.json()
            message = error_details.get('error_msg', '露天 API 回傳錯誤')
        except:
            message = str(e)
        return jsonify({"message": f"API 請求錯誤: {message}", "status_code": e.response.status_code}), e.response.status_code
        
    except requests.exceptions.RequestException as e:
        print(f"[ERROR] Network request exception: {e}")
        return jsonify({"message": f"請求露天 API 時發生網路錯誤: {str(e)}"}), 503

@app.route('/')
def index():
    return "Ruten API Proxy is running (v3 - Final)."

if __name__ == '__main__':
    app.run(debug=True, port=5001)

