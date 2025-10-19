#!/bin/bash
# سكريبت تثبيت الخطوط العربية للسيرفر

echo "=========================================="
echo "   تثبيت الخطوط العربية"
echo "=========================================="

# الألوان
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# إنشاء مجلد الخطوط
echo -e "\n${YELLOW}[1/6]${NC} إنشاء مجلد الخطوط..."
mkdir -p ~/.fonts
echo -e "${GREEN}✓${NC} تم إنشاء مجلد ~/.fonts"

# تثبيت حزم الخطوط العربية
echo -e "\n${YELLOW}[2/6]${NC} تثبيت حزم الخطوط العربية..."
sudo apt-get update
sudo apt-get install -y fonts-noto-core fonts-noto-ui-core fonts-arabeyes fonts-kacst fonts-khmeros-core
echo -e "${GREEN}✓${NC} تم تثبيت حزم الخطوط"

# تحميل خطوط Google Fonts
echo -e "\n${YELLOW}[3/6]${NC} تحميل خطوط Google Fonts..."

# Noto Sans Arabic
echo "📥 تحميل Noto Sans Arabic..."
wget -O noto-sans-arabic.zip "https://fonts.google.com/download?family=Noto%20Sans%20Arabic" 2>/dev/null
if [ -f noto-sans-arabic.zip ]; then
    unzip -q noto-sans-arabic.zip -d ~/.fonts/
    echo -e "${GREEN}✓${NC} تم تحميل Noto Sans Arabic"
    rm noto-sans-arabic.zip
else
    echo -e "${YELLOW}⚠${NC} فشل تحميل Noto Sans Arabic"
fi

# Amiri (خط عربي كلاسيكي)
echo "📥 تحميل Amiri..."
wget -O amiri.zip "https://fonts.google.com/download?family=Amiri" 2>/dev/null
if [ -f amiri.zip ]; then
    unzip -q amiri.zip -d ~/.fonts/
    echo -e "${GREEN}✓${NC} تم تحميل Amiri"
    rm amiri.zip
else
    echo -e "${YELLOW}⚠${NC} فشل تحميل Amiri"
fi

# تحديث cache الخطوط
echo -e "\n${YELLOW}[4/6]${NC} تحديث cache الخطوط..."
fc-cache -fv
echo -e "${GREEN}✓${NC} تم تحديث cache الخطوط"

# فحص الخطوط المتاحة
echo -e "\n${YELLOW}[5/6]${NC} فحص الخطوط المتاحة..."
echo "🔍 الخطوط العربية المتاحة:"
fc-list | grep -i arabic | head -5
echo ""
echo "🔍 خطوط Noto:"
fc-list | grep -i noto | head -5

# اختبار الخطوط
echo -e "\n${YELLOW}[6/6]${NC} اختبار الخطوط..."
python3 -c "
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase import pdfmetrics
import os

# اختبار الخطوط المتاحة
font_paths = [
    '/usr/share/fonts/truetype/noto/NotoSansArabic-Regular.ttf',
    '~/.fonts/NotoSansArabic-Regular.ttf',
    '~/.fonts/Amiri-Regular.ttf'
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

echo -e "\n${GREEN}=========================================="
echo "   ✅ اكتمل تثبيت الخطوط العربية!"
echo "==========================================${NC}"
echo ""
echo "📋 الخطوات التالية:"
echo "   1. إعادة تشغيل التطبيق"
echo "   2. اختبار توليد PDF"
echo "   3. التحقق من عرض النصوص العربية"
echo ""
echo "🔧 لإعادة تشغيل التطبيق:"
echo "   pkill -f 'python.*app.py'"
echo "   nohup python app.py > app.log 2>&1 &"
echo ""
