#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
إضافة حقول الفنيين لجدول stage
التاريخ: 2025-10-14
"""

import sqlite3

def add_technician_fields():
    """إضافة حقول الفنيين لجدول stage"""
    
    db_path = 'instance/kitchen_factory.db'
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        print("=" * 50)
        print("إضافة حقول الفنيين لجدول stage")
        print("=" * 50)
        
        # قائمة الحقول المراد إضافتها
        fields_to_add = [
            ("manufacturing_technician_id", "INTEGER"),
            ("installation_technician_id", "INTEGER"),
            ("manufacturing_assigned_at", "DATETIME"),
            ("installation_assigned_at", "DATETIME"),
            ("manufacturing_start_date", "DATETIME"),
            ("manufacturing_end_date", "DATETIME"),
            ("installation_start_date", "DATETIME"),
            ("installation_end_date", "DATETIME"),
            ("order_meters", "REAL")
        ]
        
        added_count = 0
        for field_name, field_def in fields_to_add:
            try:
                cursor.execute(f"ALTER TABLE stage ADD COLUMN {field_name} {field_def}")
                print(f"✅ تم إضافة حقل {field_name}")
                added_count += 1
            except sqlite3.OperationalError as e:
                if "duplicate column name" in str(e):
                    print(f"ℹ️  الحقل {field_name} موجود مسبقاً")
                else:
                    print(f"❌ خطأ في إضافة {field_name}: {str(e)}")
        
        conn.commit()
        print(f"\n✅ تم إضافة {added_count} حقل جديد لجدول stage")
        print("✅ اكتمل إضافة حقول الفنيين بنجاح!")
        
        return True
        
    except Exception as e:
        conn.rollback()
        print(f"❌ حدث خطأ: {str(e)}")
        return False
        
    finally:
        conn.close()

if __name__ == '__main__':
    print("🚀 إضافة حقول الفنيين")
    success = add_technician_fields()
    if success:
        print("\n✅ تم التحديث بنجاح!")
    else:
        print("\n❌ فشل التحديث!")
