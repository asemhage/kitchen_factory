#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Migration Script: إنشاء جداول الفنيين والمستحقات وتحديث جدول المراحل
التاريخ: 2025-10-14
الهدف: إنشاء هيكل بيانات إدارة الفنيين

التغييرات:
- إنشاء جدول technicians
- إنشاء جدول technician_dues
- إنشاء جدول technician_payments
- تحديث جدول stage بإضافة حقول الفنيين
"""

import sqlite3
from datetime import datetime, timezone
import sys

def create_technicians_tables():
    """إنشاء جداول الفنيين وتحديث جدول المراحل"""
    
    # الاتصال بقاعدة البيانات
    db_path = 'instance/kitchen_factory.db'
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        print("=" * 70)
        print("بدء إنشاء جداول الفنيين")
        print("=" * 70)
        
        # التحقق من عدم وجود جدول الفنيين مسبقاً
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='technicians'")
        if cursor.fetchone():
            print("⚠️  جدول الفنيين موجود مسبقاً! لتجنب فقدان البيانات، لن نقوم بإعادة إنشائه.")
            choice = input("هل تريد المتابعة مع باقي الجداول؟ (yes/no): ")
            if choice.lower() not in ['yes', 'y', 'نعم']:
                return False
        
        # 1. إنشاء جدول الفنيين
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS technicians (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            phone TEXT,
            email TEXT,
            national_id TEXT,
            specialization TEXT,
            status TEXT DEFAULT 'نشط',
            hire_date DATE,
            bank_name TEXT,
            bank_account TEXT,
            payment_method TEXT DEFAULT 'per_meter',
            manufacturing_rate_per_meter REAL DEFAULT 0,
            installation_rate_per_meter REAL DEFAULT 0,
            notes TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME
        )
        """)
        print("✅ تم إنشاء جدول الفنيين (technicians)")
        
        # 2. إنشاء جدول مستحقات الفنيين
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS technician_dues (
            id INTEGER PRIMARY KEY,
            technician_id INTEGER NOT NULL,
            order_id INTEGER NOT NULL,
            stage_id INTEGER NOT NULL,
            due_type TEXT NOT NULL,
            meters REAL,
            rate_per_meter REAL,
            amount REAL NOT NULL,
            is_paid BOOLEAN DEFAULT 0,
            paid_at DATETIME,
            payment_id INTEGER,
            notes TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (technician_id) REFERENCES technicians(id),
            FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE CASCADE,
            FOREIGN KEY (stage_id) REFERENCES stage(id) ON DELETE CASCADE,
            FOREIGN KEY (payment_id) REFERENCES technician_payments(id)
        )
        """)
        print("✅ تم إنشاء جدول مستحقات الفنيين (technician_dues)")
        
        # 3. إنشاء جدول دفعات الفنيين
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS technician_payments (
            id INTEGER PRIMARY KEY,
            technician_id INTEGER NOT NULL,
            amount REAL NOT NULL,
            payment_date DATE NOT NULL,
            payment_method TEXT,
            reference_number TEXT,
            notes TEXT,
            paid_by TEXT,
            is_active BOOLEAN DEFAULT 1,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (technician_id) REFERENCES technicians(id)
        )
        """)
        print("✅ تم إنشاء جدول دفعات الفنيين (technician_payments)")
        
        # 4. تحديث جدول المراحل بإضافة حقول الفنيين
        # أولاً، نتحقق من وجود الأعمدة بالفعل لتجنب الأخطاء
        try:
            # التحقق من وجود manufacturing_technician_id
            cursor.execute("SELECT manufacturing_technician_id FROM stage LIMIT 1")
        except sqlite3.OperationalError:
            # العمود غير موجود، نضيفه
            cursor.execute("ALTER TABLE stage ADD COLUMN manufacturing_technician_id INTEGER REFERENCES technicians(id)")
            print("✅ تم إضافة حقل manufacturing_technician_id لجدول المراحل")
        
        try:
            # التحقق من وجود installation_technician_id
            cursor.execute("SELECT installation_technician_id FROM stage LIMIT 1")
        except sqlite3.OperationalError:
            # العمود غير موجود، نضيفه
            cursor.execute("ALTER TABLE stage ADD COLUMN installation_technician_id INTEGER REFERENCES technicians(id)")
            print("✅ تم إضافة حقل installation_technician_id لجدول المراحل")
        
        # إضافة باقي الحقول
        columns_to_add = [
            ("manufacturing_assigned_at", "DATETIME"),
            ("installation_assigned_at", "DATETIME"),
            ("manufacturing_start_date", "DATETIME"),
            ("manufacturing_end_date", "DATETIME"),
            ("installation_start_date", "DATETIME"),
            ("installation_end_date", "DATETIME"),
            ("order_meters", "REAL")
        ]
        
        for col_name, col_type in columns_to_add:
            try:
                # التحقق من وجود العمود
                cursor.execute(f"SELECT {col_name} FROM stage LIMIT 1")
            except sqlite3.OperationalError:
                # العمود غير موجود، نضيفه
                cursor.execute(f"ALTER TABLE stage ADD COLUMN {col_name} {col_type}")
                print(f"✅ تم إضافة حقل {col_name} لجدول المراحل")
        
        # 5. إنشاء الفهارس
        # الفهارس تسرع عمليات البحث والاستعلام
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_tech_status ON technicians(status)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_tech_due_paid ON technician_dues(is_paid)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_tech_due_tech ON technician_dues(technician_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_tech_due_order ON technician_dues(order_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_tech_payment_tech ON technician_payments(technician_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_stage_tech_mfg ON stage(manufacturing_technician_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_stage_tech_inst ON stage(installation_technician_id)")
        print("✅ تم إنشاء الفهارس")
        
        # 6. إضافة الإعدادات الافتراضية
        cursor.execute("SELECT * FROM system_settings WHERE key='default_manufacturing_rate'")
        if not cursor.fetchone():
            cursor.execute("""
            INSERT INTO system_settings (key, value, value_type, category, description)
            VALUES ('default_manufacturing_rate', '50.0', 'float', 'technicians', 'سعر المتر الافتراضي للتصنيع (د.ل)')
            """)
            print("✅ تم إضافة إعداد default_manufacturing_rate")
        
        cursor.execute("SELECT * FROM system_settings WHERE key='default_installation_rate'")
        if not cursor.fetchone():
            cursor.execute("""
            INSERT INTO system_settings (key, value, value_type, category, description)
            VALUES ('default_installation_rate', '30.0', 'float', 'technicians', 'سعر المتر الافتراضي للتركيب (د.ل)')
            """)
            print("✅ تم إضافة إعداد default_installation_rate")
        
        cursor.execute("SELECT * FROM system_settings WHERE key='auto_create_dues'")
        if not cursor.fetchone():
            cursor.execute("""
            INSERT INTO system_settings (key, value, value_type, category, description)
            VALUES ('auto_create_dues', 'true', 'boolean', 'technicians', 'إنشاء المستحقات تلقائياً عند إكمال المرحلة')
            """)
            print("✅ تم إضافة إعداد auto_create_dues")
        
        # 7. حفظ التغييرات
        conn.commit()
        
        # 8. عرض إحصائيات نهائية
        print("\n" + "=" * 70)
        print("📈 إحصائيات الترحيل:")
        print("=" * 70)
        
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = cursor.fetchall()
        print("📊 الجداول الموجودة في قاعدة البيانات:")
        for table in sorted([t[0] for t in tables]):
            print(f"   - {table}")
        
        print("\n✅ اكتمل إنشاء جداول الفنيين بنجاح!")
        return True
        
    except Exception as e:
        conn.rollback()
        print(f"\n❌ حدث خطأ أثناء الترحيل: {str(e)}")
        import traceback
        traceback.print_exc()
        return False
        
    finally:
        conn.close()


if __name__ == '__main__':
    print("\n🚀 سكربت إنشاء جداول الفنيين")
    print("   التاريخ: 2025-10-14\n")
    
    # تأكيد من المستخدم
    if len(sys.argv) > 1 and sys.argv[1] == '--force':
        success = create_technicians_tables()
    else:
        response = input("⚠️  هذا السكربت سيقوم بإنشاء جداول الفنيين. هل تريد المتابعة؟ (yes/no): ")
        if response.lower() in ['yes', 'y', 'نعم']:
            success = create_technicians_tables()
        else:
            print("\n❌ تم إلغاء العملية")
            sys.exit(0)
            
    if success:
        print("\n✅ تم التحديث بنجاح!")
    else:
        print("\n❌ فشل التحديث!")
        sys.exit(1)
