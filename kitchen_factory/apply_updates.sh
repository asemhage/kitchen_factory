#!/bin/bash
# سكريبت تطبيق التحديثات على السيرفر - 2025-10-18

set -e  # إيقاف عند أول خطأ

echo "=========================================="
echo "  تطبيق تحديثات نظام المراحل"
echo "=========================================="

cd /home/asem/kitchen_factory

# نسخ احتياطي
echo "[1/4] إنشاء نسخة احتياطية..."
cp kitchen_factory.db kitchen_factory.db.backup_$(date +%Y%m%d_%H%M%S)

# تطبيق Migration
echo "[2/4] تطبيق Migration..."
python migrate_add_stage_rates.py

# التحقق
echo "[3/4] التحقق من الحقول الجديدة..."
sqlite3 kitchen_factory.db "PRAGMA table_info(stage);" | grep -E "(manufacturing_rate|installation_rate)" && echo "✅ الحقول موجودة"

# إعادة التشغيل
echo "[4/4] إعادة تشغيل التطبيق..."
sudo systemctl restart kitchen_factory

echo ""
echo "=========================================="
echo "  ✅ تم تطبيق التحديثات بنجاح!"
echo "=========================================="

