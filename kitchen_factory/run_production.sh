#!/bin/bash
# Script لتشغيل التطبيق في بيئة الإنتاج على Ubuntu

# التأكد من تشغيل السكريبت من مجلد المشروع
cd "$(dirname "$0")"

# تفعيل البيئة الافتراضية
source venv/bin/activate

# تعيين متغيرات البيئة
export FLASK_APP=app.py
export FLASK_ENV=production
export LANG=ar_SA.UTF-8
export LC_ALL=ar_SA.UTF-8

# التحقق من قاعدة البيانات
if [ ! -d "instance" ]; then
    mkdir -p instance
    echo "✅ تم إنشاء مجلد instance"
fi

# تشغيل التطبيق باستخدام gunicorn للإنتاج
# إذا لم يكن gunicorn مثبت، سيستخدم flask run
if command -v gunicorn &> /dev/null
then
    echo "🚀 تشغيل التطبيق باستخدام Gunicorn على المنفذ 4012..."
    gunicorn -w 4 -b 0.0.0.0:4012 --timeout 120 --access-logfile - --error-logfile - app:app
else
    echo "⚠️  Gunicorn غير مثبت. استخدام Flask run..."
    echo "💡 للأداء الأفضل، قم بتثبيت gunicorn: pip install gunicorn"
    python app.py
fi

