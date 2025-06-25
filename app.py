import os
import hmac
import hashlib
import time
import requests
from urllib.parse import urlencode
from flask import Flask, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv

# 從 .env 文件載入環境變數 (本地測試用)
load_dotenv()

app = Flask(__name__)

# **== 部署到網站的最終設定 ==**
# 為了安全性，我們不再允許所有來源(*)。
# 請將 YOUR_WEBSITE_DOMAIN.com 換成您網站的確切網址。
# 例如： origins = ["https://www.my-cool-shop.com", "https://my-cool-shop.com"]
# 如果您在本地測試時，也可以加入 "http://localhost:8000"
origins = ["https://kentware.com"] 
CORS(app, resources={r"/api/*": {"origins": origins}})


# 從環境變數讀取您的露天 API 金鑰
API_KEY = os.getenv('RUTEN_API_KEY')
SECRET_KEY = os.getenv('RUTEN_SECRET_KEY')
SALT_KEY = os.getenv('RUTEN_SALT_KEY')

print("--- Ruten Proxy Service Starting (Production Mode) ---")
print(f"Allowed Origins: {origins}")
print(f"RUTEN_API_KEY loaded: {'Yes' if API_KEY else 'No - PLEASE CHECK RENDER ENV VARS'}")


BASE_URL = "https://partner.ruten.com.tw"

def _make_ruten_request(endpoint: str, params: dict):
    """一個通用的函數，用於準備並發送請求到露天"""
    if not all([API_KEY, SECRET_KEY, SALT_KEY]):
        raise ValueError("伺服器未設定露天 API 憑證")

    sorted_params = dict(sorted(params.items()))
    query_string = urlencode(sorted_params)
    full_url = f"{BASE_URL}{endpoint}?{query_string}"
    
    timestamp = str(int(time.time()))
    
    request_body = ""
    sign_string = f"{SALT_KEY}{full_url}{request_body}{timestamp}"
    
    signature = hmac.new(
        SECRET_KEY.encode('utf-8'),
        sign_string.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()

    headers = {
        'User-Agent': 'Ruten-Proxy-App/1.0',
        'Content-Type': 'application/json',
        'X-RT-Key': API_KEY,
        'X-RT-Timestamp': timestamp,
        'X-RT-Authorization': signature
    }
    
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
        message = str(e)
        status_code = 500
        if isinstance(e, requests.exceptions.HTTPError):
            status_code = e.response.status_code
            try:
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
        
    try:
        _make_ruten_request('/api/v1/product/list', {'status': 'all', 'offset': 1, 'limit': 1})
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
    return "Ruten API Proxy is running (Production Mode)."

if __name__ == '__main__':
    # 這段是本地測試用的，部署到 Render 時不會執行
    # 若要在本地測試，請記得將您的 localhost 加入 origins 列表
    app.run(debug=True, port=5001)

