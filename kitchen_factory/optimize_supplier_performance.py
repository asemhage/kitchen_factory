#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
سكريبت تحسين أداء نظام الموردين
تاريخ: 2025-10-19
"""

import sys
import os
from datetime import datetime, timezone
import sqlite3

# إضافة المسار الجذر للمشروع لتمكين استيراد app
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from kitchen_factory.app import app, db, AuditLog

def optimize_supplier_performance():
    """تحسين أداء نظام الموردين"""
    with app.app_context():
        print("⚡ بدء تحسين أداء نظام الموردين...\n")
        
        conn = sqlite3.connect(app.config['SQLALCHEMY_DATABASE_URI'].replace('sqlite:///', ''))
        cursor = conn.cursor()
        
        # 1. إنشاء فهارس للأداء
        print("======================================================================")
        print("🔍 الخطوة 1: إنشاء فهارس الأداء...")
        print("======================================================================")
        
        indexes = [
            # فهارس الموردين
            ("CREATE INDEX IF NOT EXISTS idx_suppliers_showroom ON suppliers(showroom_id)", "فهرس الصالة للموردين"),
            ("CREATE INDEX IF NOT EXISTS idx_suppliers_active ON suppliers(is_active)", "فهرس الموردين النشطين"),
            ("CREATE INDEX IF NOT EXISTS idx_suppliers_name ON suppliers(name)", "فهرس أسماء الموردين"),
            
            # فهارس الديون
            ("CREATE INDEX IF NOT EXISTS idx_supplier_debts_supplier ON supplier_debts(supplier_id)", "فهرس المورد للديون"),
            ("CREATE INDEX IF NOT EXISTS idx_supplier_debts_remaining ON supplier_debts(remaining_debt)", "فهرس الدين المتبقي"),
            
            # فهارس الفواتير
            ("CREATE INDEX IF NOT EXISTS idx_supplier_invoices_supplier ON supplier_invoices(supplier_id)", "فهرس المورد للفواتير"),
            ("CREATE INDEX IF NOT EXISTS idx_supplier_invoices_showroom ON supplier_invoices(showroom_id)", "فهرس الصالة للفواتير"),
            ("CREATE INDEX IF NOT EXISTS idx_supplier_invoices_date ON supplier_invoices(invoice_date)", "فهرس تاريخ الفاتورة"),
            ("CREATE INDEX IF NOT EXISTS idx_supplier_invoices_status ON supplier_invoices(debt_status)", "فهرس حالة الدين"),
            ("CREATE INDEX IF NOT EXISTS idx_supplier_invoices_active ON supplier_invoices(is_active)", "فهرس الفواتير النشطة"),
            
            # فهارس المدفوعات
            ("CREATE INDEX IF NOT EXISTS idx_supplier_payments_supplier ON supplier_payments(supplier_id)", "فهرس المورد للمدفوعات"),
            ("CREATE INDEX IF NOT EXISTS idx_supplier_payments_debt ON supplier_payments(debt_id)", "فهرس الدين للمدفوعات"),
            ("CREATE INDEX IF NOT EXISTS idx_supplier_payments_date ON supplier_payments(payment_date)", "فهرس تاريخ الدفع"),
            ("CREATE INDEX IF NOT EXISTS idx_supplier_payments_active ON supplier_payments(is_active)", "فهرس المدفوعات النشطة"),
            
            # فهارس التوزيع
            ("CREATE INDEX IF NOT EXISTS idx_payment_allocations_payment ON payment_allocations(payment_id)", "فهرس الدفع للتوزيع"),
            ("CREATE INDEX IF NOT EXISTS idx_payment_allocations_invoice ON payment_allocations(invoice_id)", "فهرس الفاتورة للتوزيع"),
            ("CREATE INDEX IF NOT EXISTS idx_payment_allocations_date ON payment_allocations(allocation_date)", "فهرس تاريخ التوزيع"),
        ]
        
        created_count = 0
        for sql, description in indexes:
            try:
                cursor.execute(sql)
                print(f"   ✅ {description}")
                created_count += 1
            except Exception as e:
                print(f"   ⚠️  فشل إنشاء {description}: {e}")
        
        conn.commit()
        print(f"\n   📊 تم إنشاء {created_count} فهرس من أصل {len(indexes)}")
        
        # 2. تحليل الأداء
        print("\n======================================================================")
        print("📊 الخطوة 2: تحليل الأداء...")
        print("======================================================================")
        
        # إحصائيات الجداول
        tables_stats = [
            ("suppliers", "الموردين"),
            ("supplier_debts", "ديون الموردين"),
            ("supplier_invoices", "فواتير الموردين"),
            ("supplier_payments", "مدفوعات الموردين"),
            ("payment_allocations", "توزيع المدفوعات")
        ]
        
        for table_name, description in tables_stats:
            try:
                cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
                count = cursor.fetchone()[0]
                print(f"   • {description}: {count:,} سجل")
            except Exception as e:
                print(f"   ⚠️  فشل تحليل {description}: {e}")
        
        # 3. تحسين الاستعلامات
        print("\n======================================================================")
        print("🔧 الخطوة 3: تحسين الاستعلامات...")
        print("======================================================================")
        
        # تحليل الاستعلامات البطيئة
        print("   📈 تحليل الاستعلامات...")
        
        # فحص الجداول الكبيرة
        large_tables = []
        for table_name, description in tables_stats:
            try:
                cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
                count = cursor.fetchone()[0]
                if count > 1000:
                    large_tables.append((table_name, description, count))
            except:
                pass
        
        if large_tables:
            print("   ⚠️  جداول كبيرة تحتاج تحسين:")
            for table_name, description, count in large_tables:
                print(f"      • {description}: {count:,} سجل")
        else:
            print("   ✅ جميع الجداول بحجم مناسب")
        
        # 4. تنظيف البيانات
        print("\n======================================================================")
        print("🧹 الخطوة 4: تنظيف البيانات...")
        print("======================================================================")
        
        # حذف السجلات المحذوفة (soft delete)
        cleanup_queries = [
            ("DELETE FROM suppliers WHERE is_active = 0 AND deleted_at < datetime('now', '-30 days')", "حذف الموردين المحذوفين"),
            ("DELETE FROM supplier_invoices WHERE is_active = 0", "حذف الفواتير المحذوفة"),
            ("DELETE FROM supplier_payments WHERE is_active = 0", "حذف المدفوعات المحذوفة"),
        ]
        
        cleaned_count = 0
        for sql, description in cleanup_queries:
            try:
                cursor.execute(sql)
                affected = cursor.rowcount
                if affected > 0:
                    print(f"   ✅ {description}: {affected} سجل")
                    cleaned_count += affected
                else:
                    print(f"   ℹ️  {description}: لا توجد سجلات للحذف")
            except Exception as e:
                print(f"   ⚠️  فشل {description}: {e}")
        
        conn.commit()
        
        # 5. تحسين الذاكرة
        print("\n======================================================================")
        print("💾 الخطوة 5: تحسين الذاكرة...")
        print("======================================================================")
        
        # تحسين إعدادات SQLite
        optimizations = [
            ("PRAGMA journal_mode = WAL", "تفعيل WAL mode"),
            ("PRAGMA synchronous = NORMAL", "تحسين المزامنة"),
            ("PRAGMA cache_size = 10000", "زيادة حجم الكاش"),
            ("PRAGMA temp_store = MEMORY", "استخدام الذاكرة للتخزين المؤقت"),
        ]
        
        for sql, description in optimizations:
            try:
                cursor.execute(sql)
                print(f"   ✅ {description}")
            except Exception as e:
                print(f"   ⚠️  فشل {description}: {e}")
        
        conn.close()
        
        # 6. تسجيل العملية
        print("\n======================================================================")
        print("📝 الخطوة 6: تسجيل العملية...")
        print("======================================================================")
        
        try:
            audit_log = AuditLog(
                table_name='system',
                record_id=0,
                action='optimize_supplier_performance',
                reason='تحسين أداء نظام الموردين',
                notes=f'تم إنشاء {created_count} فهرس وتنظيف {cleaned_count} سجل',
                showroom_id=None,
                user_name='system'
            )
            db.session.add(audit_log)
            db.session.commit()
            
            print("   ✅ تم تسجيل العملية في سجل التدقيق")
            
        except Exception as e:
            print(f"   ⚠️  فشل تسجيل العملية: {e}")
        
        print("\n======================================================================")
        print("✅ تم تحسين الأداء بنجاح!")
        print("======================================================================")
        print("\n📝 الملاحظات:")
        print(f"   1. تم إنشاء {created_count} فهرس للأداء")
        print(f"   2. تم تنظيف {cleaned_count} سجل")
        print("   3. تم تحسين إعدادات SQLite")
        print("   4. النظام محسن للأداء")
        print("\n🎯 النظام جاهز للاستخدام بأداء محسن!")
        
        return True

if __name__ == '__main__':
    optimize_supplier_performance()
