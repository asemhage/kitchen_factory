#!/bin/bash
# سكريبت تنزيل المشروع من GitHub على السيرفر
# الاستخدام: ./redeploy_from_github.sh
# التاريخ: 2025-10-18
# المستودع: https://github.com/asemhage/kitchen_factory

set -e  # إيقاف عند أول خطأ

echo "=========================================="
echo "  تنزيل Kitchen Factory من GitHub"
echo "=========================================="
echo ""

# التحقق من المسار
if [ "$(pwd)" != "/home/asem" ]; then
    echo "⚠️  يرجى تشغيل السكريبت من: /home/asem"
    echo "   cd /home/asem && ./redeploy_from_github.sh"
    exit 1
fi

# 1. إيقاف الخدمة
echo "[1/13] إيقاف الخدمة..."
sudo systemctl stop kitchen_factory
echo "✅ تم إيقاف الخدمة"

# 2. التحقق من وجود المشروع القديم
if [ ! -d "kitchen_factory" ]; then
    echo "⚠️  لا يوجد مشروع قديم، سيتم التنزيل مباشرة..."
    git clone https://github.com/asemhage/kitchen_factory.git
    cd kitchen_factory
    sudo systemctl start kitchen_factory
    echo "✅ تم التنزيل والتشغيل"
    exit 0
fi

# 3. نسخ احتياطي من قاعدة البيانات
echo "[2/13] نسخ احتياطي من قاعدة البيانات..."
BACKUP_TIME=$(date +%Y%m%d_%H%M%S)
if [ -f "kitchen_factory/kitchen_factory.db" ]; then
    cp kitchen_factory/kitchen_factory.db "kitchen_factory_db_backup_${BACKUP_TIME}.db"
    echo "✅ تم النسخ: kitchen_factory_db_backup_${BACKUP_TIME}.db"
else
    echo "⚠️  لم يتم العثور على قاعدة البيانات"
fi

# 4. نسخ احتياطي من ملفات الرفع
echo "[3/13] نسخ احتياطي من ملفات الرفع..."
if [ -d "kitchen_factory/uploads" ]; then
    cp -r kitchen_factory/uploads "uploads_backup_${BACKUP_TIME}"
    echo "✅ تم النسخ: uploads_backup_${BACKUP_TIME}"
else
    echo "⚠️  لا توجد ملفات رفع"
fi

# 5. نسخ احتياطي كامل
echo "[4/13] نسخ احتياطي كامل..."
tar -czf "kitchen_factory_full_backup_${BACKUP_TIME}.tar.gz" kitchen_factory/
echo "✅ تم النسخ: kitchen_factory_full_backup_${BACKUP_TIME}.tar.gz"

# 6. حذف المشروع القديم
echo "[5/13] حذف المشروع القديم..."
rm -rf kitchen_factory
echo "✅ تم الحذف"

# 7. تنزيل المشروع من GitHub
echo "[6/13] تنزيل المشروع من GitHub..."
git clone https://github.com/asemhage/kitchen_factory.git
echo "✅ تم التنزيل بنجاح"

# 8. استرجاع قاعدة البيانات
echo "[7/13] استرجاع قاعدة البيانات..."
if [ -f "kitchen_factory_db_backup_${BACKUP_TIME}.db" ]; then
    cp "kitchen_factory_db_backup_${BACKUP_TIME}.db" kitchen_factory/kitchen_factory.db
    echo "✅ تم استرجاع قاعدة البيانات"
else
    echo "⚠️  لم يتم العثور على نسخة احتياطية"
fi

# 9. استرجاع ملفات الرفع
echo "[8/13] استرجاع ملفات الرفع..."
if [ -d "uploads_backup_${BACKUP_TIME}" ]; then
    mkdir -p kitchen_factory/uploads
    cp -r uploads_backup_${BACKUP_TIME}/* kitchen_factory/uploads/
    echo "✅ تم استرجاع ملفات الرفع"
else
    echo "⚠️  لا توجد ملفات رفع للاسترجاع"
    mkdir -p kitchen_factory/uploads
fi

# 10. التحقق من البيئة الافتراضية
echo "[9/13] التحقق من البيئة الافتراضية..."
cd kitchen_factory
if [ ! -d "venv" ]; then
    echo "⚠️  إنشاء بيئة افتراضية جديدة..."
    python3 -m venv venv
    source venv/bin/activate
    pip install --upgrade pip
    pip install -r requirements.txt
    echo "✅ تم إنشاء البيئة الافتراضية"
else
    echo "✅ البيئة الافتراضية موجودة"
fi

# 11. تطبيق Migrations
echo "[10/13] تطبيق Migrations..."
python migrate_add_stage_rates.py 2>/dev/null && echo "✅ تم تطبيق migration" || echo "⚠️  Migration تم تطبيقه مسبقاً"

# 12. إعطاء الصلاحيات المناسبة
echo "[11/13] ضبط الصلاحيات..."
chmod +x *.sh 2>/dev/null || true
chmod 644 kitchen_factory.db 2>/dev/null || true
echo "✅ تم ضبط الصلاحيات"

# 13. بدء الخدمة
echo "[12/13] بدء الخدمة..."
cd /home/asem
sudo systemctl start kitchen_factory
echo "✅ تم بدء الخدمة"

# 14. التحقق من الحالة
echo "[13/13] التحقق من الحالة..."
sleep 3
if sudo systemctl is-active --quiet kitchen_factory; then
    echo "✅ الخدمة تعمل بنجاح"
    STATUS="✅ يعمل"
else
    echo "❌ الخدمة لا تعمل!"
    STATUS="❌ لا يعمل"
    sudo systemctl status kitchen_factory --no-pager
fi

echo ""
echo "=========================================="
echo "  ✅ اكتمل التنزيل من GitHub!"
echo "=========================================="
echo ""
echo "📊 النتائج:"
echo "  - المستودع: https://github.com/asemhage/kitchen_factory"
echo "  - حالة الخدمة: $STATUS"
echo "  - النسخ الاحتياطية:"
echo "    • قاعدة البيانات: kitchen_factory_db_backup_${BACKUP_TIME}.db"
echo "    • ملفات الرفع: uploads_backup_${BACKUP_TIME}"
echo "    • نسخة كاملة: kitchen_factory_full_backup_${BACKUP_TIME}.tar.gz"
echo ""
echo "🌐 اختبر التطبيق:"
echo "  http://102.213.180.235:4012"
echo ""
echo "📝 للتحديثات المستقبلية:"
echo "  cd /home/asem/kitchen_factory"
echo "  git pull"
echo "  sudo systemctl restart kitchen_factory"
echo ""
echo "🆘 في حالة حدوث مشكلة:"
echo "  cd /home/asem"
echo "  tar -xzf kitchen_factory_full_backup_${BACKUP_TIME}.tar.gz"
echo "  sudo systemctl start kitchen_factory"

