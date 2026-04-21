import os
import requests
from flask import Flask, render_template, request, jsonify
from langchain_openai import AzureChatOpenAI
from langchain.agents import initialize_agent, Tool

app = Flask(__name__)

# --- CẤU HÌNH ---
os.environ["AZURE_OPENAI_API_KEY"] = "Erllz05hTVhX9qPyuQ5hfWRfnk0o8udR57U4f9zUCYhY1VhGYA6vJQQJ99CDACi0881XJ3w3AAABACOGGgKQ"
os.environ["AZURE_OPENAI_ENDPOINT"] = "https://webinar-model.openai.azure.com/openai/v1/chat/completions"

llm = AzureChatOpenAI(
    azure_deployment="demo-model", 
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
