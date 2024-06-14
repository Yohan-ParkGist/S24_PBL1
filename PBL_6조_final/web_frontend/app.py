import os
import sys
import datetime
import PyPDF2
import warnings
from PIL import Image
import pytesseract
from fpdf import FPDF
from flask import Flask, render_template, request, redirect, url_for, send_from_directory, flash
import openai

app = Flask(__name__, template_folder=os.getcwd(), static_folder=os.getcwd())
app.config['UPLOAD_FOLDER'] = 'uploads'
app.secret_key = 'supersecretkey'

# OpenAI API 키 설정
os.environ["OPENAI_API_KEY"] = ""
client = openai.OpenAI()

# 폰트 경고 무시
warnings.filterwarnings('ignore', category=UserWarning)

# 로그 파일 경로 설정
log_file_path = os.path.join(os.getcwd(), "chat_log.txt")

# 초기 프롬프트 설정
prompts = "사전에 학습된 규정을 바탕으로 이후 입력된 과제서의 예산안 부분의 적합성을 판단해주세요. 예산을 수식에 대입하여 계산해주시고, 계산된 식과 계산된 예산값을 출력한 뒤, 계획된 예산값과 계산값을 비교분석해주세요. 수치적인 통계를 내주시고 어떠한 계산 방법이 선택되었는지도 알려주세요. 가독성이 높게 표나 그래프를 활용해주세요. 이 때, 계산된 예산값보다 계획된 예산값이 작거나 같으면 적합판정을 내주세요. 그리고 해당 예산표에 적힌 예산이 허용 가능 예산 범위를 넘은 경우, 해당 예산의 최댓값을 재공지하며 수정을 요구하는 문장을 작성해주세요. 그리고 마지막 줄에 최종 평가와 피드백을 요약하여 다섯문장 내의 결론을 추가해주세요. 만약, 내용이 길더라도 문장을 생략하지 말고 전체 출력해주세요. 또한 모든 예산 항목을 항목별로 계산해주시고 예시는 들지 마세요."

def log_message(role, content):
    with open(log_file_path, "a", encoding='utf-8-sig') as log_file:
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_file.write(f"[{timestamp}] {role}: {content}\n")

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

def load_guidelines(file_path):
    _, file_extension = os.path.splitext(file_path)
    if file_extension.lower() == '.pdf':
        return read_pdf(file_path)
    elif file_extension.lower() == '.txt':
        return read_txt(file_path)
    else:
        raise ValueError("규율 파일은 PDF 혹은 TXT 형식만 지원합니다.")

def generate_pdf(content_list):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    font_path = os.path.join(os.getcwd(), "maru.ttf")
    pdf.add_font("maru", "", font_path, uni=True)
    pdf.set_font("maru", size=12)
    for idx, content in enumerate(content_list, 1):
        pdf.multi_cell(0, 10, f"{idx}. {content}")
        pdf.ln(10)
    result_pdf_path = os.path.join(os.getcwd(), "result.pdf")
    pdf.output(result_pdf_path)
    return result_pdf_path

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload():
    if 'file' not in request.files:
        flash('파일이 선택되지 않았습니다.', 'error')
        return redirect(request.url)

    file = request.files['file']
    if file.filename == '':
        flash('파일이 선택되지 않았습니다.', 'error')
        return redirect(request.url)

    if file and allowed_file(file.filename):
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
        file.save(file_path)
        try:
            guideline_content = load_guidelines(file_path)
            messages = [{"role": "system", "content": guideline_content}]
            log_message("System", f"{file.filename} 파일 내용을 추가했습니다.")
            evaluation_results = []
            messages.append({"role": "user", "content": prompts})
            log_message("User", prompts)
            completion = client.chat.completions.create(
                model="gpt-4o",
                messages=messages,
                stream=True
            )
            response_text = ""
            for chunk in completion:
                if chunk.choices[0].delta.content is not None:
                    response_text += chunk.choices[0].delta.content
            messages.append({"role": "assistant", "content": response_text})
            log_message("Assistant", response_text)
            evaluation_results.append(response_text)

            generate_pdf(evaluation_results)
            flash('파일이 성공적으로 업로드되고 처리되었습니다.', 'success')
        except Exception as e:
            flash(f'파일 처리 중 오류 발생: {e}', 'error')
        return redirect(url_for('index'))

    flash('허용되지 않는 파일 형식입니다. PDF 또는 TXT 파일만 업로드해주세요.', 'error')
    return redirect(url_for('index'))

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in {'pdf', 'txt'}

if __name__ == '__main__':
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    app.run(debug=True)