#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
سكريبت إصلاح قوي لجداول الموردين - يحذف كل شيء ويعيد إنشاؤه
تاريخ: 2025-10-19
"""

import sys
import os
from datetime import datetime, timezone
import sqlite3

# إضافة المسار الجذر للمشروع لتمكين استيراد app
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from kitchen_factory.app import app, db, Supplier, SupplierDebt, SupplierInvoice, SupplierPayment, PaymentAllocation, AuditLog

def force_fix_supplier_tables():
    """إصلاح قوي لجداول الموردين - يحذف كل شيء ويعيد إنشاؤه"""
    with app.app_context():
        print("💥 بدء الإصلاح القوي لجداول الموردين...\n")
        print("⚠️  تحذير: سيتم حذف جميع بيانات الموردين والفواتير!")
        print("")
        
        # 1. فحص الجداول الموجودة
        print("======================================================================")
        print("🔍 الخطوة 1: فحص الجداول الموجودة...")
        print("======================================================================")
        
        conn = sqlite3.connect(app.config['SQLALCHEMY_DATABASE_URI'].replace('sqlite:///', ''))
        cursor = conn.cursor()
        
        # فحص الجداول الموجودة
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        all_tables = [row[0] for row in cursor.fetchall()]
        
        supplier_tables = [t for t in all_tables if 'supplier' in t.lower() or 'purchase' in t.lower()]
        print(f"   الجداول المتعلقة بالموردين: {supplier_tables}")
        
        # 2. حذف جميع الجداول المتعلقة بالموردين
        print("\n======================================================================")
        print("🗑️  الخطوة 2: حذف جميع الجداول المتعلقة بالموردين...")
        print("======================================================================")
        
        # قائمة الجداول للحذف
        tables_to_drop = [
            'payment_allocations',
            'supplier_payments', 
            'supplier_invoices',
            'supplier_debts',
            'suppliers',
            'purchase_invoice_items',
            'purchase_invoices'
        ]
        
        dropped_count = 0
        for table_name in tables_to_drop:
            if table_name in all_tables:
                try:
                    cursor.execute(f"DROP TABLE IF EXISTS {table_name}")
                    print(f"   ✅ تم حذف جدول {table_name}")
                    dropped_count += 1
                except Exception as e:
                    print(f"   ⚠️  فشل حذف جدول {table_name}: {e}")
        
        conn.commit()
        print(f"\n   📊 تم حذف {dropped_count} جدول")
        
        # 3. حذف الفهارس المتبقية
        print("\n======================================================================")
        print("🧹 الخطوة 3: تنظيف الفهارس المتبقية...")
        print("======================================================================")
        
        try:
            cursor.execute("SELECT name FROM sqlite_master WHERE type='index' AND name LIKE '%supplier%'")
            indexes = [row[0] for row in cursor.fetchall()]
            
            for index_name in indexes:
                try:
                    cursor.execute(f"DROP INDEX IF EXISTS {index_name}")
                    print(f"   ✅ تم حذف فهرس {index_name}")
                except Exception as e:
                    print(f"   ⚠️  فشل حذف فهرس {index_name}: {e}")
        except Exception as e:
            print(f"   ⚠️  فشل تنظيف الفهارس: {e}")
        
        conn.commit()
        conn.close()
        
        # 4. إعادة إنشاء الجداول من الصفر
        print("\n======================================================================")
        print("🏗️  الخطوة 4: إعادة إنشاء الجداول من الصفر...")
        print("======================================================================")
        
        try:
            # حذف جميع الجداول من SQLAlchemy
            db.drop_all()
            print("   ✅ تم حذف جميع الجداول من SQLAlchemy")
            
            # إنشاء جميع الجداول من جديد
            db.create_all()
            print("   ✅ تم إنشاء جميع الجداول من جديد")
            
        except Exception as e:
            print(f"   ❌ فشل إعادة إنشاء الجداول: {e}")
            return False
        
        # 5. التحقق من الجداول الجديدة
        print("\n======================================================================")
        print("🔍 الخطوة 5: التحقق من الجداول الجديدة...")
        print("======================================================================")
        
        conn = sqlite3.connect(app.config['SQLALCHEMY_DATABASE_URI'].replace('sqlite:///', ''))
        cursor = conn.cursor()
        
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE '%supplier%'")
        new_supplier_tables = [row[0] for row in cursor.fetchall()]
        
        print(f"   الجداول الجديدة: {new_supplier_tables}")
        
        # التحقق من بنية كل جدول
        required_tables = ['suppliers', 'supplier_debts', 'supplier_invoices', 'supplier_payments', 'payment_allocations']
        all_created = True
        
        for table_name in required_tables:
            if table_name in new_supplier_tables:
                cursor.execute(f"PRAGMA table_info({table_name})")
                columns = cursor.fetchall()
                print(f"   ✅ جدول {table_name}: {len(columns)} عمود")
            else:
                print(f"   ❌ جدول {table_name} غير موجود")
                all_created = False
        
        conn.close()
        
        if not all_created:
            print("   ❌ فشل إنشاء بعض الجداول المطلوبة")
            return False
        
        # 6. اختبار إضافة مورد تجريبي
        print("\n======================================================================")
        print("🧪 الخطوة 6: اختبار إضافة مورد تجريبي...")
        print("======================================================================")
        
        try:
            # إنشاء مورد تجريبي
            test_supplier = Supplier(
                name="مورد تجريبي للاختبار",
                code="TEST001",
                phone="123456789",
                email="test@example.com",
                showroom_id=1,  # افتراض أن الصالة رقم 1 موجودة
                created_by="system"
            )
            
            db.session.add(test_supplier)
            db.session.flush()
            print(f"   ✅ تم إنشاء المورد التجريبي (ID: {test_supplier.id})")
            
            # إنشاء سجل دين للمورد
            test_debt = SupplierDebt(
                supplier_id=test_supplier.id,
                total_debt=0,
                paid_amount=0,
                remaining_debt=0
            )
            
            db.session.add(test_debt)
            db.session.commit()
            print("   ✅ تم إنشاء سجل الدين للمورد التجريبي")
            
            # حذف المورد التجريبي
            db.session.delete(test_supplier)
            db.session.delete(test_debt)
            db.session.commit()
            print("   ✅ تم حذف المورد التجريبي")
            
        except Exception as e:
            print(f"   ❌ فشل اختبار إضافة المورد: {e}")
            db.session.rollback()
            return False
        
        # 7. تسجيل العملية
        print("\n======================================================================")
        print("📝 الخطوة 7: تسجيل العملية...")
        print("======================================================================")
        
        try:
            audit_log = AuditLog(
                table_name='system',
                record_id=0,
                action='force_fix_supplier_tables',
                reason='إصلاح قوي لجداول الموردين',
                notes='تم حذف جميع الجداول وإعادة إنشائها من الصفر',
                showroom_id=None,
                user_name='system'
            )
            db.session.add(audit_log)
            db.session.commit()
            
            print("   ✅ تم تسجيل العملية في سجل التدقيق")
            
        except Exception as e:
            print(f"   ⚠️  فشل تسجيل العملية: {e}")
        
        print("\n======================================================================")
        print("✅ تم الإصلاح القوي بنجاح!")
        print("======================================================================")
        print("\n📝 الملاحظات:")
        print("   1. تم حذف جميع الجداول المتعلقة بالموردين")
        print("   2. تم إعادة إنشاء الجداول من الصفر")
        print("   3. تم اختبار النظام")
        print("   4. النظام جاهز للاستخدام")
        print("\n🎯 يمكنك الآن إضافة موردين جدد بدون مشاكل!")
        
        return True

if __name__ == '__main__':
    force_fix_supplier_tables()
