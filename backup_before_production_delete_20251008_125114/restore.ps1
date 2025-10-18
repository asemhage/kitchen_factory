# ═══════════════════════════════════════════════════════════════
# سكربت الاستعادة السريع - Restore Script
# نقطة الرجوع: قبل حذف قسم خط الإنتاج
# التاريخ: 2025-10-08
# ═══════════════════════════════════════════════════════════════

Write-Host ""
Write-Host "╔════════════════════════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║                                                            ║" -ForegroundColor Cyan
Write-Host "║           🔄 استعادة نقطة الرجوع 🔄                    ║" -ForegroundColor White -BackgroundColor DarkCyan
Write-Host "║                                                            ║" -ForegroundColor Cyan
Write-Host "╚════════════════════════════════════════════════════════════╝" -ForegroundColor Cyan
Write-Host ""

# التحقق من المسار
if (-not (Test-Path "../kitchen_factory/app.py")) {
    Write-Host "❌ خطأ: يجب تشغيل السكربت من مجلد النسخ الاحتياطي" -ForegroundColor Red
    Write-Host "   الاستخدام الصحيح:" -ForegroundColor Yellow
    Write-Host "   cd backup_before_production_delete_XXXXXX" -ForegroundColor White
    Write-Host "   .\restore.ps1" -ForegroundColor White
    Write-Host ""
    exit 1
}

# تأكيد الاستعادة
Write-Host "⚠️  تحذير: هذا سيستبدل الملفات الحالية بالنسخة القديمة" -ForegroundColor Yellow
Write-Host ""
$confirm = Read-Host "هل تريد المتابعة؟ (نعم/لا)"
if ($confirm -ne "نعم" -and $confirm -ne "yes" -and $confirm -ne "y") {
    Write-Host ""
    Write-Host "❌ تم إلغاء العملية" -ForegroundColor Red
    Write-Host ""
    exit 0
}

Write-Host ""
Write-Host "🔄 جاري الاستعادة..." -ForegroundColor Cyan
Write-Host ""

try {
    # 1. استعادة app.py
    Write-Host "1/6 - استعادة app.py..." -ForegroundColor Yellow
    Copy-Item "app.py.backup" "../kitchen_factory/app.py" -Force -ErrorAction Stop
    Write-Host "   ✅ تم" -ForegroundColor Green

    # 2. استعادة production.html
    Write-Host "2/6 - استعادة production.html..." -ForegroundColor Yellow
    Copy-Item "production.html.backup" "../kitchen_factory/templates/production.html" -Force -ErrorAction Stop
    Write-Host "   ✅ تم" -ForegroundColor Green

    # 3. استعادة order_production.html
    Write-Host "3/6 - استعادة order_production.html..." -ForegroundColor Yellow
    Copy-Item "order_production.html.backup" "../kitchen_factory/templates/order_production.html" -Force -ErrorAction Stop
    Write-Host "   ✅ تم" -ForegroundColor Green

    # 4. استعادة production_stages.html
    Write-Host "4/6 - استعادة production_stages.html..." -ForegroundColor Yellow
    Copy-Item "production_stages.html.backup" "../kitchen_factory/templates/reports/production_stages.html" -Force -ErrorAction Stop
    Write-Host "   ✅ تم" -ForegroundColor Green

    # 5. استعادة base.html
    Write-Host "5/6 - استعادة base.html..." -ForegroundColor Yellow
    Copy-Item "base.html.backup" "../kitchen_factory/templates/base.html" -Force -ErrorAction Stop
    Write-Host "   ✅ تم" -ForegroundColor Green

    # 6. استعادة قاعدة البيانات
    Write-Host "6/6 - استعادة قاعدة البيانات..." -ForegroundColor Yellow
    if (Test-Path "kitchen_factory.db.backup") {
        Copy-Item "kitchen_factory.db.backup" "../kitchen_factory/instance/kitchen_factory.db" -Force -ErrorAction Stop
        Write-Host "   ✅ تم" -ForegroundColor Green
    } else {
        Write-Host "   ⚠️  لم يتم العثور على نسخة قاعدة البيانات" -ForegroundColor Yellow
    }

    Write-Host ""
    Write-Host "╔════════════════════════════════════════════════════════════╗" -ForegroundColor Green
    Write-Host "║                                                            ║" -ForegroundColor Green
    Write-Host "║         ✅ تمت الاستعادة بنجاح! ✅                      ║" -ForegroundColor White -BackgroundColor DarkGreen
    Write-Host "║                                                            ║" -ForegroundColor Green
    Write-Host "╚════════════════════════════════════════════════════════════╝" -ForegroundColor Green
    Write-Host ""
    Write-Host "📝 ما تم استعادته:" -ForegroundColor Cyan
    Write-Host "   • app.py - الملف الرئيسي" -ForegroundColor White
    Write-Host "   • 3 قوالب HTML للإنتاج" -ForegroundColor White
    Write-Host "   • base.html - القالب الأساسي" -ForegroundColor White
    Write-Host "   • kitchen_factory.db - قاعدة البيانات" -ForegroundColor White
    Write-Host ""
    Write-Host "🚀 الخطوات التالية:" -ForegroundColor Magenta
    Write-Host "   1. تشغيل التطبيق:" -ForegroundColor Yellow
    Write-Host "      cd ../kitchen_factory" -ForegroundColor White
    Write-Host "      python app.py" -ForegroundColor White
    Write-Host ""
    Write-Host "   2. اختبار قسم خط الإنتاج" -ForegroundColor Yellow
    Write-Host "      http://localhost:5000/production" -ForegroundColor White
    Write-Host ""
    
} catch {
    Write-Host ""
    Write-Host "╔════════════════════════════════════════════════════════════╗" -ForegroundColor Red
    Write-Host "║                                                            ║" -ForegroundColor Red
    Write-Host "║              ❌ حدث خطأ في الاستعادة! ❌               ║" -ForegroundColor White -BackgroundColor DarkRed
    Write-Host "║                                                            ║" -ForegroundColor Red
    Write-Host "╚════════════════════════════════════════════════════════════╝" -ForegroundColor Red
    Write-Host ""
    Write-Host "تفاصيل الخطأ:" -ForegroundColor Red
    Write-Host $_.Exception.Message -ForegroundColor Yellow
    Write-Host ""
    Write-Host "⚠️  يرجى:" -ForegroundColor Yellow
    Write-Host "   1. التأكد من إغلاق التطبيق" -ForegroundColor White
    Write-Host "   2. التأكد من الصلاحيات على الملفات" -ForegroundColor White
    Write-Host "   3. إعادة المحاولة" -ForegroundColor White
    Write-Host ""
    exit 1
}


