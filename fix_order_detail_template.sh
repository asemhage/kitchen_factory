#!/bin/bash
# سكريبت لإصلاح خطأ Jinja2 في order_detail.html

echo "🔧 بدء إصلاح order_detail.html..."

# المسار إلى الملف
TEMPLATE_FILE="/home/asem/kitchen_factory/templates/order_detail.html"

# التحقق من وجود الملف
if [ ! -f "$TEMPLATE_FILE" ]; then
    echo "❌ الملف غير موجود: $TEMPLATE_FILE"
    exit 1
fi

# إنشاء نسخة احتياطية
BACKUP_FILE="${TEMPLATE_FILE}.backup_$(date +%Y%m%d_%H%M%S)"
cp "$TEMPLATE_FILE" "$BACKUP_FILE"
echo "✅ تم إنشاء نسخة احتياطية: $BACKUP_FILE"

# إصلاح الملف باستخدام sed
# البحث عن السطر الذي يحتوي على "{% block scripts %}" 
# والسطر السابق له يحتوي على "{% endif %}"
# وإضافة "{% endblock %}" بينهما

sed -i '/{% if current_user.role != '"'"'موظف استقبال'"'"' %}/,/{% endif %}/ {
    /{% endif %}/a\
\
{% endblock %}
}' "$TEMPLATE_FILE"

echo "✅ تم تطبيق الإصلاح"

# التحقق من الإصلاح
if grep -q "{% endblock %}" "$TEMPLATE_FILE" | grep -q "{% block scripts %}"; then
    echo "✅ الإصلاح ناجح!"
    echo ""
    echo "📋 لإكمال التطبيق، قم بإعادة تشغيل التطبيق:"
    echo "   sudo systemctl restart kitchen_factory"
    echo ""
    echo "أو إذا كان يعمل يدوياً:"
    echo "   cd /home/asem/kitchen_factory"
    echo "   # أوقف التطبيق (Ctrl+C)"
    echo "   source venv/bin/activate"
    echo "   python app.py"
else
    echo "⚠️  قد تحتاج للتعديل يدوياً"
fi

echo ""
echo "💾 النسخة الاحتياطية موجودة في: $BACKUP_FILE"

