#!/bin/bash
# سكريبت تحديث السيرفر - نظام الموردين الجديد
# تاريخ: 2025-10-19

echo "=========================================="
echo "🔄 بدء تحديث نظام الموردين على السيرفر"
echo "=========================================="
echo ""

# الألوان
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 1. التحديث من GitHub
echo "📥 الخطوة 1: سحب التحديثات من GitHub..."
cd ~/kitchen_factory
git pull origin main

if [ $? -ne 0 ]; then
    echo -e "${RED}❌ فشل سحب التحديثات من GitHub${NC}"
    exit 1
fi

echo -e "${GREEN}✅ تم سحب التحديثات بنجاح${NC}"
echo ""

# 2. إيقاف التطبيق
echo "🛑 الخطوة 2: إيقاف التطبيق..."

# محاولة إيقاف systemd (قد يفشل)
sudo systemctl stop kitchen_factory 2>/dev/null || true

# إيقاف يدوي
pkill -f "python.*app.py" || true

sleep 2

echo -e "${GREEN}✅ تم إيقاف التطبيق${NC}"
echo ""

# 3. تفعيل البيئة الافتراضية
echo "🐍 الخطوة 3: تفعيل البيئة الافتراضية..."
cd ~/kitchen_factory/kitchen_factory
source ../venv/bin/activate

echo -e "${GREEN}✅ تم تفعيل البيئة${NC}"
echo ""

# 4. نسخة احتياطية
echo "💾 الخطوة 4: عمل نسخة احتياطية..."
BACKUP_NAME="kitchen_factory.db.backup_before_supplier_rebuild_$(date +%Y%m%d_%H%M%S)"
cp instance/kitchen_factory.db instance/$BACKUP_NAME

echo -e "${GREEN}✅ تم حفظ النسخة الاحتياطية: $BACKUP_NAME${NC}"
echo ""

# 5. تشغيل سكريبت الترحيل
echo "🔄 الخطوة 5: تشغيل سكريبت إعادة البناء..."
echo -e "${YELLOW}⚠️  سيتم حذف جميع بيانات الموردين القديمة!${NC}"
echo ""

python migrate_supplier_system_rebuild.py

if [ $? -ne 0 ]; then
    echo -e "${RED}❌ فشل سكريبت الترحيل!${NC}"
    echo -e "${YELLOW}⚠️  استرجاع النسخة الاحتياطية...${NC}"
    cp instance/$BACKUP_NAME instance/kitchen_factory.db
    echo -e "${GREEN}✅ تم استرجاع النسخة الاحتياطية${NC}"
    exit 1
fi

echo -e "${GREEN}✅ تم الترحيل بنجاح${NC}"
echo ""

# 6. تشغيل التطبيق
echo "🚀 الخطوة 6: تشغيل التطبيق..."

nohup python app.py > ~/kitchen_factory_app.log 2>&1 &

sleep 3

# التحقق من التشغيل
if ps aux | grep -v grep | grep "python.*app.py" > /dev/null; then
    echo -e "${GREEN}✅ التطبيق يعمل بنجاح!${NC}"
    PID=$(ps aux | grep -v grep | grep "python.*app.py" | awk '{print $2}')
    echo -e "${GREEN}   PID: $PID${NC}"
else
    echo -e "${RED}❌ فشل تشغيل التطبيق!${NC}"
    echo -e "${YELLOW}   افحص السجلات: tail -50 ~/kitchen_factory_app.log${NC}"
    exit 1
fi

echo ""

# 7. عرض الملخص
echo "=========================================="
echo "✅ تم إكمال التحديث بنجاح!"
echo "=========================================="
echo ""
echo "📊 الملخص:"
echo "   • تم سحب التحديثات من GitHub"
echo "   • تم عمل نسخة احتياطية: $BACKUP_NAME"
echo "   • تم إعادة بناء نظام الموردين"
echo "   • التطبيق يعمل على PID: $PID"
echo ""
echo "🔍 للتحقق:"
echo "   • السجلات: tail -f ~/kitchen_factory_app.log"
echo "   • الحالة: ps aux | grep app.py"
echo "   • المتصفح: http://$(hostname -I | awk '{print $1}'):4012"
echo ""
echo "🎯 النظام الجديد جاهز للاستخدام!"
echo ""

