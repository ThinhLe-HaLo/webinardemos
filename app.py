import os
import requests
from flask import Flask, render_template, request, jsonify
from langchain_openai import AzureChatOpenAI
from langchain.agents import initialize_agent, Tool

app = Flask(__name__)

# --- CẤU HÌNH ---
AZURE_OPENAI_API_KEY = os.getenv("AZURE_OPENAI_API_KEY")
AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT")
AZURE_OPENAI_DEPLOYMENT_NAME = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME")

# Kiểm tra nếu thiếu biến môi trường thì báo lỗi ngay để dễ debug
if not AZURE_OPENAI_API_KEY or not AZURE_OPENAI_ENDPOINT:
    raise ValueError("Thiếu cấu hình biến môi trường cho Azure OpenAI!")

llm = AzureChatOpenAI(
    azure_deployment=AZURE_OPENAI_DEPLOYMENT_NAME, 
    api_version="2023-05-15",
    temperature=0
)

def web_fetcher(url):
    # Header này là "chìa khóa" để mở cửa IMDS của Azure
    headers = {"Metadata": "true"}
    try:
        # LỖ HỔNG SSRF: Không kiểm tra nếu url trỏ tới 169.254.169.254
        response = requests.get(url, headers=headers, timeout=7)
        return response.text
    except Exception as e:
        return f"Error: {str(e)}"

tools = [
    Tool(name="WebReader", func=web_fetcher, description="Dùng để đọc nội dung từ một URL.")
]
agent = initialize_agent(tools, llm, agent="zero-shot-react-description", verbose=True)

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
    app.run()i
