@echo off
REM سكريبت تحديث سريع للسيرفر
REM الاستخدام: اضغط مرتين على الملف

echo ========================================
echo   تحديث Kitchen Factory على السيرفر
echo ========================================
echo.

REM Git Push من المحلي
echo [1/3] رفع التعديلات...
git add .
git commit -m "تحديث: %date% %time%"
git push

echo.
echo [2/3] تحديث السيرفر...
ssh asem@102.213.180.235 "cd /home/asem/kitchen_factory && git pull && python migrate_*.py 2>/dev/null; sudo systemctl restart kitchen_factory"

echo.
echo [3/3] اختبار السيرفر...
curl -s http://102.213.180.235:4012 > nul && echo ✅ السيرفر يعمل بنجاح || echo ❌ فشل الاتصال بالسيرفر

echo.
echo ========================================
echo   ✅ تم التحديث بنجاح!
echo ========================================
pause

