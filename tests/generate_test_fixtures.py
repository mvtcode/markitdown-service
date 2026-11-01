"""
Helper script to generate various test files:
- Plain text: txt, csv, html
- Media: wav audio
- OCR test images: png, jpg (with text drawn onto images)
- PDF: PDF with text and embedded image
- Office: docx, xlsx
"""

import math
import os
from pathlib import Path
import struct
import wave

from PIL import Image, ImageDraw, ImageFont

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def ensure_fixtures_dir():
    os.makedirs(FIXTURES_DIR, exist_ok=True)


def create_plain_text_files():
    # 1. TXT
    txt_path = FIXTURES_DIR / "sample.txt"
    with open(txt_path, "w", encoding="utf-8") as f:
        f.write("# Báo Cáo Kỹ Thuật\n\nĐây là tệp tin văn bản thuần túy kiểm tra tính năng chuyển đổi.")

    # 2. CSV
    csv_path = FIXTURES_DIR / "sample.csv"
    with open(csv_path, "w", encoding="utf-8") as f:
        f.write("ID,Tên sản phẩm,Đơn giá,Số lượng,Thành tiền\n")
        f.write("1,Laptop Dell XPS,25000000,2,50000000\n")
        f.write("2,Chuột không dây,350000,5,1750000\n")
        f.write("3,Bàn phím cơ,1200000,3,3600000\n")

    # 3. HTML
    html_path = FIXTURES_DIR / "sample.html"
    with open(html_path, "w", encoding="utf-8") as f:
        f.write("""<!DOCTYPE html>
<html>
<head><title>Trang HTML Test</title></head>
<body>
    <h1>Tiêu đề bài viết HTML</h1>
    <p>Đoạn văn bản HTML kiểm tra chuyển đổi sang Markdown.</p>
    <ul>
        <li>Tính năng 1: Chuyển đổi định dạng</li>
        <li>Tính năng 2: Hỗ trợ OCR</li>
        <li>Tính năng 3: Xử lý hàng đợi</li>
    </ul>
</body>
</html>""")


def create_media_audio():
    # Generate 1 second synthetic 440Hz sine wave WAV file
    wav_path = FIXTURES_DIR / "sample_audio.wav"
    sample_rate = 16000
    duration_sec = 1.0
    frequency = 440.0

    num_samples = int(sample_rate * duration_sec)
    with wave.open(str(wav_path), "w") as wav_file:
        wav_file.setnchannels(1)  # Mono
        wav_file.setsampwidth(2)  # 16-bit
        wav_file.setframerate(sample_rate)
        for i in range(num_samples):
            value = int(32767.0 * 0.5 * math.sin(2.0 * math.pi * frequency * (i / sample_rate)))
            data = struct.pack("<h", value)
            wav_file.writeframesraw(data)


def create_ocr_images():
    # Create an image with clear readable text
    width, height = 650, 260
    bg_color = (255, 255, 255)
    text_color = (10, 10, 10)

    # 1. PNG Image
    img_png = Image.new("RGB", (width, height), bg_color)
    draw_png = ImageDraw.Draw(img_png)

    # Use default font
    lines = [
        "HOA DON BAN HANG",
        "Ma so: HD-2026-9999",
        "Khach hang: NGUYEN VAN A",
        "Tong thanh toan: 5.000.000 VND",
        "Trang thai: DA THANH TOAN",
    ]
    y = 25
    for line in lines:
        draw_png.text((35, y), line, fill=text_color)
        y += 40

    png_path = FIXTURES_DIR / "receipt_ocr.png"
    img_png.save(png_path, "PNG")

    # 2. JPG Image
    jpg_path = FIXTURES_DIR / "receipt_ocr.jpg"
    img_png.save(jpg_path, "JPEG", quality=95)


def create_pdf_with_image():
    # Create PDF embedding the OCR receipt image using PyMuPDF (fitz)
    try:
        import pymupdf

        doc = pymupdf.open()
        page = doc.new_page(width=612, height=792)  # Standard Letter

        # Insert some text
        page.insert_text((50, 50), "Bao Cao Tai Lieu Dinh Kem", fontsize=16)

        # Insert OCR image
        png_path = FIXTURES_DIR / "receipt_ocr.png"
        if png_path.exists():
            rect = pymupdf.Rect(50, 100, 550, 300)
            page.insert_image(rect, filename=str(png_path))

        pdf_path = FIXTURES_DIR / "scanned_doc.pdf"
        doc.save(str(pdf_path))
        doc.close()
    except Exception as e:
        print(f"Warning: could not create PDF via pymupdf: {e}")


def create_office_files():
    # 1. DOCX
    try:
        import docx

        doc = docx.Document()
        doc.add_heading("Hợp Đồng Dịch Vụ Phần Mềm", level=1)
        doc.add_paragraph("Bên A và Bên B thỏa thuận cung cấp dịch vụ chuyển đổi Markdown.")

        table = doc.add_table(rows=1, cols=3)
        hdr_cells = table.rows[0].cells
        hdr_cells[0].text = "STT"
        hdr_cells[1].text = "Hạng mục"
        hdr_cells[2].text = "Chi phí"

        row = table.add_row().cells
        row[0].text = "1"
        row[1].text = "API Service"
        row[2].text = "10.000.000 VND"

        docx_path = FIXTURES_DIR / "sample.docx"
        doc.save(str(docx_path))
    except Exception as e:
        print(f"Warning: could not create docx: {e}")

    # 2. XLSX
    try:
        import openpyxl

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "DoanhThu"
        ws.append(["Tháng", "Doanh thu", "Chi phí", "Lợi nhuận"])
        ws.append(["Tháng 1", 100000, 40000, 60000])
        ws.append(["Tháng 2", 120000, 45000, 75000])
        ws.append(["Tháng 3", 150000, 50000, 100000])

        xlsx_path = FIXTURES_DIR / "sample.xlsx"
        wb.save(str(xlsx_path))
    except Exception as e:
        print(f"Warning: could not create xlsx: {e}")


def generate_all():
    ensure_fixtures_dir()
    create_plain_text_files()
    create_media_audio()
    create_ocr_images()
    create_pdf_with_image()
    create_office_files()
    print(f"All test fixtures successfully generated in: {FIXTURES_DIR}")


if __name__ == "__main__":
    generate_all()

