import streamlit as st
import pandas as pd
import pytesseract
import fitz  # PyMuPDF
from PIL import Image
from io import BytesIO
from streamlit_drawable_canvas import st_canvas

# لو عندك Tesseract في مسار مختلف:
# pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

st.set_page_config(layout="wide")
st.title("أداة استخراج البيانات من ملفات PDF (تحديد مربعات)")

# نحتفظ بالنتائج في جلسة المستخدم
if "extracted_data" not in st.session_state:
    st.session_state["extracted_data"] = []

# رفع ملفات PDF متعددة
uploaded_files = st.file_uploader(
    "ارفع ملفات PDF (يمكن رفع عدة ملفات)",
    type=["pdf"],
    accept_multiple_files=True
)

if "current_index" not in st.session_state:
    st.session_state["current_index"] = 0

def pdf_page_to_image(pdf_bytes, page_index=0):
    """حوّل صفحة محددة من PDF إلى صورة PIL."""
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    if page_index >= len(doc):
        page_index = 0
    page = doc[page_index]
    pix = page.get_pixmap()
    img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
    return img, len(doc)

def ocr_image_part(img, left, top, width, height, lang="ara+eng"):
    """قص جزء (مربع) من الصورة وتشغيل OCR عليه."""
    box = (left, top, left + width, top + height)
    cropped_img = img.crop(box)
    text = pytesseract.image_to_string(cropped_img, lang=lang)
    return text.strip()

# إذا رُفعت ملفات
if uploaded_files:
    files = uploaded_files

    # الملف الحالي
    current_file = files[st.session_state.current_index]
    pdf_bytes = current_file.read()

    # اختيار الصفحة
    doc_temp = fitz.open(stream=pdf_bytes, filetype="pdf")
    total_pages = len(doc_temp)
    page_number = st.number_input(
        "اختر رقم الصفحة للمعاينة (الصفرية)",
        min_value=0,
        max_value=total_pages - 1,
        value=0
    )

    # تحويل الصفحة المختارة إلى صورة
    pdf_image, page_count = pdf_page_to_image(pdf_bytes, page_index=page_number)
    w, h = pdf_image.size

    col1, col2 = st.columns(2)

    with col1:
        st.subheader(f"ملف: {current_file.name}")
        st.write(f"عدد الصفحات: {page_count}, تشاهد الصفحة رقم: {page_number}")

        # نعرض Canvas ليتمكن المستخدم من رسم مربعات
        canvas_result = st_canvas(
            fill_color="rgba(255, 255, 255, 0.1)",
            stroke_width=2,
            stroke_color="#FF0000",
            background_image=pdf_image,
            update_streamlit=True,
            drawing_mode="rect",
            width=w,
            height=h,
            key=f"canvas_{st.session_state.current_index}_{page_number}",
        )

        # زر لاستخراج النص من كل المربعات
        if st.button("استخراج النص من المربعات المرسومة"):
            if canvas_result.json_data is not None:
                objects = canvas_result.json_data["objects"]
                if not objects:
                    st.warning("لم ترسم أي مربع بعد.")
                else:
                    extracted_texts = {}
                    for i, obj in enumerate(objects):
                        left = int(obj["left"])
                        top = int(obj["top"])
                        width_box = int(obj["width"])
                        height_box = int(obj["height"])

                        text = ocr_image_part(pdf_image, left, top, width_box, height_box, lang="ara+eng")
                        extracted_texts[f"المربع {i+1}"] = text

                    # عرض النتائج
                    st.write("**النصوص المستخرجة**:")
                    for k, v in extracted_texts.items():
                        st.write(f"**{k}:** {v}")

                    # المستخدم قد يختار ملء الحقول تلقائيًا أو يدويًا
                    # مثلاً نعبي في session لصفحة ملء تلقائي:
                    st.session_state["last_extracted"] = extracted_texts

    with col2:
        st.subheader("أدخل البيانات يدويًا أو الصقها من OCR")

        # لو استخرجنا نصًا للتو، نعرضه ليسهل النسخ
        if "last_extracted" in st.session_state:
            st.write("**النصوص OCR:**", st.session_state["last_extracted"])

        input_dict = {}
        input_dict["file_name"] = current_file.name
        input_dict["page_number"] = page_number
        input_dict["supplier_name"] = st.text_input("اسم المورد")
        input_dict["invoice_number"] = st.text_input("رقم الفاتورة")
        input_dict["date"] = st.text_input("تاريخ الفاتورة (مثل 2023-01-01)")
        input_dict["total"] = st.text_input("المبلغ الإجمالي")
        input_dict["notes"] = st.text_area("ملاحظات")

        if st.button("حفظ البيانات لهذه الصفحة"):
            st.session_state["extracted_data"].append(input_dict)
            st.success("تم حفظ البيانات لهذه الصفحة.")

    # زر للانتقال للملف التالي
    st.markdown("---")
    if st.button("التالي >>"):
        st.session_state.current_index += 1
        if st.session_state.current_index >= len(files):
            st.session_state.current_index = len(files)
            st.success("انتهت الملفات")
        st.experimental_rerun()

# عند الانتهاء من كل الملفات
if st.session_state["extracted_data"] and st.session_state.current_index >= len(uploaded_files):
    st.header("كل البيانات المستخرجة والمحفوظة")
    df = pd.DataFrame(st.session_state["extracted_data"])
    st.dataframe(df)

    # زر تحميل Excel
    output = BytesIO()
    df.to_excel(output, index=False)
    st.download_button("تنزيل Excel", output.getvalue(), "extracted_data.xlsx")
