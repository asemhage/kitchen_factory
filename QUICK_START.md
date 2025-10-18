# 🚀 دليل البدء السريع

## 💻 تشغيل على Windows (التطوير)

```bash
cd kitchen_factory
python app.py
```

**الوصول:** `http://localhost:4012`

---

## 🐧 تشغيل على Ubuntu (الإنتاج)

### خطوات سريعة:

```bash
# 1. تثبيت المتطلبات
sudo apt update
sudo apt install python3 python3-pip python3-venv fonts-arabic -y

# 2. إعداد المشروع
cd /var/www/kitchen_factory/kitchen_factory
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
pip install gunicorn

# 3. تشغيل
chmod +x run_production.sh
./run_production.sh
```

**الوصول:** `http://server_ip:4012`

---

## 📋 معلومات المنفذ

- **المنفذ:** `4012`
- **Host:** `0.0.0.0` (يقبل جميع الاتصالات)

---

## 📚 للمزيد من التفاصيل

- **دليل النشر الكامل:** `DEPLOYMENT_UBUNTU.md`
- **سجل التغييرات:** `Change log.md`

---

## 🔧 أوامر مفيدة

### التحقق من المنفذ:
```bash
# Windows
netstat -an | findstr 4012

# Ubuntu
sudo netstat -tlnp | grep 4012
# أو
sudo lsof -i :4012
```

### إيقاف التطبيق:
```bash
# إذا كان يعمل في الخلفية
sudo systemctl stop kitchen_factory

# أو
sudo pkill -f "python.*app.py"
sudo pkill -f "gunicorn.*4012"
```

### إعادة التشغيل:
```bash
sudo systemctl restart kitchen_factory
```

---

**✅ جاهز للعمل!**

