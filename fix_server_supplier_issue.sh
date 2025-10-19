#!/bin/bash
# سكريبت إصلاح مشكلة الموردين على السيرفر
# تاريخ: 2025-10-19

echo "=========================================="
echo "🔧 إصلاح مشكلة جداول الموردين على السيرفر"
echo "=========================================="
echo ""

# الألوان
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 1. إيقاف التطبيق
echo "🛑 الخطوة 1: إيقاف التطبيق..."
pkill -f "python.*app.py" || true
sleep 2
echo -e "${GREEN}✅ تم إيقاف التطبيق${NC}"
echo ""

# 2. الانتقال لمجلد التطبيق
echo "📁 الخطوة 2: الانتقال لمجلد التطبيق..."
cd ~/kitchen_factory/kitchen_factory
source ../venv/bin/activate
echo -e "${GREEN}✅ تم تفعيل البيئة${NC}"
echo ""

# 3. عمل نسخة احتياطية
echo "💾 الخطوة 3: عمل نسخة احتياطية..."
BACKUP_NAME="kitchen_factory.db.backup_before_fix_$(date +%Y%m%d_%H%M%S)"
cp instance/kitchen_factory.db instance/$BACKUP_NAME
echo -e "${GREEN}✅ تم حفظ النسخة الاحتياطية: $BACKUP_NAME${NC}"
echo ""

# 4. تشغيل سكريبت الإصلاح
echo "🔧 الخطوة 4: تشغيل سكريبت الإصلاح..."
python fix_server_supplier_tables.py

if [ $? -ne 0 ]; then
    echo -e "${RED}❌ فشل سكريبت الإصلاح!${NC}"
    echo -e "${YELLOW}⚠️  استرجاع النسخة الاحتياطية...${NC}"
    cp instance/$BACKUP_NAME instance/kitchen_factory.db
    echo -e "${GREEN}✅ تم استرجاع النسخة الاحتياطية${NC}"
    exit 1
fi

echo -e "${GREEN}✅ تم الإصلاح بنجاح${NC}"
echo ""

# 5. تشغيل التطبيق
echo "🚀 الخطوة 5: تشغيل التطبيق..."
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

# 6. عرض الملخص
echo "=========================================="
echo "✅ تم إصلاح المشكلة بنجاح!"
echo "=========================================="
echo ""
echo "📊 الملخص:"
echo "   • تم إيقاف التطبيق"
echo "   • تم عمل نسخة احتياطية: $BACKUP_NAME"
echo "   • تم إصلاح جداول الموردين"
echo "   • التطبيق يعمل على PID: $PID"
echo ""
echo "🔍 للتحقق:"
echo "   • السجلات: tail -f ~/kitchen_factory_app.log"
echo "   • الحالة: ps aux | grep app.py"
echo "   • المتصفح: http://$(hostname -I | awk '{print $1}'):4012"
echo ""
echo "🎯 يمكنك الآن إضافة موردين جدد بدون مشاكل!"
echo ""
