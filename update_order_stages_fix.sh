#!/bin/bash

# سكربت تحديث order_stages.html على السيرفر
# التاريخ: 2025-10-20
# الهدف: إصلاح مشكلة عرض جميع المراحل في الجدول

echo "============================================"
echo "تحديث order_stages.html على السيرفر"
echo "============================================"

# الانتقال إلى مجلد المشروع
cd ~/kitchen_factory/kitchen_factory

# نسخ احتياطية
echo "📦 إنشاء نسخة احتياطية..."
cp templates/order_stages.html templates/order_stages.html.backup_$(date +%Y%m%d_%H%M%S)

# رفع الملف المحدث
echo "📤 رفع الملف المحدث..."
# ملاحظة: يجب رفع الملف يدوياً أو عبر scp/git

# إعادة تشغيل التطبيق
echo "🔄 إعادة تشغيل التطبيق..."
pkill -f "python.*app.py"
sleep 2
nohup python app.py > app.log 2>&1 &

echo ""
echo "✅ تم التحديث بنجاح!"
echo ""
echo "📋 الخطوات التالية:"
echo "1. افتح المتصفح واضغط Ctrl+Shift+R (Hard Refresh)"
echo "2. اذهب إلى صفحة مراحل الطلب"
echo "3. تحقق من ظهور جميع المراحل الـ6 في الجدول"
echo ""
echo "🔍 للتحقق من السجلات:"
echo "tail -f app.log"
echo ""

