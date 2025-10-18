#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Migration Script - Phase 1: إضافة نظام الصالات
==================================================

هذا السكربت يقوم بـ:
1. إنشاء جدول showrooms
2. إضافة showroom_id لجميع الجداول المطلوبة
3. إنشاء صالة افتراضية
4. إسناد جميع البيانات الحالية للصالة الافتراضية
5. إضافة الحقول الجديدة للنماذج (Customer, Material)

تاريخ الإنشاء: 2025-01-07
"""

import sqlite3
import os
import shutil
from datetime import datetime

def backup_database(db_path):
    """إنشاء نسخة احتياطية من قاعدة البيانات"""
    if os.path.exists(db_path):
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_path = f"{db_path}.backup_migration_{timestamp}"
        shutil.copy2(db_path, backup_path)
        print(f"✅ تم إنشاء نسخة احتياطية: {backup_path}")
        return backup_path
    return None

def migrate_database(db_path):
    """تنفيذ الترحيل"""
    
    print("="*60)
    print("بدء ترحيل قاعدة البيانات - Phase 1: الصالات")
    print("="*60)
    print()
    
    if not os.path.exists(db_path):
        print(f"⚠️  قاعدة البيانات غير موجودة: {db_path}")
        print("   سيتم إنشاؤها عند تشغيل التطبيق")
        return True
    
    # نسخة احتياطية
    backup_path = backup_database(db_path)
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        print("📋 الخطوة 1: إنشاء جدول showrooms...")
        
        # إنشاء جدول showrooms
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS showrooms (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name VARCHAR(100) UNIQUE NOT NULL,
                code VARCHAR(20) UNIQUE,
                address VARCHAR(200),
                phone VARCHAR(20),
                manager_name VARCHAR(100),
                notes TEXT,
                is_active BOOLEAN DEFAULT 1,
                deleted_at DATETIME,
                deleted_by VARCHAR(100),
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME
            )
        """)
        
        print("   ✅ تم إنشاء جدول showrooms")
        
        # إنشاء الصالة الافتراضية
        print("\n📋 الخطوة 2: إنشاء الصالة الافتراضية...")
        
        cursor.execute("""
            INSERT OR IGNORE INTO showrooms (name, code, is_active, created_at)
            VALUES ('الصالة الرئيسية', 'MAIN', 1, CURRENT_TIMESTAMP)
        """)
        
        default_showroom_id = cursor.lastrowid
        if default_showroom_id == 0:
            # الصالة موجودة بالفعل، احصل على ID
            cursor.execute("SELECT id FROM showrooms WHERE code = 'MAIN'")
            result = cursor.fetchone()
            default_showroom_id = result[0] if result else 1
        
        print(f"   ✅ الصالة الافتراضية: ID={default_showroom_id}")
        
        # قائمة الجداول التي تحتاج showroom_id
        tables_to_update = [
            ('user', True),  # nullable للمديرين
            ('orders', False),
            ('material', False),
            ('order_material', False),
            ('stage', False),
            ('document', False),
            ('received_order', False),
            ('material_consumption', False),
            ('order_cost', False),
            ('payment', False),
        ]
        
        print("\n📋 الخطوة 3: إضافة showroom_id للجداول...")
        
        for table_name, nullable in tables_to_update:
            # تحقق من وجود الجدول
            cursor.execute(f"""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name='{table_name}'
            """)
            
            if not cursor.fetchone():
                print(f"   ⚠️  الجدول {table_name} غير موجود - تخطي")
                continue
            
            # تحقق من وجود العمود
            cursor.execute(f"PRAGMA table_info({table_name})")
            columns = [col[1] for col in cursor.fetchall()]
            
            if 'showroom_id' in columns:
                print(f"   ⏭️  {table_name}: showroom_id موجود بالفعل")
                continue
            
            # إضافة العمود
            nullable_sql = "NULL" if nullable else "NOT NULL DEFAULT 1"
            try:
                cursor.execute(f"""
                    ALTER TABLE {table_name}
                    ADD COLUMN showroom_id INTEGER {nullable_sql}
                    REFERENCES showrooms(id)
                """)
                print(f"   ✅ {table_name}: تم إضافة showroom_id")
                
                # إسناد البيانات الحالية للصالة الافتراضية
                if not nullable:
                    cursor.execute(f"""
                        UPDATE {table_name}
                        SET showroom_id = {default_showroom_id}
                        WHERE showroom_id IS NULL OR showroom_id = 0
                    """)
                    rows_updated = cursor.rowcount
                    if rows_updated > 0:
                        print(f"      → تم تحديث {rows_updated} سجل")
                
            except sqlite3.OperationalError as e:
                print(f"   ⚠️  {table_name}: {e}")
        
        # إضافة حقول جديدة لـ user
        print("\n📋 الخطوة 4: تحديث جدول user...")
        
        user_fields = [
            ('is_active', 'BOOLEAN DEFAULT 1'),
            ('last_login', 'DATETIME'),
        ]
        
        for field_name, field_type in user_fields:
            cursor.execute("PRAGMA table_info(user)")
            columns = [col[1] for col in cursor.fetchall()]
            
            if field_name not in columns:
                try:
                    cursor.execute(f"""
                        ALTER TABLE user
                        ADD COLUMN {field_name} {field_type}
                    """)
                    print(f"   ✅ تم إضافة {field_name}")
                except sqlite3.OperationalError as e:
                    print(f"   ⚠️  {field_name}: {e}")
        
        # تحديث is_active للمستخدمين الحاليين
        cursor.execute("UPDATE user SET is_active = 1 WHERE is_active IS NULL")
        
        # إضافة حقول جديدة لـ customer
        print("\n📋 الخطوة 5: تحديث جدول customer...")
        
        customer_fields = [
            ('email', 'VARCHAR(100)'),
            ('tax_id', 'VARCHAR(50)'),
            ('customer_type', "VARCHAR(20) DEFAULT 'فرد'"),
            ('notes', 'TEXT'),
            ('is_active', 'BOOLEAN DEFAULT 1'),
            ('created_at', 'DATETIME DEFAULT CURRENT_TIMESTAMP'),
        ]
        
        for field_name, field_type in customer_fields:
            cursor.execute("PRAGMA table_info(customer)")
            columns = [col[1] for col in cursor.fetchall()]
            
            if field_name not in columns:
                try:
                    cursor.execute(f"""
                        ALTER TABLE customer
                        ADD COLUMN {field_name} {field_type}
                    """)
                    print(f"   ✅ تم إضافة {field_name}")
                except sqlite3.OperationalError as e:
                    print(f"   ⚠️  {field_name}: {e}")
        
        # تحديث القيم الافتراضية
        cursor.execute("UPDATE customer SET is_active = 1 WHERE is_active IS NULL")
        cursor.execute("UPDATE customer SET customer_type = 'فرد' WHERE customer_type IS NULL")
        
        # إضافة حقول جديدة لـ material
        print("\n📋 الخطوة 6: تحديث جدول material...")
        
        material_fields = [
            ('cost_price', 'FLOAT DEFAULT 0'),
            ('purchase_price', 'FLOAT DEFAULT 0'),
            ('selling_price', 'FLOAT DEFAULT 0'),
            ('cost_price_mode', "VARCHAR(30) DEFAULT 'purchase_price_default'"),
            ('allow_manual_price_edit', 'BOOLEAN DEFAULT 1'),
            ('price_locked', 'BOOLEAN DEFAULT 0'),
            ('price_updated_by', 'VARCHAR(100)'),
            ('is_active', 'BOOLEAN DEFAULT 1'),
            ('deleted_at', 'DATETIME'),
        ]
        
        for field_name, field_type in material_fields:
            cursor.execute("PRAGMA table_info(material)")
            columns = [col[1] for col in cursor.fetchall()]
            
            if field_name not in columns:
                try:
                    cursor.execute(f"""
                        ALTER TABLE material
                        ADD COLUMN {field_name} {field_type}
                    """)
                    print(f"   ✅ تم إضافة {field_name}")
                except sqlite3.OperationalError as e:
                    print(f"   ⚠️  {field_name}: {e}")
        
        # نسخ unit_price إلى cost_price و purchase_price
        cursor.execute("""
            UPDATE material 
            SET cost_price = unit_price, 
                purchase_price = unit_price
            WHERE cost_price = 0 OR cost_price IS NULL
        """)
        
        # تحديث القيم الافتراضية
        cursor.execute("UPDATE material SET is_active = 1 WHERE is_active IS NULL")
        cursor.execute("UPDATE material SET allow_manual_price_edit = 1 WHERE allow_manual_price_edit IS NULL")
        cursor.execute("UPDATE material SET price_locked = 0 WHERE price_locked IS NULL")
        
        # إنشاء Indexes للأداء
        print("\n📋 الخطوة 7: إنشاء Indexes...")
        
        indexes = [
            ("idx_customer_phone", "customer", "phone"),
            ("idx_customer_name", "customer", "name"),
            ("idx_order_showroom_status", "orders", "showroom_id, status"),
            ("idx_order_showroom_date", "orders", "showroom_id, order_date"),
        ]
        
        for idx_name, table, columns in indexes:
            try:
                cursor.execute(f"""
                    CREATE INDEX IF NOT EXISTS {idx_name}
                    ON {table}({columns})
                """)
                print(f"   ✅ {idx_name}")
            except sqlite3.OperationalError as e:
                print(f"   ⚠️  {idx_name}: {e}")
        
        # حفظ التغييرات
        conn.commit()
        
        print("\n" + "="*60)
        print("✅ اكتمل الترحيل بنجاح!")
        print("="*60)
        print()
        print("📊 ملخص:")
        print(f"   • جدول showrooms: تم الإنشاء")
        print(f"   • الصالة الافتراضية: ID={default_showroom_id}")
        print(f"   • الجداول المحدثة: {len([t for t in tables_to_update])}")
        print()
        print("⚠️  ملاحظات مهمة:")
        print("   1. تم إسناد جميع البيانات الحالية للصالة الافتراضية")
        print("   2. يجب إعادة تشغيل التطبيق الآن")
        print("   3. النسخة الاحتياطية متوفرة في حال حدوث مشكلة")
        print()
        
        return True
        
    except Exception as e:
        print(f"\n❌ خطأ أثناء الترحيل: {e}")
        print(f"   يمكنك استعادة النسخة الاحتياطية: {backup_path}")
        return False
        
    finally:
        if 'conn' in locals():
            conn.close()

if __name__ == "__main__":
    import sys
    
    # البحث عن قاعدة البيانات
    possible_paths = [
        'kitchen_factory.db',
        'instance/kitchen_factory.db',
        '../instance/kitchen_factory.db',
    ]
    
    db_found = False
    for db_path in possible_paths:
        if os.path.exists(db_path):
            print(f"📁 تم العثور على قاعدة البيانات: {db_path}")
            print()
            
            # تأكيد من المستخدم (إلا إذا استخدم --yes)
            if '--yes' in sys.argv or '-y' in sys.argv:
                response = 'yes'
                print("⚡ الوضع التلقائي: سيتم تطبيق الترحيل تلقائياً")
            else:
                response = input(f"هل تريد تطبيق الترحيل على {db_path}? (نعم/لا): ").strip().lower()
            
            if response in ['نعم', 'yes', 'y']:
                success = migrate_database(db_path)
                if success:
                    print("\n🎉 تم بنجاح! يمكنك الآن تشغيل التطبيق")
                    sys.exit(0)
                else:
                    print("\n❌ فشل الترحيل")
                    sys.exit(1)
            else:
                print("تم إلغاء العملية.")
                sys.exit(0)
            
            db_found = True
            break
    
    if not db_found:
        print("⚠️  لم يتم العثور على قاعدة بيانات موجودة")
        print("   سيتم إنشاء قاعدة بيانات جديدة عند تشغيل التطبيق")
        sys.exit(0)

