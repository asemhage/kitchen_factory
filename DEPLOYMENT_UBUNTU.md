# 🚀 دليل نشر التطبيق على Ubuntu Server

## 📋 المتطلبات الأساسية

### 1. تحديث النظام
```bash
sudo apt update
sudo apt upgrade -y
```

### 2. تثبيت Python 3 و pip
```bash
sudo apt install python3 python3-pip python3-venv -y
```

### 3. تثبيت الأدوات الإضافية
```bash
# لدعم اللغة العربية في PDF
sudo apt install fonts-arabic -y
sudo apt install ttf-dejavu-core -y

# أدوات النظام
sudo apt install git supervisor nginx -y
```

---

## 📦 نشر التطبيق

### 1. نقل المشروع إلى السيرفر
```bash
# استخدم git أو scp لنقل الملفات
cd /var/www/
sudo git clone <repository-url> kitchen_factory
# أو
sudo scp -r /path/to/local/kitchen_factory user@server:/var/www/
```

### 2. إعداد البيئة الافتراضية
```bash
cd /var/www/kitchen_factory/kitchen_factory
python3 -m venv venv
source venv/bin/activate
```

### 3. تثبيت المتطلبات
```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### 4. تهيئة قاعدة البيانات
```bash
# إنشاء مجلد instance إذا لم يكن موجوداً
mkdir -p instance

# نسخ قاعدة البيانات إذا كانت موجودة
# أو سيتم إنشاؤها تلقائياً عند التشغيل الأول
```

---

## ⚙️ إعداد Supervisor (للتشغيل المستمر)

### 1. إنشاء ملف إعدادات Supervisor
```bash
sudo nano /etc/supervisor/conf.d/kitchen_factory.conf
```

### 2. محتوى الملف:
```ini
[program:kitchen_factory]
directory=/var/www/kitchen_factory/kitchen_factory
command=/var/www/kitchen_factory/kitchen_factory/venv/bin/python app.py
user=www-data
autostart=true
autorestart=true
stopasgroup=true
killasgroup=true
stderr_logfile=/var/log/kitchen_factory/err.log
stdout_logfile=/var/log/kitchen_factory/out.log
environment=LANG=ar_SA.UTF-8,LC_ALL=ar_SA.UTF-8
```

### 3. إنشاء مجلد السجلات
```bash
sudo mkdir -p /var/log/kitchen_factory
sudo chown www-data:www-data /var/log/kitchen_factory
```

### 4. تفعيل وتشغيل Supervisor
```bash
sudo supervisorctl reread
sudo supervisorctl update
sudo supervisorctl start kitchen_factory
```

### 5. التحقق من الحالة
```bash
sudo supervisorctl status kitchen_factory
```

---

## 🔧 إعداد Nginx (Reverse Proxy)

### 1. إنشاء ملف إعدادات Nginx
```bash
sudo nano /etc/nginx/sites-available/kitchen_factory
```

### 2. محتوى الملف:
```nginx
server {
    listen 80;
    server_name your_domain.com;  # غير هذا إلى اسم النطاق الخاص بك

    # دعم الملفات الكبيرة (للصور)
    client_max_body_size 20M;

    # التوجيه للتطبيق
    location / {
        proxy_pass http://127.0.0.1:4012;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # التعامل مع الملفات الثابتة (اختياري)
    location /static {
        alias /var/www/kitchen_factory/kitchen_factory/static;
        expires 30d;
    }

    location /uploads {
        alias /var/www/kitchen_factory/kitchen_factory/uploads;
        expires 7d;
    }
}
```

### 3. تفعيل الموقع
```bash
sudo ln -s /etc/nginx/sites-available/kitchen_factory /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

---

## 🔒 إعداد SSL (HTTPS) - اختياري

### استخدام Let's Encrypt
```bash
sudo apt install certbot python3-certbot-nginx -y
sudo certbot --nginx -d your_domain.com
```

---

## 🔥 إعداد Firewall

```bash
# السماح بالمنافذ الضرورية
sudo ufw allow 22/tcp      # SSH
sudo ufw allow 80/tcp      # HTTP
sudo ufw allow 443/tcp     # HTTPS
sudo ufw allow 4012/tcp    # التطبيق (إذا كنت تريد الوصول المباشر)

# تفعيل Firewall
sudo ufw enable
sudo ufw status
```

---

## 📝 أوامر إدارة التطبيق

### إيقاف التطبيق
```bash
sudo supervisorctl stop kitchen_factory
```

### تشغيل التطبيق
```bash
sudo supervisorctl start kitchen_factory
```

### إعادة تشغيل التطبيق
```bash
sudo supervisorctl restart kitchen_factory
```

### عرض السجلات
```bash
# سجلات التطبيق
sudo tail -f /var/log/kitchen_factory/out.log
sudo tail -f /var/log/kitchen_factory/err.log

# سجلات Nginx
sudo tail -f /var/nginx/access.log
sudo tail -f /var/nginx/error.log
```

---

## 🔄 تحديث التطبيق

```bash
# إيقاف التطبيق
sudo supervisorctl stop kitchen_factory

# تحديث الكود
cd /var/www/kitchen_factory
sudo git pull

# تحديث المتطلبات
cd kitchen_factory
source venv/bin/activate
pip install -r requirements.txt

# نسخ احتياطي لقاعدة البيانات
cp instance/kitchen_factory.db instance/kitchen_factory.db.backup_$(date +%Y%m%d_%H%M%S)

# إعادة تشغيل التطبيق
sudo supervisorctl start kitchen_factory
```

---

## 🛠️ استكشاف الأخطاء

### 1. التطبيق لا يعمل
```bash
# التحقق من حالة Supervisor
sudo supervisorctl status kitchen_factory

# عرض السجلات
sudo tail -n 50 /var/log/kitchen_factory/err.log
```

### 2. خطأ في قاعدة البيانات
```bash
# التأكد من الصلاحيات
sudo chown -R www-data:www-data /var/www/kitchen_factory/kitchen_factory/instance
```

### 3. مشاكل الخطوط العربية
```bash
# إعادة تثبيت الخطوط
sudo apt install --reinstall fonts-arabic ttf-dejavu-core
fc-cache -f -v
```

### 4. التحقق من المنفذ 4012
```bash
# التأكد من أن المنفذ مفتوح
sudo netstat -tlnp | grep 4012
# أو
sudo lsof -i :4012
```

---

## 📊 معلومات المنفذ

- **المنفذ المحلي:** `4012`
- **الوصول المباشر:** `http://localhost:4012`
- **الوصول عبر Nginx:** `http://your_domain.com` (المنفذ 80 أو 443)

---

## ✅ اختبار التطبيق

### 1. الاختبار المحلي على السيرفر
```bash
curl http://localhost:4012
```

### 2. الاختبار من جهاز آخر
```bash
curl http://server_ip:4012
```

### 3. الاختبار عبر Nginx
```bash
curl http://your_domain.com
```

---

## 📞 دعم اللغة العربية

### التأكد من دعم UTF-8
```bash
# في ملف /etc/default/locale
LANG=ar_SA.UTF-8
LC_ALL=ar_SA.UTF-8

# تطبيق التغييرات
sudo locale-gen ar_SA.UTF-8
sudo update-locale
```

---

## 🎯 ملاحظات مهمة

1. **أمان قاعدة البيانات:**
   - احفظ نسخ احتياطية دورية من قاعدة البيانات
   - استخدم `cron` لأتمتة النسخ الاحتياطي

2. **الأداء:**
   - استخدم `gunicorn` بدلاً من `flask run` للإنتاج:
     ```bash
     pip install gunicorn
     gunicorn -w 4 -b 0.0.0.0:4012 app:app
     ```

3. **الأمان:**
   - غير `debug=True` إلى `debug=False` في الإنتاج
   - استخدم متغيرات بيئة للمعلومات الحساسة
   - فعّل HTTPS باستخدام Let's Encrypt

4. **المراقبة:**
   - راقب استخدام الموارد (CPU, RAM, Disk)
   - تحقق من السجلات بانتظام
   - استخدم أدوات مثل `htop` و `iotop`

---

## 🆘 الدعم

في حال مواجهة مشاكل:
1. تحقق من السجلات في `/var/log/kitchen_factory/`
2. تحقق من حالة Supervisor: `sudo supervisorctl status`
3. تحقق من حالة Nginx: `sudo systemctl status nginx`
4. تأكد من الصلاحيات: `ls -la /var/www/kitchen_factory/`

---

**✅ الآن التطبيق جاهز للعمل على المنفذ 4012 في بيئة Ubuntu!**

