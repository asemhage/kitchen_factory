#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
سكربت لإعادة تسمية جدول 'order' إلى 'orders'
لحل مشكلة الكلمة المحجوزة في SQL
"""

import sqlite3
import os
from datetime import datetime

def backup_database(db_path):
    """إنشاء نسخة احتياطية من قاعدة البيانات"""
    if os.path.exists(db_path):
        backup_path = f"{db_path}.backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        import shutil
        shutil.copy2(db_path, backup_path)
        print(f"✅ تم إنشاء نسخة احتياطية: {backup_path}")
        return backup_path
    return None

def rename_order_table(db_path='kitchen_factory.db'):
    """إعادة تسمية جدول order إلى orders"""
    
    if not os.path.exists(db_path):
        print(f"⚠️  قاعدة البيانات غير موجودة: {db_path}")
        return False
    
    # إنشاء نسخة احتياطية
    backup_path = backup_database(db_path)
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # التحقق من وجود جدول 'order'
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='order'")
        if not cursor.fetchone():
            print("ℹ️  جدول 'order' غير موجود. ربما تم تغيير الاسم بالفعل أو القاعدة جديدة.")
            conn.close()
            return True
        
        print("🔄 بدء عملية إعادة التسمية...")
        
        # في SQLite، يجب إنشاء جدول جديد ونسخ البيانات
        # لكن الأسهل هو استخدام ALTER TABLE RENAME
        cursor.execute('ALTER TABLE "order" RENAME TO "orders"')
        
        conn.commit()
        print("✅ تم إعادة تسمية الجدول من 'order' إلى 'orders' بنجاح!")
        
        # التحقق من النتيجة
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='orders'")
        if cursor.fetchone():
            print("✅ تم التحقق: جدول 'orders' موجود الآن")
        
        conn.close()
        return True
        
    except sqlite3.Error as e:
        print(f"❌ حدث خطأ أثناء إعادة التسمية: {e}")
        if backup_path:
            print(f"💡 يمكنك استعادة النسخة الاحتياطية من: {backup_path}")
        return False

if __name__ == "__main__":
    import sys
    
    # التحقق من وجود علم --yes
    auto_yes = '--yes' in sys.argv or '-y' in sys.argv
    
    print("=" * 60)
    print("سكربت إعادة تسمية جدول order إلى orders")
    print("=" * 60)
    print()
    
    # محاولة البحث عن قاعدة البيانات في المواقع المختلفة
    possible_paths = [
        'kitchen_factory.db',
        'instance/kitchen_factory.db',
        '../kitchen_factory.db'
    ]
    
    db_found = False
    for db_path in possible_paths:
        if os.path.exists(db_path):
            print(f"📁 تم العثور على قاعدة البيانات: {db_path}")
            print()
            
            if auto_yes:
                response = 'yes'
                print(f"⚡ الوضع التلقائي: سيتم تطبيق التغيير تلقائياً على {db_path}")
            else:
                response = input(f"هل تريد إعادة تسمية الجدول في {db_path}? (نعم/لا): ").strip().lower()
            
            if response in ['نعم', 'yes', 'y']:
                if rename_order_table(db_path):
                    print()
                    print("🎉 تمت العملية بنجاح!")
                    print()
                    print("⚠️  ملاحظة مهمة:")
                    print("   - تأكد من إعادة تشغيل التطبيق لاستخدام الجدول الجديد")
                    print("   - الكود في app.py يستخدم الآن 'orders' كاسم للجدول")
                else:
                    print()
                    print("❌ فشلت العملية. تحقق من الأخطاء أعلاه.")
            else:
                print("تم إلغاء العملية.")
            
            db_found = True
            print()
    
    if not db_found:
        print("⚠️  لم يتم العثور على قاعدة البيانات في المواقع المتوقعة:")
        for path in possible_paths:
            print(f"   - {path}")
        print()
        print("💡 إذا كانت قاعدة البيانات في موقع آخر، قم بتشغيل:")
        print("   python rename_order_table.py")
        print("   ثم عدل المسار في السكربت")

