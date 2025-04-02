import streamlit as st
import fitz  # PyMuPDF
import pandas as pd
from PIL import Image
from io import BytesIO
import easyocr
import numpy as np
from streamlit_drawable_canvas import st_canvas

# ---------------------------------------------------------------------------------
#  إعداد واجهة التطبيق والضبط العام
# ---------------------------------------------------------------------------------

st.set_page_config(layout="wide", page_title="أداة استخراج البيانات من PDF")
st.title("أداة استخراج البيانات من ملفات PDF - تحديد مربعات + EasyOCR")

# ---------------------------------------------------------------------------------
#  تهيئة EasyOCR
# ---------------------------------------------------------------------------------
# - نختار اللغات: ar للغة العربية + en للغة الإنجليزية
# - قد تحمل EasyOCR ملفات اللغة في أول مرة، لذا قد يستغرق الأمر بعض الوقت
reader = easyocr.Reader(["ar", "en"], gpu=False)

# ---------------------------------------------------------------------------------
#  session_state لتخزين البيانات بين الصفحات
# ---------------------------------------------------------------------------------
if "data_rows" not in st.session_state:
    st.session_state["data_rows"] = []  # قائمة من القواميس

if "current_file_index" not in st.session_state:
    st.session_state["current_file_index"] = 0

# ---------------------------------------------------------------------------------
#  دالة لتحويل صفحة من PDF إلى صورة
# ---------------------------------------------------------------------------------
def pdf_page_to_image(pdf_bytes, page_index=0):
    """إرجاع (صورة من الصفحة المختارة, عدد الصفحات)"""
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    total_pages = len(doc)
    if page_index >= total_pages:
        page_index = 0
    page = doc[page_index]
    pix = page.get_pixmap()
    img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
    return img, total_pages

# ---------------------------------------------------------------------------------
#  دالة لاستخراج النص من منطقة محددة في الصورة عبر EasyOCR
# ---------------------------------------------------------------------------------
def easyocr_extract_subimage(img, left, top, width, height):
    """
    قص المنطقة (left, top, right=left+width, bottom=top+height) من الصورة
    ثم استخدم EasyOCR لاستخراج النص.
    """
    cropped = img.crop((left, top, left + width, top + height))
    # EasyOCR يتوقع مصفوفة NumPy
    cropped_np = np.array(cropped)
    result = reader.readtext(cropped_np, detail=0)  # detail=0 يعطينا النص فقط
    text = "\n".join(result).strip()
    return text

# ---------------------------------------------------------------------------------
#  واجهة رفع الملفات
# ---------------------------------------------------------------------------------
uploaded_files = st.file_uploader(
    "ارفع ملفات PDF (يمكنك رفع عدة ملفات)",
    type=["pdf"],
    accept_multiple_files=True
)

# ---------------------------------------------------------------------------------
#  إذا رفعنا ملفات، نعالج الملف الحالي
# ---------------------------------------------------------------------------------
if uploaded_files:
    files = uploaded_files
    current_index = st.session_state["current_file_index"]

    # التأكد ألا نتجاوز عدد الملفات
    if current_index >= len(files):
        st.success("انتهت كل الملفات!")
    else:
        # الملف الحالي
        current_file = files[current_index]
        pdf_bytes = current_file.read()

        # اختيار الصفحة
        with st.sidebar:
            st.markdown("## التحكم في الصفحة:")
            doc_temp = fitz.open(stream=pdf_bytes, filetype="pdf")
            total_pages = len(doc_temp)
            page_number = st.number_input(
                "اختر رقم الصفحة (صفرية)",
                min_value=0,
                max_value=total_pages - 1,
                value=0
            )

        # تحويل الصفحة لصورة
        pdf_img, total_page_count = pdf_page_to_image(pdf_bytes, page_index=page_number)

        st.subheader(f"معاينة: {current_file.name} (صفحة {page_number} / {total_page_count - 1})")

        w, h = pdf_img.size

        # ---------------------------------------------------------------------------------
        #  رسم المربعات على الصورة (Canvas)
        # ---------------------------------------------------------------------------------
        st.write("### ارسم مربعات حول المناطق المراد استخراج النص منها (EasyOCR):")
        canvas_result = st_canvas(
            fill_color="rgba(255, 255, 255, 0.0)",
            stroke_width=2,
            stroke_color="#FF0000",
            background_image=pdf_img,
            update_streamlit=True,
            drawing_mode="rect",
            width=w,
            height=h,
            key=f"canvas_{current_index}_{page_number}",
        )

        # زر لاستخراج النص من المربعات
        if st.button("استخراج النص من المربعات"):
            if canvas_result.json_data is not None:
                objects = canvas_result.json_data["objects"]
                if not objects:
                    st.warning("لم تقم برسم أي مربع بعد.")
                else:
                    st.write("#### النتائج الأولية من EasyOCR:")
                    extracted_texts = {}
                    for i, obj in enumerate(objects):
                        # إحداثيات المربع
                        left = int(obj["left"])
                        top = int(obj["top"])
                        width_box = int(obj["width"])
                        height_box = int(obj["height"])

                        text_ocr = easyocr_extract_subimage(pdf_img, left, top, width_box, height_box)
                        extracted_texts[f"مربع_{i+1}"] = text_ocr

                    # عرض النصوص أمام المستخدم
                    for name, val in extracted_texts.items():
                        st.write(f"**{name}:**\n{val}\n")

                    # حفظ هذه النصوص في session_state إذا أردت
                    st.session_state["last_ocr"] = extracted_texts
            else:
                st.warning("Canvas فارغ، تأكد من الرسم أو إعادة المحاولة.")

        # ---------------------------------------------------------------------------------
        #  تعبئة بيانات الفاتورة يدوياً (باختيار نص من OCR أو كتابته)
        # ---------------------------------------------------------------------------------
        st.write("---")
        st.write("### تعبئة بيانات الفاتورة:")
        if "last_ocr" not in st.session_state:
            st.session_state["last_ocr"] = {}

        input_dict = {}
        input_dict["file_name"] = current_file.name
        input_dict["page_number"] = page_number

        # مثال لحقول
        # بإمكانك أن تنسخ النص من مربعات OCR أعلاه.
        col_left, col_right = st.columns(2)
        with col_left:
            input_dict["supplier_name"] = st.text_input("اسم المورد", value="")
            input_dict["invoice_number"] = st.text_input("رقم الفاتورة", value="")
        with col_right:
            input_dict["date"] = st.text_input("تاريخ الفاتورة (YYYY-MM-DD)")
            input_dict["total"] = st.text_input("المبلغ الإجمالي")

        input_dict["notes"] = st.text_area("ملاحظات إضافية")

        if st.button("حفظ بيانات هذه الصفحة"):
            st.session_state["data_rows"].append(input_dict)
            st.success("تم حفظ بيانات هذه الصفحة!")

        # ---------------------------------------------------------------------------------
        #  زر الانتقال للملف التالي
        # ---------------------------------------------------------------------------------
        st.write("---")
        if st.button(">> التالي"):
            st.session_state["current_file_index"] += 1
            if st.session_state["current_file_index"] >= len(files):
                st.success("تمت معالجة كل الملفات!")
            st.experimental_rerun()

# ---------------------------------------------------------------------------------
#  عند انتهاء كل الملفات أو في أي وقت، عرض النتائج وتنزيلها
# ---------------------------------------------------------------------------------
if st.session_state["data_rows"] and (not uploaded_files or st.session_state["current_file_index"] >= len(uploaded_files)):
    st.header("البيانات التي تم جمعها:")
    df = pd.DataFrame(st.session_state["data_rows"])
    st.dataframe(df)

    # زر لتنزيل Excel
    output = BytesIO()
    df.to_excel(output, index=False)
    st.download_button("تحميل النتائج كـ Excel", output.getvalue(), file_name="extracted_data.xlsx")
