#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
سكريبت إصلاح جداول الموردين على السيرفر
تاريخ: 2025-10-19
"""

import sys
import os
from datetime import datetime, timezone
import sqlite3

# إضافة المسار الجذر للمشروع لتمكين استيراد app
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from kitchen_factory.app import app, db, Supplier, SupplierDebt, SupplierInvoice, SupplierPayment, PaymentAllocation, AuditLog

def fix_server_supplier_tables():
    """إصلاح جداول الموردين على السيرفر"""
    with app.app_context():
        print("🔧 بدء إصلاح جداول الموردين على السيرفر...\n")
        
        # 1. فحص الجداول الموجودة
        print("======================================================================")
        print("🔍 الخطوة 1: فحص الجداول الموجودة...")
        print("======================================================================")
        
        conn = sqlite3.connect(app.config['SQLALCHEMY_DATABASE_URI'].replace('sqlite:///', ''))
        cursor = conn.cursor()
        
        # فحص الجداول الموجودة
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE '%supplier%'")
        existing_tables = [row[0] for row in cursor.fetchall()]
        
        print(f"   الجداول الموجودة: {existing_tables}")
        
        # 2. حذف الجداول القديمة إذا كانت موجودة
        print("\n======================================================================")
        print("🗑️  الخطوة 2: حذف الجداول القديمة...")
        print("======================================================================")
        
        old_tables = ['purchase_invoice_items', 'supplier_payments', 'purchase_invoices', 'suppliers']
        
        for table_name in old_tables:
            if table_name in existing_tables:
                try:
                    cursor.execute(f"DROP TABLE IF EXISTS {table_name}")
                    print(f"   ✅ تم حذف جدول {table_name}")
                except Exception as e:
                    print(f"   ⚠️  فشل حذف جدول {table_name}: {e}")
        
        # 3. حذف الجداول الجديدة إذا كانت موجودة (لإعادة إنشائها)
        print("\n======================================================================")
        print("🔄 الخطوة 3: إعادة إنشاء الجداول الجديدة...")
        print("======================================================================")
        
        new_tables = ['suppliers', 'supplier_debts', 'supplier_invoices', 'supplier_payments', 'payment_allocations']
        
        for table_name in new_tables:
            if table_name in existing_tables:
                try:
                    cursor.execute(f"DROP TABLE IF EXISTS {table_name}")
                    print(f"   ✅ تم حذف جدول {table_name} لإعادة إنشائه")
                except Exception as e:
                    print(f"   ⚠️  فشل حذف جدول {table_name}: {e}")
        
        conn.commit()
        conn.close()
        
        # 4. إنشاء الجداول الجديدة
        print("\n======================================================================")
        print("🏗️  الخطوة 4: إنشاء الجداول الجديدة...")
        print("======================================================================")
        
        try:
            # إنشاء جميع الجداول
            db.create_all()
            print("   ✅ تم إنشاء جميع الجداول الجديدة")
        except Exception as e:
            print(f"   ❌ فشل إنشاء الجداول: {e}")
            return False
        
        # 5. التحقق من الجداول الجديدة
        print("\n======================================================================")
        print("🔍 الخطوة 5: التحقق من الجداول الجديدة...")
        print("======================================================================")
        
        conn = sqlite3.connect(app.config['SQLALCHEMY_DATABASE_URI'].replace('sqlite:///', ''))
        cursor = conn.cursor()
        
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE '%supplier%'")
        new_tables = [row[0] for row in cursor.fetchall()]
        
        print(f"   الجداول الجديدة: {new_tables}")
        
        # التحقق من بنية كل جدول
        for table_name in ['suppliers', 'supplier_debts', 'supplier_invoices', 'supplier_payments', 'payment_allocations']:
            if table_name in new_tables:
                cursor.execute(f"PRAGMA table_info({table_name})")
                columns = cursor.fetchall()
                print(f"   ✅ جدول {table_name}: {len(columns)} عمود")
            else:
                print(f"   ❌ جدول {table_name} غير موجود")
        
        conn.close()
        
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
            
            # إنشاء سجل دين للمورد
            test_debt = SupplierDebt(
                supplier_id=test_supplier.id,
                total_debt=0,
                paid_amount=0,
                remaining_debt=0
            )
            
            db.session.add(test_debt)
            db.session.commit()
            
            print("   ✅ تم إضافة مورد تجريبي بنجاح")
            
            # حذف المورد التجريبي
            db.session.delete(test_supplier)
            db.session.delete(test_debt)
            db.session.commit()
            
            print("   ✅ تم حذف المورد التجريبي")
            
        except Exception as e:
            print(f"   ❌ فشل اختبار إضافة المورد: {e}")
            db.session.rollback()
            return False
        
        # 7. تسجيل في سجل التدقيق
        print("\n======================================================================")
        print("📝 الخطوة 7: تسجيل العملية...")
        print("======================================================================")
        
        try:
            audit_log = AuditLog(
                user_id=None,
                action='fix_server_supplier_tables',
                reason='إصلاح جداول الموردين على السيرفر',
                details='تم حذف الجداول القديمة وإنشاء الجداول الجديدة بنجاح',
                showroom_id=None,
                created_at=datetime.now(timezone.utc)
            )
            db.session.add(audit_log)
            db.session.commit()
            
            print("   ✅ تم تسجيل العملية في سجل التدقيق")
            
        except Exception as e:
            print(f"   ⚠️  فشل تسجيل العملية: {e}")
        
        print("\n======================================================================")
        print("✅ تم إصلاح جداول الموردين بنجاح!")
        print("======================================================================")
        print("\n📝 الملاحظات:")
        print("   1. تم حذف الجداول القديمة")
        print("   2. تم إنشاء الجداول الجديدة")
        print("   3. تم اختبار النظام")
        print("   4. النظام جاهز للاستخدام")
        print("\n🎯 يمكنك الآن إضافة موردين جدد بدون مشاكل!")
        
        return True

if __name__ == '__main__':
    fix_server_supplier_tables()
