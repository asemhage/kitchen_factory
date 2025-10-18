"""
تحديث جدول order_materials لإضافة حقول النظام الجديد
"""
import sqlite3
from datetime import datetime

def migrate_order_materials():
    """إضافة الحقول الجديدة لجدول order_materials"""
    
    conn = sqlite3.connect('kitchen_factory/instance/kitchen_factory.db')
    cursor = conn.cursor()
    
    print("🔄 بدء تحديث جدول order_materials...")
    
    try:
        # التحقق من وجود الجدول
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND (name='order_material' OR name='order_materials')
        """)
        
        table_check = cursor.fetchone()
        if not table_check:
            print("❌ جدول order_material غير موجود!")
            return False
        
        table_name = table_check[0]
        print(f"✅ تم العثور على الجدول: {table_name}")
        
        # الحقول الجديدة المطلوبة
        new_columns = [
            ("quantity_needed", "FLOAT DEFAULT 0"),
            ("quantity_consumed", "FLOAT DEFAULT 0"),
            ("quantity_shortage", "FLOAT DEFAULT 0"),
            ("unit_cost", "FLOAT"),
            ("total_cost", "FLOAT"),
            ("status", "VARCHAR(20) DEFAULT 'pending'"),
            ("added_at", "DATETIME"),
            ("consumed_at", "DATETIME"),
            ("completed_at", "DATETIME"),
            ("added_by", "VARCHAR(100)"),
            ("notes", "TEXT"),
        ]
        
        # التحقق من الأعمدة الموجودة
        cursor.execute(f"PRAGMA table_info({table_name})")
        existing_columns = {row[1] for row in cursor.fetchall()}
        
        # إضافة الأعمدة الجديدة
        for col_name, col_type in new_columns:
            if col_name not in existing_columns:
                try:
                    cursor.execute(f"ALTER TABLE {table_name} ADD COLUMN {col_name} {col_type}")
                    print(f"✅ تم إضافة العمود: {col_name}")
                except sqlite3.OperationalError as e:
                    print(f"⚠️ العمود {col_name} موجود مسبقاً أو حدث خطأ: {e}")
        
        # تحديث البيانات الموجودة لتوافق النظام الجديد
        cursor.execute(f"""
            UPDATE {table_name} 
            SET quantity_needed = COALESCE(quantity_used, 0),
                quantity_consumed = COALESCE(quantity_used, 0),
                quantity_shortage = 0,
                unit_cost = COALESCE(unit_price, 0),
                status = 'complete',
                added_at = COALESCE(batch_date, datetime('now'))
            WHERE quantity_needed IS NULL OR quantity_needed = 0
        """)
        
        rows_updated = cursor.rowcount
        print(f"✅ تم تحديث {rows_updated} صف من البيانات القديمة")
        
        # إنشاء الفهارس
        indexes = [
            ("idx_order_material", "order_id, material_id"),
            ("idx_material_order", "material_id, order_id"),
            ("idx_om_status", "status"),
            ("idx_om_shortage", "quantity_shortage"),
        ]
        
        for idx_name, idx_columns in indexes:
            try:
                cursor.execute(f"""
                    CREATE INDEX IF NOT EXISTS {idx_name} 
                    ON {table_name} ({idx_columns})
                """)
                print(f"✅ تم إنشاء الفهرس: {idx_name}")
            except sqlite3.OperationalError as e:
                print(f"⚠️ الفهرس {idx_name} موجود مسبقاً: {e}")
        
        conn.commit()
        print(f"\n✅ تم تحديث جدول {table_name} بنجاح!")
        return True
        
    except Exception as e:
        conn.rollback()
        print(f"\n❌ خطأ أثناء التحديث: {e}")
        return False
        
    finally:
        conn.close()

if __name__ == "__main__":
    print("╔════════════════════════════════════════════════════════════╗")
    print("║   تحديث جدول order_materials - نظام الخصم المباشر        ║")
    print("╚════════════════════════════════════════════════════════════╝")
    print()
    
    success = migrate_order_materials()
    
    if success:
        print("\n🎉 التحديث مكتمل! يمكنك الآن استخدام النظام الجديد.")
    else:
        print("\n⚠️ فشل التحديث! يرجى مراجعة الأخطاء أعلاه.")

