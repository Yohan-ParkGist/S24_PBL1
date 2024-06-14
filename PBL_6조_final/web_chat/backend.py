import os
from flask import Flask, request, jsonify
import openai
import base64
import requests
import PyPDF2
import datetime

app = Flask(__name__)

# API 키 설정
api_key = ""
openai.api_key = api_key

# 로그 파일 경로
log_file_path = "chat_log.txt"

def log_message(role, content):
    with open(log_file_path, "a", encoding='utf-8-sig') as log_file:
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_file.write(f"[{timestamp}] {role}: {content}\n")

def encode_image(image_path):
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode('utf-8')

def read_pdf(file_path):
    content = ""
    with open(file_path, "rb") as f:
        reader = PyPDF2.PdfReader(f)
        for page in reader.pages:
            content += page.extract_text() + "\n"
    return content

def read_txt(file_path):
    with open(file_path, "r", encoding="utf-8") as file:
        content = file.read()
    return content

def image_download(file_name, img_url):
    current_dir = os.getcwd()
    image_folder = os.path.join(current_dir, "image")
    if not os.path.exists(image_folder):
        os.makedirs(image_folder)
    res = requests.get(img_url)
    if res.status_code == 200:
        file_path = os.path.join(image_folder, f"{file_name}.jpg")
        with open(file_path, 'wb') as file:
            file.write(res.content)
        return file_path
    else:
        return None

@app.route('/upload_file', methods=['POST'])
def upload_file():
    file = request.files['file']
    file_path = os.path.join(os.getcwd(), file.filename)
    file.save(file_path)
    
    file_extension = os.path.splitext(file_path)[1].lower()
    if file_extension == '.pdf':
        content = read_pdf(file_path)
    elif file_extension == '.txt':
        content = read_txt(file_path)
    else:
        return jsonify({'message': '지원하지 않는 파일 형식입니다.'})
    
    log_message("System", f"{file_path} 파일 내용을 추가했습니다.")
    return jsonify({'message': f"{file_path} 파일을 성공적으로 업로드했습니다.", 'content': content})

@app.route('/generate_image', methods=['POST'])
def generate_image():
    data = request.get_json()
    prompt = data['prompt']
    file_name = data['file_name']
    
    response = openai.Image.create(
        model="dall-e-3",
        prompt=prompt,
        n=1,
        size="1024x1024",
        quality="hd",
    )
    image_url = image_url = response.data[0].url
    file_path = image_download(file_name, image_url)
    
    if file_path:
        return jsonify({'message': f"이미지가 성공적으로 {file_name}.jpg 이름으로 저장되었습니다."})
    else:
        return jsonify({'message': "이미지를 다운로드 하는데 실패하였습니다."})

@app.route('/analyze_image', methods=['POST'])
def analyze_image():
    data = request.get_json()
    file_name = data['file_name']
    file_path = os.path.join(os.getcwd(), "image", f"{file_name}.jpg")
    
    if not os.path.exists(file_path):
        return jsonify({'message': '이미지 파일을 찾을 수 없습니다.'})
    
    base64_image = encode_image(file_path)
    response = openai.ChatCompletion.create(
        model="gpt-4o",
        messages=[
            {
                "role": "user",
                "content": f"Analyze this image: <|image|>{base64_image}"
            }
        ],
        stream=True
    )
    
    analysis_result = response.choices[0].message.content
    log_message("User", f"{file_path} 이미지를 분석 요청했습니다.")
    log_message("Assistant", analysis_result)
    
    return jsonify({'message': analysis_result})

if __name__ == "__main__":
    app.run(debug=True)