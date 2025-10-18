#!/bin/bash
# سكريبت إعداد Git على السيرفر
# الاستخدام: قم بنسخ ولصق هذه الأوامر في SSH

echo "=========================================="
echo "  إعداد Git للمشروع على السيرفر"
echo "=========================================="

# الانتقال للمجلد الرئيسي
cd /home/asem

# نسخ احتياطي من المشروع الحالي
echo "[1/5] إنشاء نسخة احتياطية..."
tar -czf kitchen_factory_backup_$(date +%Y%m%d_%H%M%S).tar.gz kitchen_factory/

# إعادة تسمية المجلد الحالي
echo "[2/5] حفظ المشروع القديم..."
mv kitchen_factory kitchen_factory_old

# استنساخ من Git (سيطلب منك URL)
echo "[3/5] استنساخ المشروع من Git..."
echo "الآن قم بنسخ أمر git clone من GitHub/GitLab"
echo "مثال: git clone https://github.com/username/kitchen_factory.git"
read -p "اضغط Enter بعد استنساخ المشروع..."

# نسخ قاعدة البيانات من المشروع القديم
echo "[4/5] نسخ قاعدة البيانات..."
cp kitchen_factory_old/kitchen_factory.db kitchen_factory/ 2>/dev/null || echo "لم يتم العثور على قاعدة البيانات"

# نسخ ملفات الرفع (uploads)
echo "[5/5] نسخ ملفات الرفع..."
cp -r kitchen_factory_old/uploads/* kitchen_factory/uploads/ 2>/dev/null || echo "لم يتم العثور على ملفات رفع"

# تطبيق Migrations
echo "تطبيق Migrations..."
cd kitchen_factory
python migrate_add_stage_rates.py 2>/dev/null || echo "Migration تم تطبيقه مسبقاً"

# إعادة تشغيل الخدمة
echo "إعادة تشغيل الخدمة..."
sudo systemctl restart kitchen_factory

echo ""
echo "=========================================="
echo "  ✅ تم الإعداد بنجاح!"
echo "=========================================="
echo ""
echo "للتحديثات المستقبلية، استخدم:"
echo "  cd /home/asem/kitchen_factory"
echo "  git pull"
echo "  sudo systemctl restart kitchen_factory"

