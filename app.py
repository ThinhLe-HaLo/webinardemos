import os
import requests
from flask import Flask, render_template, request, jsonify
from langchain_openai import AzureChatOpenAI
from langchain.agents import initialize_agent, Tool
from azure.identity import DefaultAzureCredential, get_bearer_token_provider
from bs4 import BeautifulSoup

app = Flask(__name__)

# --- 1. CẤU HÌNH BIẾN MÔI TRƯỜNG ---
# Lưu ý: Các biến này bạn cấu hình trên Azure App Service (Environment Variables)
AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT")
AZURE_OPENAI_DEPLOYMENT_NAME = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME")

if not AZURE_OPENAI_ENDPOINT or not AZURE_OPENAI_DEPLOYMENT_NAME:
    raise ValueError("Thiếu cấu hình biến môi trường AZURE_OPENAI_ENDPOINT hoặc AZURE_OPENAI_DEPLOYMENT_NAME!")

# --- 2. XÁC THỰC BẰNG MANAGED IDENTITY (KHÔNG DÙNG KEY) ---
credential = DefaultAzureCredential()
token_provider = get_bearer_token_provider(
    credential, "https://cognitiveservices.azure.com/.default"
)

# Khởi tạo mô hình LLM
llm = AzureChatOpenAI(
    azure_ad_token_provider=token_provider,
    azure_deployment=AZURE_OPENAI_DEPLOYMENT_NAME, 
    api_version="2023-05-15",
    temperature=0
)

# --- 3. CÔNG CỤ ĐỌC WEB (WEB FETCHER) ---
import requests
from bs4 import BeautifulSoup

def web_fetcher(url):
    # Header Metadata: true là BẮT BUỘC để Azure trả về Token
    headers = {
        "Metadata": "true",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
    }
    try:
        # Sử dụng Session để quản lý kết nối tốt hơn
        session = requests.Session()
        
        # Gửi request với verify=False (chỉ dùng cho demo) 
        # và allow_redirects=True để xử lý bit.ly
        response = session.get(
            url, 
            headers=headers, 
            timeout=15, 
            allow_redirects=True,
            verify=False 
        )

        content_type = response.headers.get("Content-Type", "").lower()

        # TÌNH HUỐNG SSRF: Nếu trả về JSON (Token)
        if "application/json" in content_type:
            return f"Hệ thống đã trích xuất dữ liệu nhạy cảm: {response.text}"

        # TÌNH HUỐNG LINK CLEAN: Dùng BeautifulSoup
        soup = BeautifulSoup(response.text, 'html.parser')
        for s in soup(["script", "style"]):
            s.decompose()
            
        clean_text = soup.get_text(separator=' ', strip=True)
        return clean_text[:5000]

    except Exception as e:
        # Trả về lỗi chi tiết để bạn biết chính xác server đang chặn ở đâu
        return f"Lỗi kỹ thuật (SSRF Triggered): {str(e)}"
# --- 4. THIẾT LẬP AGENT ---
tools = [
    Tool(
        name="WebReader",
        func=web_fetcher,
        description="Hữu ích khi người dùng cung cấp một đường link URL và muốn bạn đọc nội dung, tóm tắt hoặc trả lời câu hỏi về bài báo đó."
    )
]

agent = initialize_agent(
    tools, 
    llm, 
    agent="zero-shot-react-description", 
    verbose=True, 
    handle_parsing_errors=True # Xử lý lỗi định dạng câu trả lời của AI
)

# --- 5. ĐỊNH NGHĨA CÁC ROUTE TRÊN WEB ---
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/ask', methods=['POST'])
def ask():
    data = request.json
    
    # 1. HTML gửi nhãn 'prompt', nên Python sẽ tìm 'prompt'
    user_input = data.get('prompt') 

    if not user_input:
        return jsonify({"answer": "Bạn chưa nhập câu hỏi!"})

    try:
        # Gọi Agent xử lý
        result = agent.invoke({"input": user_input})
        
        # 2. HTML chờ nhận nhãn 'answer', nên Python trả về 'answer'
        return jsonify({"answer": result["output"]})
        
    except Exception as e:
        print(f"Lỗi hệ thống: {str(e)}")
        return jsonify({"answer": f"Xin lỗi, tôi gặp trục trặc khi xử lý: {str(e)}"})

if __name__ == '__main__':
    # Chạy local để test, trên Azure sẽ dùng Gunicorn
    app.run(debug=True)
