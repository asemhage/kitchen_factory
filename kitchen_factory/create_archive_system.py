#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
سكريبت إنشاء نظام الأرشفة الشامل
التاريخ: 2025-10-14
الهدف: إنشاء البنية التحتية الكاملة لنظام الأرشفة

المراحل:
1. إنشاء جداول البيانات الوصفية للأرشيف
2. إنشاء جداول البيانات المؤرشفة
3. إضافة الفهارس والقيود
4. إضافة إعدادات النظام للأرشفة
"""

import sqlite3
from datetime import datetime, timezone
import json
import sys
import os

def create_archive_system():
    """إنشاء نظام الأرشفة الكامل"""
    
    db_path = 'instance/kitchen_factory.db'
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        print("=" * 70)
        print("🚀 بدء إنشاء نظام الأرشفة الشامل")
        print("=" * 70)
        
        # 1. إنشاء جداول البيانات الوصفية
        create_archive_metadata_tables(cursor)
        
        # 2. إنشاء جداول البيانات المؤرشفة  
        create_archive_data_tables(cursor)
        
        # 3. إضافة الفهارس
        create_archive_indexes(cursor)
        
        # 4. إضافة إعدادات النظام
        add_archive_system_settings(cursor)
        
        # 5. إدراج البيانات الافتراضية
        insert_default_archive_data(cursor)
        
        conn.commit()
        
        print("\n" + "=" * 70)
        print("✅ تم إنشاء نظام الأرشفة بنجاح!")
        print("=" * 70)
        
        # عرض إحصائيات الجداول المنشأة
        show_created_tables_stats(cursor)
        
        return True
        
    except Exception as e:
        conn.rollback()
        print(f"\n❌ حدث خطأ أثناء إنشاء نظام الأرشفة: {str(e)}")
        import traceback
        traceback.print_exc()
        return False
        
    finally:
        conn.close()

def create_archive_metadata_tables(cursor):
    """إنشاء جداول البيانات الوصفية للأرشيف"""
    
    print("📋 إنشاء جداول البيانات الوصفية...")
    
    # جدول البيانات الوصفية الرئيسي
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS archive_metadata (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_table TEXT NOT NULL,
            source_id INTEGER NOT NULL,
            archived_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            archived_by TEXT NOT NULL,
            archive_reason TEXT,
            archive_type TEXT DEFAULT 'automatic' CHECK(archive_type IN ('manual', 'automatic', 'scheduled')),
            original_record_json TEXT,
            can_restore BOOLEAN DEFAULT 1,
            restore_conditions TEXT,
            data_size_bytes INTEGER,
            checksum TEXT,
            expires_at DATETIME,
            
            UNIQUE(source_table, source_id)
        )
    """)
    print("✅ تم إنشاء جدول archive_metadata")
    
    # جدول تتبع العلاقات المؤرشفة
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS archive_relationships (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            parent_table TEXT NOT NULL,
            parent_id INTEGER NOT NULL,
            child_table TEXT NOT NULL,
            child_id INTEGER NOT NULL,
            relationship_type TEXT,
            archived_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            archive_batch_id INTEGER,
            
            FOREIGN KEY (archive_batch_id) REFERENCES archive_metadata(id) ON DELETE SET NULL
        )
    """)
    print("✅ تم إنشاء جدول archive_relationships")
    
    # جدول إحصائيات الأرشيف
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS archive_statistics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            table_name TEXT NOT NULL UNIQUE,
            total_archived INTEGER DEFAULT 0,
            total_size_mb REAL DEFAULT 0,
            last_archive_date DATETIME,
            last_restore_date DATETIME,
            average_archive_age_days INTEGER,
            archive_success_rate REAL DEFAULT 100.0,
            last_updated DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    print("✅ تم إنشاء جدول archive_statistics")
    
    # جدول سجل عمليات الأرشفة
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS archive_operations_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            operation_type TEXT NOT NULL CHECK(operation_type IN ('archive', 'restore', 'delete', 'verify', 'search')),
            table_name TEXT,
            record_count INTEGER DEFAULT 0,
            operation_start DATETIME DEFAULT CURRENT_TIMESTAMP,
            operation_end DATETIME,
            duration_seconds INTEGER,
            status TEXT DEFAULT 'running' CHECK(status IN ('running', 'completed', 'failed', 'cancelled')),
            error_message TEXT,
            performed_by TEXT,
            batch_size INTEGER,
            affected_records TEXT,
            performance_metrics TEXT
        )
    """)
    print("✅ تم إنشاء جدول archive_operations_log")
    
    # جدول جدولة الأرشفة التلقائية
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS archive_scheduler (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            table_name TEXT NOT NULL,
            schedule_name TEXT NOT NULL,
            is_enabled BOOLEAN DEFAULT 1,
            cron_expression TEXT,
            archive_condition TEXT NOT NULL,
            batch_size INTEGER DEFAULT 100,
            max_records_per_run INTEGER DEFAULT 1000,
            last_run DATETIME,
            next_run DATETIME,
            success_count INTEGER DEFAULT 0,
            failure_count INTEGER DEFAULT 0,
            last_error TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            created_by TEXT
        )
    """)
    print("✅ تم إنشاء جدول archive_scheduler")

def create_archive_data_tables(cursor):
    """إنشاء جداول البيانات المؤرشفة"""
    
    print("\n📦 إنشاء جداول البيانات المؤرشفة...")
    
    # جداول الطلبيات المؤرشفة
    tables_to_create = [
        ('archive_orders', 'orders', 'الطلبيات'),
        ('archive_stages', 'stage', 'مراحل الطلبيات'),
        ('archive_order_costs', 'order_costs', 'تكاليف الطلبيات'),
        ('archive_order_material', 'order_material', 'مواد الطلبيات'),
        ('archive_documents', 'documents', 'مرفقات الطلبيات'),
        ('archive_received_order', 'received_order', 'استلام الطلبيات'),
        ('archive_payments', 'payments', 'دفعات الطلبيات'),
        
        # جداول الفواتير المؤرشفة
        ('archive_purchase_invoice', 'purchase_invoice', 'فواتير الشراء'),
        ('archive_purchase_invoice_item', 'purchase_invoice_item', 'عناصر فواتير الشراء'),
        ('archive_supplier_payment', 'supplier_payment', 'دفعات الموردين'),
        
        # جداول الفنيين المؤرشفة
        ('archive_technician_due', 'technician_due', 'مستحقات الفنيين'),
        ('archive_technician_payment', 'technician_payment', 'دفعات الفنيين'),
        
        # جداول أخرى
        ('archive_audit_log', 'audit_log', 'سجل التدقيق'),
    ]
    
    for archive_table, source_table, description in tables_to_create:
        try:
            # التحقق من وجود الجدول الأصلي
            cursor.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{source_table}'")
            if cursor.fetchone():
                # إنشاء جدول الأرشيف بنفس بنية الجدول الأصلي
                cursor.execute(f"CREATE TABLE IF NOT EXISTS {archive_table} AS SELECT * FROM {source_table} WHERE 1=0")
                
                # إضافة حقول الأرشفة الخاصة
                try:
                    cursor.execute(f"ALTER TABLE {archive_table} ADD COLUMN archive_metadata_id INTEGER")
                except sqlite3.OperationalError:
                    pass  # العمود موجود بالفعل
                
                try:
                    cursor.execute(f"ALTER TABLE {archive_table} ADD COLUMN archived_at DATETIME DEFAULT CURRENT_TIMESTAMP")
                except sqlite3.OperationalError:
                    pass  # العمود موجود بالفعل
                
                print(f"✅ تم إنشاء جدول {archive_table} ({description})")
            else:
                print(f"⚠️  الجدول الأصلي {source_table} غير موجود - تخطي {archive_table}")
        except Exception as e:
            print(f"❌ خطأ في إنشاء {archive_table}: {str(e)}")

def create_archive_indexes(cursor):
    """إنشاء الفهارس للأداء الأمثل"""
    
    print("\n🔍 إنشاء الفهارس...")
    
    # فهارس جدول البيانات الوصفية
    indexes = [
        ("idx_archive_metadata_source", "archive_metadata", "source_table, source_id"),
        ("idx_archive_metadata_date", "archive_metadata", "archived_at"),
        ("idx_archive_metadata_type", "archive_metadata", "archive_type"),
        ("idx_archive_metadata_user", "archive_metadata", "archived_by"),
        ("idx_archive_metadata_restore", "archive_metadata", "can_restore"),
        
        # فهارس جدول العلاقات
        ("idx_archive_rel_parent", "archive_relationships", "parent_table, parent_id"),
        ("idx_archive_rel_child", "archive_relationships", "child_table, child_id"),
        ("idx_archive_rel_batch", "archive_relationships", "archive_batch_id"),
        
        # فهارس جدول الإحصائيات
        ("idx_archive_stats_table", "archive_statistics", "table_name"),
        ("idx_archive_stats_date", "archive_statistics", "last_archive_date"),
        
        # فهارس سجل العمليات
        ("idx_archive_ops_type", "archive_operations_log", "operation_type"),
        ("idx_archive_ops_start", "archive_operations_log", "operation_start"),
        ("idx_archive_ops_status", "archive_operations_log", "status"),
        ("idx_archive_ops_table", "archive_operations_log", "table_name"),
        ("idx_archive_ops_user", "archive_operations_log", "performed_by"),
        
        # فهارس جدولة الأرشفة
        ("idx_archive_sched_table", "archive_scheduler", "table_name"),
        ("idx_archive_sched_enabled", "archive_scheduler", "is_enabled"),
        ("idx_archive_sched_next", "archive_scheduler", "next_run"),
    ]
    
    for index_name, table_name, columns in indexes:
        try:
            cursor.execute(f"CREATE INDEX IF NOT EXISTS {index_name} ON {table_name}({columns})")
            print(f"✅ تم إنشاء فهرس {index_name}")
        except Exception as e:
            print(f"❌ خطأ في إنشاء الفهرس {index_name}: {str(e)}")

def add_archive_system_settings(cursor):
    """إضافة إعدادات نظام الأرشفة"""
    
    print("\n⚙️ إضافة إعدادات نظام الأرشفة...")
    
    # إعدادات الأرشفة
    archive_settings = [
        # إعدادات التفعيل والتحكم العام
        ('archive_system_enabled', 'true', 'boolean', 'archive', 'تفعيل نظام الأرشفة الشامل'),
        ('archive_auto_mode_enabled', 'true', 'boolean', 'archive', 'تفعيل الأرشفة التلقائية'),
        ('archive_manual_mode_enabled', 'true', 'boolean', 'archive', 'السماح بالأرشفة اليدوية'),
        
        # إعدادات الفترات الزمنية (بالأيام)
        ('order_auto_archive_days', '90', 'integer', 'archive', 'أيام أرشفة الطلبيات تلقائياً بعد التسليم'),
        ('invoice_auto_archive_days', '120', 'integer', 'archive', 'أيام أرشفة الفواتير تلقائياً بعد الدفع الكامل'),
        ('technician_payment_archive_days', '180', 'integer', 'archive', 'أيام أرشفة مستحقات الفنيين بعد الدفع'),
        ('audit_log_archive_days', '180', 'integer', 'archive', 'أيام أرشفة سجل التدقيق'),
        
        # إعدادات الأداء والكفاءة
        ('archive_batch_size', '50', 'integer', 'archive', 'عدد السجلات في الدفعة الواحدة للأرشفة'),
        ('archive_max_daily_records', '500', 'integer', 'archive', 'الحد الأقصى للسجلات المؤرشفة يومياً'),
        ('archive_compression_enabled', 'false', 'boolean', 'archive', 'تفعيل ضغط البيانات المؤرشفة'),
        
        # إعدادات الأمان والصلاحيات
        ('archive_encryption_enabled', 'false', 'boolean', 'archive', 'تفعيل تشفير البيانات الحساسة في الأرشيف'),
        ('archive_access_log_enabled', 'true', 'boolean', 'archive', 'تسجيل جميع عمليات الوصول للأرشيف'),
        ('max_restore_records_per_day', '10', 'integer', 'archive', 'الحد الأقصى لاستعادة السجلات يومياً'),
        ('archive_admin_notification', 'true', 'boolean', 'archive', 'إرسال إشعارات للمدير عن عمليات الأرشفة'),
        
        # إعدادات النسخ الاحتياطي والصيانة
        ('archive_backup_enabled', 'true', 'boolean', 'archive', 'تفعيل النسخ الاحتياطي للأرشيف'),
        ('archive_retention_years', '7', 'integer', 'archive', 'مدة الاحتفاظ بالبيانات المؤرشفة بالسنوات'),
        
        # إعدادات الواجهة والعرض
        ('archive_search_results_limit', '100', 'integer', 'archive', 'الحد الأقصى لنتائج البحث في الأرشيف'),
        ('archive_dashboard_enabled', 'true', 'boolean', 'archive', 'عرض إحصائيات الأرشيف في لوحة التحكم'),
        
        # إعدادات التشغيل والجدولة
        ('archive_scheduler_enabled', 'true', 'boolean', 'archive', 'تفعيل جدولة الأرشفة التلقائية'),
        ('archive_daily_maintenance_time', '02:00', 'string', 'archive', 'وقت الصيانة اليومية للأرشيف (24h format)'),
        ('archive_operation_timeout_minutes', '30', 'integer', 'archive', 'انتهاء وقت عمليات الأرشفة بالدقائق'),
    ]
    
    # إضافة الإعدادات
    for key, value, value_type, category, description in archive_settings:
        try:
            cursor.execute("""
                INSERT OR IGNORE INTO system_settings (key, value, value_type, category, description)
                VALUES (?, ?, ?, ?, ?)
            """, (key, value, value_type, category, description))
            print(f"✅ تم إضافة إعداد {key}")
        except Exception as e:
            print(f"❌ خطأ في إضافة إعداد {key}: {str(e)}")

def insert_default_archive_data(cursor):
    """إدراج البيانات الافتراضية لنظام الأرشفة"""
    
    print("\n📊 إدراج البيانات الافتراضية...")
    
    # إضافة إحصائيات افتراضية للجداول
    default_tables = [
        'orders', 'purchase_invoice', 'technician_due', 'audit_log'
    ]
    
    for table in default_tables:
        try:
            cursor.execute("""
                INSERT OR IGNORE INTO archive_statistics (table_name, total_archived, total_size_mb, archive_success_rate)
                VALUES (?, 0, 0.0, 100.0)
            """, (table,))
            print(f"✅ تم إضافة إحصائيات افتراضية لجدول {table}")
        except Exception as e:
            print(f"❌ خطأ في إضافة إحصائيات {table}: {str(e)}")
    
    # إضافة جداول أرشفة افتراضية
    default_schedules = [
        {
            'table_name': 'orders',
            'schedule_name': 'أرشفة الطلبيات المسلّمة تلقائياً',
            'archive_condition': "status = 'مسلّم' AND delivery_date <= DATE('now', '-90 days')",
            'batch_size': 50
        },
        {
            'table_name': 'purchase_invoice', 
            'schedule_name': 'أرشفة الفواتير المدفوعة تلقائياً',
            'archive_condition': "status = 'paid' AND payment_date <= DATE('now', '-120 days')",
            'batch_size': 30
        },
        {
            'table_name': 'audit_log',
            'schedule_name': 'أرشفة سجل التدقيق القديم',
            'archive_condition': "created_at <= DATE('now', '-180 days') AND action_type NOT LIKE 'login%'",
            'batch_size': 100
        }
    ]
    
    for schedule in default_schedules:
        try:
            cursor.execute("""
                INSERT OR IGNORE INTO archive_scheduler 
                (table_name, schedule_name, archive_condition, batch_size, created_by)
                VALUES (?, ?, ?, ?, 'system')
            """, (schedule['table_name'], schedule['schedule_name'], 
                  schedule['archive_condition'], schedule['batch_size']))
            print(f"✅ تم إضافة جدولة {schedule['schedule_name']}")
        except Exception as e:
            print(f"❌ خطأ في إضافة جدولة {schedule['schedule_name']}: {str(e)}")

def show_created_tables_stats(cursor):
    """عرض إحصائيات الجداول المنشأة"""
    
    print("\n📈 إحصائيات الجداول المنشأة:")
    print("-" * 50)
    
    # عدد الجداول المنشأة
    cursor.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name LIKE 'archive_%'")
    archive_tables_count = cursor.fetchone()[0]
    
    print(f"📦 جداول الأرشيف: {archive_tables_count}")
    
    # عدد الفهارس المنشأة
    cursor.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='index' AND name LIKE 'idx_archive_%'")
    archive_indexes_count = cursor.fetchone()[0]
    
    print(f"🔍 فهارس الأرشيف: {archive_indexes_count}")
    
    # عدد الإعدادات المضافة
    cursor.execute("SELECT COUNT(*) FROM system_settings WHERE category = 'archive'")
    archive_settings_count = cursor.fetchone()[0]
    
    print(f"⚙️ إعدادات الأرشفة: {archive_settings_count}")
    
    # عدد الجداول المجدولة
    cursor.execute("SELECT COUNT(*) FROM archive_scheduler")
    scheduled_tables_count = cursor.fetchone()[0]
    
    print(f"📅 الجداول المجدولة: {scheduled_tables_count}")
    
    print("-" * 50)
    print("🎯 نظام الأرشفة جاهز للاستخدام!")

if __name__ == '__main__':
    print("🔧 سكريبت إنشاء نظام الأرشفة الشامل")
    print("   التاريخ: 2025-10-14\n")
    
    # تأكيد من المستخدم
    if len(sys.argv) > 1 and sys.argv[1] == '--force':
        success = create_archive_system()
    else:
        response = input("⚠️  هذا السكريبت سيقوم بإنشاء نظام الأرشفة الكامل. هل تريد المتابعة؟ (yes/no): ")
        if response.lower() in ['yes', 'y', 'نعم']:
            success = create_archive_system()
        else:
            print("\n❌ تم إلغاء العملية")
            sys.exit(0)
            
    if success:
        print("\n✅ تم إنشاء نظام الأرشفة بنجاح!")
        print("يمكنك الآن البدء بتطوير وظائف الأرشفة في التطبيق.")
    else:
        print("\n❌ فشل في إنشاء نظام الأرشفة!")
        sys.exit(1)
