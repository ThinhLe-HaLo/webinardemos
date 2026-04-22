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
def web_fetcher(url):
    """Hàm lấy nội dung văn bản từ URL, loại bỏ mã HTML thừa."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        # Dùng BeautifulSoup để lọc sạch mã HTML
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Loại bỏ các tag không chứa nội dung đọc được
        for script_or_style in soup(["script", "style", "nav", "footer", "header"]):
            script_or_style.extract()
            
        clean_text = soup.get_text(separator=' ', strip=True)
        
        # Giới hạn 6000 ký tự để không bị tràn Token của AI
        return clean_text[:6000] 
        
    except Exception as e:
        return f"Lỗi khi truy cập link: {str(e)}"

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
    user_input = data.get('message')
    
    if not user_input:
        return jsonify({"response": "Bạn chưa nhập câu hỏi!"})

    try:
        # Gọi Agent xử lý (sử dụng invoke cho các bản LangChain mới)
        result = agent.invoke({"input": user_input})
        return jsonify({"response": result["output"]})
    except Exception as e:
        print(f"Lỗi hệ thống: {str(e)}")
        return jsonify({"response": f"Xin lỗi, tôi gặp trục trặc khi xử lý: {str(e)}"})

if __name__ == '__main__':
    # Chạy local để test, trên Azure sẽ dùng Gunicorn
    app.run(debug=True)
