import os
import sys
from openai import OpenAI
from PyQt5.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, QPushButton, QLabel, QFileDialog, QMessageBox
from PyQt5.QtCore import Qt
import datetime
import PyPDF2
import warnings
from PIL import Image
import pytesseract
from fpdf import FPDF
import time

# OpenAI API 키 설정
os.environ["OPENAI_API_KEY"] = ""

# 폰트 경고 무시
warnings.filterwarnings('ignore', category=UserWarning)

# 로그 파일 경로 설정
log_file_path = os.path.join(os.getcwd(), "chat_log.txt")
client = OpenAI()

# 초기 프롬프트
prompts = ["사전에 학습된 규정을 바탕으로 이후 입력된 과제서의 예산안 부분의 적합성을 판단해주세요. 예산을 수식에 대입하여 계산해주시고, 계산된 식과 계산된 예산값을 출력한 뒤, 계획된 예산값과 계산값을 비교분석해주세요. 수치적인 통계를 내주시고 어떠한 계산 방법이 선택되었는지도 알려주세요. 가독성이 높게 표나 그래프를 활용해주세요. 이 때, 계산된 예산값보다 계획된 예산값이 작거나 같으면 적합판정을 내주세요. 그리고 해당 예산표에 적힌 예산이 허용 가능 예산 범위를 넘은 경우, 해당 예산의 최댓값을 재공지하며 수정을 요구하는 문장을 작성해주세요. 그리고 마지막 줄에 최종 평가와 피드백을 요약하여 다섯문장 내의 결론을 추가해주세요. 만약, 내용이 길더라도 문장을 생략하지 말고 전체 출력해주세요. 또한 모든 예산 항목을 항목별로 계산해주시고 예시는 들지 마세요."] 

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

    if hasattr(sys, '_MEIPASS'):
        font_path = os.path.join(sys._MEIPASS, "font", "maru.ttf")
    else:
        font_path = os.path.join(os.getcwd(), "font", "maru.ttf")

    pdf.add_font("maru", "", font_path, uni=True)
    pdf.set_font("maru", size=12)

    for idx, content in enumerate(content_list, 1):
        pdf.multi_cell(0, 10, f"{idx}. {content}")
        pdf.ln(10)
    result_pdf_path = os.path.join(os.getcwd(), "result.pdf")
    pdf.output(result_pdf_path)
    QMessageBox.information(None, "결과", f"결과가 {result_pdf_path}에 저장되었습니다.")

# 규율 파일 경로 (프로그램 시작시 자동으로 로드됨)
if hasattr(sys, '_MEIPASS'):
    guideline_file_path = os.path.join(sys._MEIPASS, "GIST.txt")
else:
    guideline_file_path = os.path.join(os.getcwd(), "GIST.txt")

try:
    guideline_content = load_guidelines(guideline_file_path)
    messages = [{"role": "system", "content": guideline_content}]
    log_message("System", f"{guideline_file_path} 파일 내용을 추가했습니다.")
    print(f"{guideline_file_path} 파일을 성공적으로 불러왔습니다.")
except Exception as e:
    print(f"규율 파일을 불러오는 중 오류 발생: {e}")
    messages = []

class Application(QMainWindow):
    def __init__(self):
        super().__init__()
        self.initUI()

    def initUI(self):
        self.setWindowTitle("GIST 예산 평가 시스템")
        self.setGeometry(100, 100, 400, 200)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout()

        self.description_label = QLabel("GIST 학교 규정을 기준으로 과제서의 예산을 평가합니다.\nPDF 파일을 업로드하면 분석이 시작됩니다.")
        self.description_label.setWordWrap(True)
        layout.addWidget(self.description_label)

        self.eval_button = QPushButton("평가 파일 업로드")
        self.eval_button.clicked.connect(self.evaluate_file)
        layout.addWidget(self.eval_button)

        central_widget.setLayout(layout)

    def evaluate_file(self):
        options = QFileDialog.Options()
        file_path, _ = QFileDialog.getOpenFileName(self, "파일 선택", "", "PDF files (*.pdf);;Text files (*.txt)", options=options)
        if not file_path:
            return

        _, file_extension = os.path.splitext(file_path)
        if file_extension.lower() == '.pdf':
            file_content = read_pdf(file_path)
        elif file_extension.lower() == '.txt':
            file_content = read_txt(file_path)
        else:
            QMessageBox.critical(self, "오류", "지원하지 않는 파일 형식입니다. PDF 혹은 TXT 파일만 지원합니다.")
            return

        messages.append({"role": "system", "content": file_content})
        log_message("System", f"{file_path} 파일 내용을 추가했습니다.")
        evaluation_results = []

        for prompt in prompts:
            # response_text = "(" + prompt + ")" + "\n\n"
            response_text = "\n\n"
            messages.append({"role": "user", "content": prompt})
            log_message("User", prompt)
            completion = client.chat.completions.create(
                model="gpt-4o",
                messages=messages,
                stream=True
            )
            for chunk in completion:
                if chunk.choices[0].delta.content is not None:
                    response_text += chunk.choices[0].delta.content
            messages.append({"role": "assistant", "content": response_text})
            log_message("Assistant", response_text)
            evaluation_results.append(response_text)

        generate_pdf(evaluation_results)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    main_window = Application()
    main_window.show()
    sys.exit(app.exec_())
