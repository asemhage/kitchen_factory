# 🚀 دليل إعداد Git للمشروع

## ✅ **المرحلة 1: الإعداد المحلي (تم بنجاح)**

- ✅ تم إنشاء Git repository
- ✅ تم إضافة `.gitignore`
- ✅ تم عمل أول commit (135 ملف)

---

## 📦 **المرحلة 2: رفع المشروع على GitHub/GitLab**

### **الخيار أ: GitHub (الأسهل)**

#### **1. إنشاء Repository على GitHub:**
1. افتح https://github.com/new
2. اسم المشروع: `kitchen-factory`
3. خصوصي/عام: **Private** (موصى به)
4. **لا تضف** README أو `.gitignore` (موجود بالفعل)
5. اضغط **Create repository**

#### **2. ربط المشروع المحلي بـ GitHub:**

```bash
# استبدل USERNAME باسم حسابك على GitHub
git remote add origin https://github.com/USERNAME/kitchen-factory.git
git branch -M main
git push -u origin main
```

**البديل: استخدام SSH (أكثر أماناً):**
```bash
git remote add origin git@github.com:USERNAME/kitchen-factory.git
git branch -M main
git push -u origin main
```

---

### **الخيار ب: GitLab**

#### **1. إنشاء Project على GitLab:**
1. افتح https://gitlab.com/projects/new
2. اسم المشروع: `kitchen-factory`
3. Visibility: **Private**
4. اضغط **Create project**

#### **2. ربط المشروع:**
```bash
git remote add origin https://gitlab.com/USERNAME/kitchen-factory.git
git branch -M main
git push -u origin main
```

---

### **الخيار ج: سيرفر Git خاص (متقدم)**

إذا كنت تريد Git server على نفس السيرفر:

```bash
# على السيرفر
ssh asem@102.213.180.235
mkdir -p /home/asem/git/kitchen-factory.git
cd /home/asem/git/kitchen-factory.git
git init --bare

# على جهازك المحلي
git remote add origin asem@102.213.180.235:/home/asem/git/kitchen-factory.git
git push -u origin main
```

---

## 🖥️ **المرحلة 3: إعداد السيرفر**

### **الطريقة السهلة (GitHub/GitLab):**

```bash
# 1. الاتصال بالسيرفر
ssh asem@102.213.180.235

# 2. نسخ احتياطي
cd /home/asem
tar -czf kitchen_factory_backup_$(date +%Y%m%d_%H%M%S).tar.gz kitchen_factory/
mv kitchen_factory kitchen_factory_old

# 3. استنساخ من Git
git clone https://github.com/USERNAME/kitchen-factory.git kitchen_factory
# أو
git clone https://gitlab.com/USERNAME/kitchen-factory.git kitchen_factory

# 4. نسخ قاعدة البيانات والملفات
cp kitchen_factory_old/kitchen_factory.db kitchen_factory/
cp -r kitchen_factory_old/uploads/* kitchen_factory/uploads/

# 5. تطبيق Migrations
cd kitchen_factory
python migrate_add_stage_rates.py

# 6. إعادة التشغيل
sudo systemctl restart kitchen_factory

# 7. اختبار
curl http://localhost:4012
```

---

## 🔄 **الاستخدام اليومي**

### **بعد كل تعديل على جهازك:**

```bash
cd D:\arbcurser

# إضافة التغييرات
git add .

# Commit مع رسالة وصفية
git commit -m "وصف التعديل"

# رفع للسيرفر البعيد
git push
```

### **تحديث السيرفر:**

```bash
ssh asem@102.213.180.235 "cd /home/asem/kitchen_factory && git pull && sudo systemctl restart kitchen_factory"
```

**أو أمر واحد من جهازك:**
```bash
ssh asem@102.213.180.235 "cd /home/asem/kitchen_factory && git pull && python migrate_*.py 2>/dev/null; sudo systemctl restart kitchen_factory"
```

---

## 📝 **أوامر Git المفيدة**

### **على جهازك المحلي:**

```bash
# التحقق من الحالة
git status

# رؤية التغييرات
git diff

# رؤية السجل
git log --oneline

# التراجع عن تعديل
git checkout -- filename.py

# إنشاء فرع جديد
git checkout -b feature-name

# دمج فرع
git merge feature-name

# حذف فرع
git branch -d feature-name
```

### **على السيرفر:**

```bash
# التحديث من Git
cd /home/asem/kitchen_factory
git pull

# رؤية الإصدار الحالي
git log -1

# التحقق من الفرع
git branch

# التبديل لإصدار سابق (للطوارئ)
git log --oneline  # اختر الـ commit ID
git checkout COMMIT_ID

# العودة لآخر إصدار
git checkout main
```

---

## 🛡️ **نصائح أمنية**

### **1. حماية معلومات الاتصال:**
لا ترفع هذه الملفات لـ Git:
- ❌ قاعدة البيانات (`.db`)
- ❌ ملفات السر (`.env`)
- ❌ كلمات المرور
- ✅ `.gitignore` موجود ويحمي هذه الملفات

### **2. استخدام SSH بدلاً من HTTPS:**
```bash
# على جهازك المحلي - إنشاء SSH key
ssh-keygen -t ed25519 -C "your_email@example.com"

# عرض المفتاح العام
cat ~/.ssh/id_ed25519.pub

# أضفه في GitHub/GitLab Settings → SSH Keys
```

### **3. Git Credentials Manager:**
```bash
# لحفظ بيانات الدخول
git config --global credential.helper store
```

---

## 🔧 **حل المشاكل**

### **مشكلة: تعارض الملفات (Conflict)**
```bash
# جلب آخر التحديثات
git pull

# إذا حدث تعارض، افتح الملف وحرره يدوياً
# ثم:
git add .
git commit -m "حل التعارض"
git push
```

### **مشكلة: نسيت عمل Commit**
```bash
# أضف التغييرات للـ commit السابق
git add .
git commit --amend --no-edit
git push --force
```

### **مشكلة: أريد التراجع عن Commit**
```bash
# التراجع عن آخر commit (يبقي التغييرات)
git reset --soft HEAD~1

# التراجع عن آخر commit (يحذف التغييرات)
git reset --hard HEAD~1
```

---

## 📚 **الخطوة التالية**

بعد إعداد Git على GitHub/GitLab:
1. ✅ أعطني رابط الـ repository
2. ✅ سأعطيك الأوامر الدقيقة لإعداد السيرفر
3. ✅ ستصبح التحديثات بأمر واحد فقط!

---

## 💡 **فوائد Git**

- ✅ **مزامنة تلقائية** بين الأجهزة
- ✅ **تتبع كامل** لكل تغيير
- ✅ **إمكانية الرجوع** لأي إصدار سابق
- ✅ **نسخ احتياطي** سحابي مجاني
- ✅ **العمل الجماعي** (إذا انضم مطورون آخرون)
- ✅ **أمر واحد** للتحديث على السيرفر

---

## 🎯 **الحالة الآن**

✅ **على جهازك المحلي:**
- Git repository جاهز
- 135 ملف في أول commit
- `.gitignore` محمي للملفات الحساسة

⏳ **الخطوة التالية:**
- اختر GitHub أو GitLab
- أنشئ repository
- ارفع المشروع
- أعطني الرابط

---

**بعد ذلك، كل تحديث سيكون بأمرين فقط:**
```bash
git add . && git commit -m "تحديث" && git push
ssh asem@102.213.180.235 "cd /home/asem/kitchen_factory && git pull && sudo systemctl restart kitchen_factory"
```

🎉 **أو حتى أمر واحد إذا أردت!**

