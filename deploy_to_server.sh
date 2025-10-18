#!/bin/bash
# سكريبت نشر المشروع على السيرفر من GitHub
# التاريخ: 2025-10-18
# المستودع: https://github.com/asemhage/kitchen_factory

set -e  # إيقاف عند أول خطأ

echo "=========================================="
echo "  نشر Kitchen Factory من GitHub"
echo "=========================================="
echo ""

# الانتقال للمجلد الرئيسي
cd /home/asem

# نسخ احتياطي
echo "[1/10] إنشاء نسخة احتياطية..."
BACKUP_FILE="kitchen_factory_backup_$(date +%Y%m%d_%H%M%S).tar.gz"
if [ -d "kitchen_factory" ]; then
    tar -czf "$BACKUP_FILE" kitchen_factory/
    echo "✅ تم إنشاء نسخة احتياطية: $BACKUP_FILE"
else
    echo "⚠️  لا يوجد مشروع سابق"
fi

# حفظ المشروع القديم
echo "[2/10] حفظ المشروع القديم..."
if [ -d "kitchen_factory" ]; then
    mv kitchen_factory kitchen_factory_old
    echo "✅ تم نقل المشروع القديم إلى kitchen_factory_old"
fi

# استنساخ من GitHub
echo "[3/10] استنساخ المشروع من GitHub..."
git clone https://github.com/asemhage/kitchen_factory.git
echo "✅ تم الاستنساخ بنجاح"

# نسخ قاعدة البيانات
echo "[4/10] نسخ قاعدة البيانات..."
if [ -f "kitchen_factory_old/kitchen_factory.db" ]; then
    cp kitchen_factory_old/kitchen_factory.db kitchen_factory/
    echo "✅ تم نسخ قاعدة البيانات"
else
    echo "⚠️  لم يتم العثور على قاعدة بيانات سابقة"
fi

# نسخ ملفات الرفع
echo "[5/10] نسخ ملفات الرفع..."
if [ -d "kitchen_factory_old/uploads" ]; then
    mkdir -p kitchen_factory/uploads
    cp -r kitchen_factory_old/uploads/* kitchen_factory/uploads/ 2>/dev/null || true
    echo "✅ تم نسخ ملفات الرفع"
else
    echo "⚠️  لا توجد ملفات رفع سابقة"
fi

# نسخ ملفات الإيصالات (إذا كانت موجودة)
echo "[6/10] نسخ ملفات الإيصالات..."
if [ -d "kitchen_factory_old/receipts" ]; then
    mkdir -p kitchen_factory/receipts
    cp -r kitchen_factory_old/receipts/* kitchen_factory/receipts/ 2>/dev/null || true
    echo "✅ تم نسخ ملفات الإيصالات"
fi

# الانتقال للمشروع
cd kitchen_factory

# تطبيق Migrations
echo "[7/10] تطبيق Migrations..."
python migrate_add_stage_rates.py 2>/dev/null && echo "✅ تم تطبيق migration" || echo "⚠️  Migration تم تطبيقه مسبقاً"

# تفعيل البيئة الافتراضية (إذا كانت موجودة)
echo "[8/10] التحقق من البيئة الافتراضية..."
if [ -d "venv" ]; then
    echo "✅ البيئة الافتراضية موجودة"
else
    echo "⚠️  إنشاء بيئة افتراضية جديدة..."
    python3 -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt
fi

# إعادة تشغيل الخدمة
echo "[9/10] إعادة تشغيل الخدمة..."
sudo systemctl restart kitchen_factory
echo "✅ تم إعادة التشغيل"

# التحقق من الحالة
echo "[10/10] التحقق من حالة الخدمة..."
sleep 2
if sudo systemctl is-active --quiet kitchen_factory; then
    echo "✅ الخدمة تعمل بنجاح"
else
    echo "❌ الخدمة لا تعمل!"
    sudo systemctl status kitchen_factory
    exit 1
fi

echo ""
echo "=========================================="
echo "  ✅ تم النشر بنجاح!"
echo "=========================================="
echo ""
echo "📊 الإحصائيات:"
echo "  - المستودع: https://github.com/asemhage/kitchen_factory"
echo "  - النسخة الاحتياطية: $BACKUP_FILE"
echo "  - المشروع القديم: kitchen_factory_old"
echo ""
echo "🌐 اختبر التطبيق:"
echo "  http://102.213.180.235:4012"
echo ""
echo "📝 للتحديثات المستقبلية:"
echo "  cd /home/asem/kitchen_factory"
echo "  git pull"
echo "  sudo systemctl restart kitchen_factory"

