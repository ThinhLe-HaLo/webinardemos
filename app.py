import os
import requests
from flask import Flask, render_template, request, jsonify
from langchain_openai import AzureChatOpenAI
from langchain.agents import initialize_agent, Tool
from azure.identity import DefaultAzureCredential, get_bearer_token_provider
from bs4 import BeautifulSoup # THÊM DÒNG NÀY

app = Flask(__name__)

# --- CẤU HÌNH ---
#AZURE_OPENAI_API_KEY = os.getenv("AZURE_OPENAI_API_KEY")
AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT")
AZURE_OPENAI_DEPLOYMENT_NAME = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME")

# Kiểm tra nếu thiếu biến môi trường thì báo lỗi ngay để dễ debug
if not AZURE_OPENAI_ENDPOINT or not AZURE_OPENAI_DEPLOYMENT_NAME:
    raise ValueError("Thiếu cấu hình biến môi trường cho Azure OpenAI!")

# --- XÁC THỰC BẰNG MANAGED IDENTITY ---
credential = DefaultAzureCredential()
token_provider = get_bearer_token_provider(
    credential, "https://cognitiveservices.azure.com/.default"
)

llm = AzureChatOpenAI(
    azure_ad_token_provider=token_provider,
    azure_deployment=AZURE_OPENAI_DEPLOYMENT_NAME, 
    api_version="2023-05-15",
    temperature=0
)

def web_fetcher(url):
    headers = {"Metadata": "true"}
    try:
        response = requests.get(url, headers=headers, timeout=7)
        
        # Dùng BeautifulSoup để lọc sạch mã HTML, chỉ lấy text
        soup = BeautifulSoup(response.text, 'html.parser')
        clean_text = soup.get_text(separator=' ', strip=True)
        
        # Giới hạn số lượng ký tự trả về (ví dụ: 6000 ký tự đầu tiên)
        # Để đảm bảo AI không bao giờ bị quá tải Token
        return clean_text[:6000] 
        
    except Exception as e:
        return f"Error: {str(e)}"

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/ask', methods=['POST'])
def ask():
    user_prompt = request.json.get('prompt')
    # Agent sẽ nhận diện link trong prompt và dùng WebReader
    result = agent.run(user_prompt)
    return jsonify({"answer": result})

if __name__ == "__main__":
    app.run()
