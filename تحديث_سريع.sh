#!/bin/bash
# سكريبت تحديث سريع للسيرفر - 2025-10-19

echo "=========================================="
echo "   تحديث تطبيق Kitchen Factory"
echo "=========================================="

# الألوان
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# المتغيرات
APP_DIR="$HOME/kitchen_factory"
BACKUP_DIR="$APP_DIR/instance"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="backup_${TIMESTAMP}.db"

# الدخول للمجلد
cd $APP_DIR || {
    echo -e "${RED}❌ خطأ: لم يتم العثور على مجلد التطبيق${NC}"
    exit 1
}

# 1. إيقاف التطبيق
echo -e "\n${YELLOW}[1/6]${NC} إيقاف التطبيق..."
sudo systemctl stop kitchen_factory.service 2>/dev/null || true
pkill -f "python.*app.py" || true
sleep 2
echo -e "${GREEN}✓${NC} تم إيقاف التطبيق"

# 2. النسخ الاحتياطي
echo -e "\n${YELLOW}[2/6]${NC} إنشاء نسخة احتياطية..."
if [ -f "$BACKUP_DIR/kitchen_factory.db" ]; then
    cp "$BACKUP_DIR/kitchen_factory.db" "$BACKUP_DIR/$BACKUP_FILE"
    echo -e "${GREEN}✓${NC} تم إنشاء: $BACKUP_FILE"
else
    echo -e "${YELLOW}⚠${NC} لم يتم العثور على قاعدة بيانات للنسخ"
fi

# 3. تنزيل التحديثات
echo -e "\n${YELLOW}[3/6]${NC} تنزيل التحديثات من GitHub..."
git fetch origin
git pull origin main
if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓${NC} تم تنزيل التحديثات بنجاح"
    git log -1 --oneline
else
    echo -e "${RED}❌ فشل تنزيل التحديثات${NC}"
    exit 1
fi

# 4. تفعيل البيئة الافتراضية
echo -e "\n${YELLOW}[4/6]${NC} تفعيل البيئة الافتراضية..."
source venv/bin/activate
echo -e "${GREEN}✓${NC} تم تفعيل البيئة الافتراضية"

# 5. إعادة تشغيل التطبيق
echo -e "\n${YELLOW}[5/6]${NC} إعادة تشغيل التطبيق..."
# محاولة systemd أولاً
if systemctl is-enabled kitchen_factory.service 2>/dev/null; then
    sudo systemctl start kitchen_factory.service
    echo -e "${GREEN}✓${NC} تم التشغيل عبر systemd"
else
    # التشغيل اليدوي
    nohup python app.py > app.log 2>&1 &
    APP_PID=$!
    echo -e "${GREEN}✓${NC} تم التشغيل يدوياً - PID: $APP_PID"
fi

# 6. التحقق
echo -e "\n${YELLOW}[6/6]${NC} التحقق من التشغيل..."
sleep 3
if ps aux | grep -v grep | grep "python.*app.py" > /dev/null; then
    echo -e "${GREEN}✓${NC} التطبيق يعمل بنجاح!"
    ps aux | grep -v grep | grep "python.*app.py" | awk '{print "   PID: " $2 " | CPU: " $3 "% | MEM: " $4 "%"}'
else
    echo -e "${RED}❌ التطبيق لا يعمل!${NC}"
    echo "تحقق من اللوج:"
    echo "  tail -50 app.log"
    exit 1
fi

# عرض معلومات إضافية
echo -e "\n${GREEN}=========================================="
echo "   ✅ اكتمل التحديث بنجاح!"
echo "==========================================${NC}"
echo ""
echo "📋 معلومات التحديث:"
echo "   • الوقت: $(date '+%Y-%m-%d %H:%M:%S')"
echo "   • النسخة الاحتياطية: $BACKUP_FILE"
echo "   • آخر commit: $(git log -1 --oneline)"
echo ""
echo "🔗 رابط التطبيق:"
echo "   http://102.213.180.235:4012"
echo ""
echo "📊 لمراقبة اللوج:"
echo "   tail -f $APP_DIR/app.log"
echo ""

