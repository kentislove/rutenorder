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

# 手動附加 CORS 標頭
@app.after_request
def after_request(response):
    """在每個請求後附加 CORS 標頭"""
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
    response.headers.add('Access-Control-Allow-Methods', 'GET,POST,PUT,DELETE,OPTIONS')
    return response

# 從環境變數讀取您的露天 API 金鑰
API_KEY = os.getenv('RUTEN_API_KEY')
SECRET_KEY = os.getenv('RUTEN_SECRET_KEY')
SALT_KEY = os.getenv('RUTEN_SALT_KEY')

print("--- Ruten Proxy Service Starting (v8 - Verification Update) ---")
print(f"RUTEN_API_KEY loaded: {'Yes' if API_KEY else 'No - PLEASE CHECK RENDER ENV VARS'}")
# We don't print the actual keys for security reasons.

BASE_URL = "https://partner.ruten.com.tw"

def _make_ruten_request(endpoint: str, params: dict):
    """一個通用的函數，用於準備並發送請求到露天"""
    if not all([API_KEY, SECRET_KEY, SALT_KEY]):
        raise ValueError("伺服器未設定露天 API 憑證")

    sorted_params = dict(sorted(params.items()))
    query_string = urlencode(sorted_params)
    full_url = f"{BASE_URL}{endpoint}?{query_string}"
    
    timestamp = str(int(time.time()))
    
    # 產生簽章
    sign_string = f"{SALT_KEY}{full_url}{timestamp}"
    print(f"String to be signed: {sign_string}")
    signature = hmac.new(
        SECRET_KEY.encode('utf-8'),
        sign_string.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()

    headers = {
        'User-Agent': 'Ruten-Proxy-App/1.0',
        'X-RT-Key': API_KEY,
        'X-RT-Timestamp': timestamp,
        'X-RT-Authorization': signature
    }
    
    print(f"--> Forwarding request to Ruten: {full_url}")
    response = requests.get(full_url, headers=headers, timeout=20)
    response.raise_for_status()
    return response.json()


@app.route('/api/ruten', methods=['GET', 'OPTIONS'])
def ruten_proxy():
    if request.method == 'OPTIONS':
        return '', 200

    endpoint = request.args.get('endpoint')
    if not endpoint:
        return jsonify({"message": "錯誤：未提供目標 'endpoint' 參數"}), 400

    params = {k: v for k, v in request.args.items() if k != 'endpoint'}
    
    if endpoint == '/api/v1/product/list':
        params.setdefault('status', 'all')

    try:
        ruten_response = _make_ruten_request(endpoint, params)
        return jsonify(ruten_response)
    except Exception as e:
        # 處理 HTTP 錯誤和一般錯誤
        message = str(e)
        status_code = 500
        if isinstance(e, requests.exceptions.HTTPError):
            status_code = e.response.status_code
            try:
                # 嘗試解析露天回傳的 JSON 錯誤訊息
                error_details = e.response.json()
                message = error_details.get('error_msg', '露天 API 回傳了一個無法解析的錯誤')
            except:
                pass
        print(f"[ERROR] An error occurred: {message}")
        return jsonify({"message": f"請求失敗: {message}"}), status_code


@app.route('/api/verify', methods=['GET', 'OPTIONS'])
def verify_credentials():
    """專門用來驗證憑證的端點"""
    if request.method == 'OPTIONS':
        return '', 200
        
    print("==> Received request for /api/verify")
    try:
        # 嘗試呼叫一個最基本的 API (查詢第1頁的1筆資料)
        _make_ruten_request('/api/v1/product/list', {'status': 'all', 'offset': 1, 'limit': 1})
        # 如果沒有拋出異常，表示成功
        return jsonify({"message": "憑證有效！與露天 API 通訊成功。", "valid": True})
    except Exception as e:
        message = str(e)
        if isinstance(e, requests.exceptions.HTTPError):
            try:
                error_details = e.response.json()
                message = error_details.get('error_msg', '露天 API 回傳了一個無法解析的錯誤')
            except:
                pass
        print(f"[ERROR] Verification failed: {message}")
        return jsonify({"message": f"憑證無效或請求失敗: {message}", "valid": False}), 401


@app.route('/')
def index():
    return "Ruten API Proxy is running (v8 - Verification Update)."

if __name__ == '__main__':
    app.run(debug=True, port=5001)

