# 🔧 إصلاح مشكلة المربعات السوداء في PDF العربية

## 📋 **ملخص المشكلة:**
الحروف العربية تظهر كمربعات سوداء في إيصالات PDF بسبب:
- مسارات الخطوط مخصصة لـ Windows فقط
- عدم وجود خطوط عربية على السيرفر Linux
- مشاكل في معالجة النص العربي

---

## ✅ **ما تم إصلاحه:**

### **1️⃣ تحسين دالة تسجيل الخطوط:**
- ✅ إضافة مسارات Linux للخطوط
- ✅ إضافة مسارات macOS
- ✅ تحسين fallback للخطوط
- ✅ معالجة أفضل للأخطاء

### **2️⃣ تحسين معالجة النص العربي:**
- ✅ تحسين دالة `format_arabic_text()`
- ✅ معالجة أفضل للأخطاء
- ✅ التحقق من صحة النص

### **3️⃣ إضافة سكريبت تثبيت الخطوط:**
- ✅ `install_arabic_fonts.sh`
- ✅ تحميل خطوط Google Fonts
- ✅ تثبيت حزم الخطوط العربية

### **4️⃣ إضافة مسار اختبار:**
- ✅ `/test-fonts` لاختبار الخطوط
- ✅ عرض نتائج الاختبار

---

## 🚀 **خطوات التطبيق على السيرفر:**

### **المرحلة 1: تنزيل التحديثات**
```bash
# الاتصال بالسيرفر
ssh asem@102.213.180.235

# تنزيل التحديثات
cd ~/kitchen_factory
git pull origin main
```

### **المرحلة 2: تثبيت الخطوط العربية**
```bash
# إعطاء صلاحية التنفيذ
chmod +x install_arabic_fonts.sh

# تشغيل سكريبت تثبيت الخطوط
./install_arabic_fonts.sh
```

### **المرحلة 3: إعادة تشغيل التطبيق**
```bash
# إيقاف التطبيق
pkill -f "python.*app.py"

# إعادة التشغيل
cd ~/kitchen_factory
source venv/bin/activate
nohup python app.py > app.log 2>&1 &

# التحقق من التشغيل
ps aux | grep "python.*app.py"
```

### **المرحلة 4: اختبار الخطوط**
```bash
# اختبار الخطوط عبر المتصفح
curl http://102.213.180.235:4012/test-fonts

# أو افتح المتصفح على:
# http://102.213.180.235:4012/test-fonts
```

---

## 🔍 **اختبار الإصلاح:**

### **1️⃣ اختبار الخطوط:**
- اذهب إلى: `http://102.213.180.235:4012/test-fonts`
- يجب أن ترى رسالة نجاح أو تحذير

### **2️⃣ اختبار PDF:**
- اذهب إلى أي طلب
- اضغط "استلام العربون"
- تحقق من أن النصوص العربية تظهر بشكل صحيح

### **3️⃣ فحص اللوج:**
```bash
# مراقبة اللوج
tail -f ~/kitchen_factory/app.log

# البحث عن رسائل الخطوط
grep -i "خط" ~/kitchen_factory/app.log
grep -i "font" ~/kitchen_factory/app.log
```

---

## 🛠️ **استكشاف الأخطاء:**

### **إذا لم تعمل الخطوط:**

**1. فحص الخطوط المتاحة:**
```bash
# فحص الخطوط العربية
fc-list | grep -i arabic

# فحص خطوط Noto
fc-list | grep -i noto

# فحص خطوط المستخدم
ls ~/.fonts/
```

**2. اختبار الخطوط يدوياً:**
```bash
cd ~/kitchen_factory
python3 -c "
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase import pdfmetrics
import os

# اختبار الخطوط
font_paths = [
    '/usr/share/fonts/truetype/noto/NotoSansArabic-Regular.ttf',
    '~/.fonts/NotoSansArabic-Regular.ttf'
]

for font_path in font_paths:
    expanded_path = os.path.expanduser(font_path)
    if os.path.exists(expanded_path):
        try:
            pdfmetrics.registerFont(TTFont('TestFont', expanded_path))
            print(f'✅ {font_path} - يعمل')
        except Exception as e:
            print(f'❌ {font_path} - فشل: {str(e)}')
    else:
        print(f'⚠️ {font_path} - غير موجود')
"
```

**3. إعادة تثبيت الخطوط:**
```bash
# إعادة تشغيل سكريبت التثبيت
./install_arabic_fonts.sh

# أو تثبيت يدوي
sudo apt-get install -y fonts-noto-core fonts-arabeyes
fc-cache -fv
```

---

## 📊 **الملفات المعدلة:**

| الملف | التعديل |
|------|---------|
| `app.py` | دالة `register_arabic_fonts()` محسنة |
| `app.py` | دالة `format_arabic_text()` محسنة |
| `app.py` | دالة `generate_receipt_pdf()` محسنة |
| `app.py` | إضافة دالة `test_arabic_fonts()` |
| `app.py` | إضافة مسار `/test-fonts` |
| `install_arabic_fonts.sh` | سكريبت تثبيت الخطوط |

---

## ⚠️ **نقاط مهمة:**

1. **الخطوط**: يجب تثبيتها على السيرفر أولاً
2. **الصلاحيات**: قد تحتاج `sudo` لتثبيت الخطوط
3. **الاختبار**: اختبر الخطوط قبل التطبيق
4. **النسخ الاحتياطية**: احتفظ بنسخة من الكود الحالي

---

## 🎯 **النتيجة المتوقعة:**

بعد تطبيق الإصلاحات:
- ✅ النصوص العربية تظهر بشكل صحيح في PDF
- ✅ لا توجد مربعات سوداء
- ✅ الخطوط العربية تعمل على Linux
- ✅ fallback للخطوط الافتراضية

---

## 📞 **للدعم:**

إذا واجهت أي مشكلة:
1. تحقق من اللوج: `tail -f ~/kitchen_factory/app.log`
2. اختبر الخطوط: `http://102.213.180.235:4012/test-fonts`
3. أرسل رسائل الخطأ للدعم

---

✅ **آخر تحديث:** 2025-10-19  
🔗 **Commit:** 66913b1  
📦 **الملفات المعدلة:** 2 ملف  
🎯 **الهدف:** إصلاح مشكلة المربعات السوداء في PDF العربية
