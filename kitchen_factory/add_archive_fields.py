#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
إضافة حقول الأرشفة لجدول orders
التاريخ: 2025-10-14
"""

import sqlite3
from datetime import datetime

def add_archive_fields():
    """إضافة حقول الأرشفة لجدول orders"""
    
    db_path = 'instance/kitchen_factory.db'
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        print("=" * 50)
        print("إضافة حقول الأرشفة لجدول orders")
        print("=" * 50)
        
        # قائمة الحقول المراد إضافتها
        fields_to_add = [
            ("is_archived", "BOOLEAN DEFAULT 0"),
            ("archived_at", "DATETIME"),
            ("archived_by", "TEXT"),
            ("archive_notes", "TEXT")
        ]
        
        for field_name, field_def in fields_to_add:
            try:
                # محاولة إضافة الحقل
                cursor.execute(f"ALTER TABLE orders ADD COLUMN {field_name} {field_def}")
                print(f"✅ تم إضافة حقل {field_name}")
            except sqlite3.OperationalError as e:
                if "duplicate column name" in str(e):
                    print(f"ℹ️  الحقل {field_name} موجود مسبقاً")
                else:
                    print(f"❌ خطأ في إضافة {field_name}: {str(e)}")
        
        # تحديث الطلبيات الموجودة لتكون غير مؤرشفة بشكل افتراضي
        cursor.execute("UPDATE orders SET is_archived = 0 WHERE is_archived IS NULL")
        updated_count = cursor.rowcount
        
        conn.commit()
        print(f"\n✅ تم تحديث {updated_count} طلبية لتكون غير مؤرشفة افتراضياً")
        print("✅ اكتمل إضافة حقول الأرشفة بنجاح!")
        
        return True
        
    except Exception as e:
        conn.rollback()
        print(f"❌ حدث خطأ: {str(e)}")
        return False
        
    finally:
        conn.close()

if __name__ == '__main__':
    print("🚀 إضافة حقول الأرشفة")
    success = add_archive_fields()
    if success:
        print("\n✅ تم التحديث بنجاح! يمكنك الآن تشغيل التطبيق")
    else:
        print("\n❌ فشل التحديث!")
