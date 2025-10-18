#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Migration Script: تحديث مراحل الإنتاج
التاريخ: 2025-10-14
الهدف: تحديث أسماء المراحل القديمة وإضافة مرحلة التركيب

التغييرات:
- "قطع" → "حصر المتطلبات"
- "تجميع" → "التصنيع"
- إضافة مرحلة "التركيب" بين "التصنيع" و "تسليم"
"""

import sqlite3
from datetime import datetime, timezone

def migrate_production_stages():
    """تحديث مراحل الإنتاج في الطلبيات الموجودة"""
    
    # الاتصال بقاعدة البيانات
    db_path = 'instance/kitchen_factory.db'
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        print("=" * 70)
        print("بدء ترحيل مراحل الإنتاج")
        print("=" * 70)
        
        # 1. التحقق من وجود جدول stage
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='stage'")
        if not cursor.fetchone():
            print("❌ جدول stage غير موجود!")
            return False
        
        # 2. عرض المراحل الحالية
        cursor.execute("SELECT DISTINCT stage_name FROM stage ORDER BY stage_name")
        current_stages = cursor.fetchall()
        print("\n📊 المراحل الموجودة حالياً:")
        for stage in current_stages:
            print(f"   - {stage[0]}")
        
        # 3. تحديث مرحلة "قطع" إلى "حصر المتطلبات"
        cursor.execute("SELECT COUNT(*) FROM stage WHERE stage_name = 'قطع'")
        cutting_count = cursor.fetchone()[0]
        
        if cutting_count > 0:
            cursor.execute("""
                UPDATE stage 
                SET stage_name = 'حصر المتطلبات'
                WHERE stage_name = 'قطع'
            """)
            print(f"\n✅ تم تحديث {cutting_count} مرحلة من 'قطع' إلى 'حصر المتطلبات'")
        else:
            print("\n✓ لا توجد مراحل 'قطع' للتحديث")
        
        # 4. تحديث مرحلة "تجميع" إلى "التصنيع"
        cursor.execute("SELECT COUNT(*) FROM stage WHERE stage_name = 'تجميع'")
        assembly_count = cursor.fetchone()[0]
        
        if assembly_count > 0:
            cursor.execute("""
                UPDATE stage 
                SET stage_name = 'التصنيع'
                WHERE stage_name = 'تجميع'
            """)
            print(f"✅ تم تحديث {assembly_count} مرحلة من 'تجميع' إلى 'التصنيع'")
        else:
            print("✓ لا توجد مراحل 'تجميع' للتحديث")
        
        # 5. إضافة مرحلة "التركيب" للطلبيات الموجودة التي ليس لديها
        # نحصل على جميع الطلبيات النشطة
        cursor.execute("""
            SELECT DISTINCT o.id, o.showroom_id 
            FROM orders o
            WHERE o.id NOT IN (
                SELECT order_id FROM stage WHERE stage_name = 'التركيب'
            )
            AND o.id IN (
                SELECT order_id FROM stage WHERE stage_name IN ('التصنيع', 'تجميع')
            )
        """)
        orders_need_installation = cursor.fetchall()
        
        if orders_need_installation:
            added_count = 0
            for order_id, showroom_id in orders_need_installation:
                cursor.execute("""
                    INSERT INTO stage (order_id, stage_name, stage_type, progress, showroom_id)
                    VALUES (?, 'التركيب', 'طلب', 0, ?)
                """, (order_id, showroom_id))
                added_count += 1
            
            print(f"\n✅ تم إضافة مرحلة 'التركيب' لـ {added_count} طلبية")
        else:
            print("\n✓ جميع الطلبيات لديها مرحلة التركيب أو لا تحتاجها")
        
        # 6. حفظ التغييرات
        conn.commit()
        
        # 7. عرض المراحل بعد التحديث
        cursor.execute("SELECT DISTINCT stage_name FROM stage ORDER BY stage_name")
        updated_stages = cursor.fetchall()
        print("\n📊 المراحل بعد التحديث:")
        for stage in updated_stages:
            print(f"   - {stage[0]}")
        
        # 8. إحصائيات نهائية
        print("\n" + "=" * 70)
        print("📈 إحصائيات التحديث:")
        print("=" * 70)
        
        cursor.execute("SELECT stage_name, COUNT(*) FROM stage GROUP BY stage_name")
        stats = cursor.fetchall()
        for stage_name, count in stats:
            print(f"   {stage_name}: {count} مرحلة")
        
        print("\n✅ اكتمل الترحيل بنجاح!")
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
    print("\n🚀 سكربت ترحيل مراحل الإنتاج")
    print("   التاريخ: 2025-10-14\n")
    
    # تأكيد من المستخدم
    response = input("⚠️  هل تريد المتابعة مع الترحيل؟ (yes/no): ")
    if response.lower() in ['yes', 'y', 'نعم']:
        success = migrate_production_stages()
        if success:
            print("\n✅ تم التحديث بنجاح!")
            print("   يمكنك الآن تشغيل التطبيق")
        else:
            print("\n❌ فشل التحديث!")
            print("   راجع الأخطاء أعلاه")
    else:
        print("\n❌ تم إلغاء العملية")

