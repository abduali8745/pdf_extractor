import streamlit as st
import os
import pandas as pd
import fitz  # PyMuPDF
from io import BytesIO
from PIL import Image

st.set_page_config(layout="wide")
st.title("أداة استخراج البيانات من ملفات PDF")

# يسمح للمستخدم برفع عدة ملفات PDF
uploaded_files = st.file_uploader(
    "ارفع ملفات PDF (يمكنك رفع عدة ملفات)",
    type="pdf",
    accept_multiple_files=True
)

# تخزين البيانات في الجلسة
if "data" not in st.session_state:
    st.session_state.data = []

# لمعرفة أي ملف نحن نعالجه حاليًا
if "current_index" not in st.session_state:
    st.session_state.current_index = 0

def pdf_to_image(pdf_bytes):
    """ يحول أول صفحة من ملف PDF إلى صورة لعرضها في Streamlit """
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    page = doc[0]  # أول صفحة
    pix = page.get_pixmap()
    img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
    return img

# إذا المستخدم رفع ملفات PDF
if uploaded_files:
    # قائمة الملفات
    files = uploaded_files
    
    # نحدد الملف الحالي
    current_file = files[st.session_state.current_index]
    pdf_bytes = current_file.read()

    # نقسم الصفحة إلى عمودين (يسار لعرض الـ PDF، يمين لإدخال البيانات)
    col1, col2 = st.columns(2)
    
    with col1:
        st.header("عرض صفحة PDF")
        # نحول الـ PDF لصورة ونعرضها
        pdf_image = pdf_to_image(pdf_bytes)
        st.image(pdf_image, use_column_width=True)

    with col2:
        st.header("أدخل البيانات يدويًا")
        input_dict = {}
        file_name = current_file.name

        input_dict["file_name"] = file_name
        input_dict["supplier_name"] = st.text_input("اسم المورد")
        input_dict["invoice_number"] = st.text_input("رقم الفاتورة")
        input_dict["date"] = st.text_input("تاريخ الفاتورة (مثل 2023-01-01)")
        input_dict["total"] = st.text_input("المبلغ الإجمالي")
        input_dict["notes"] = st.text_area("ملاحظات")

        # زر الحفظ والانتقال للملف التالي
        if st.button("حفظ والانتقال إلى التالي"):
            st.session_state.data.append(input_dict)
            st.session_state.current_index += 1
            # إذا خلصنا كل الملفات، نظهر رسالة نجاح
            if st.session_state.current_index >= len(files):
                st.success("تم الانتهاء من جميع الملفات!")
            st.experimental_rerun()

# عندما ينتهي المستخدم من كل الملفات أو يرفع ملفات جديدة
if st.session_state.data and st.session_state.current_index >= len(uploaded_files):
    st.header("البيانات المستخرجة")
    df = pd.DataFrame(st.session_state.data)
    st.dataframe(df)

    # حفظ النتائج إلى ملف Excel
    output = BytesIO()
    df.to_excel(output, index=False)
    st.download_button("تحميل البيانات كـ Excel", output.getvalue(), "extracted_data.xlsx")
