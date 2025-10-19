#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
سكريبت إنشاء جداول الموردين يدوياً
تاريخ: 2025-10-19
"""

import sys
import os
from datetime import datetime, timezone
import sqlite3

# إضافة المسار الجذر للمشروع لتمكين استيراد app
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from kitchen_factory.app import app, db, Supplier, SupplierDebt, SupplierInvoice, SupplierPayment, PaymentAllocation, AuditLog

def manual_create_supplier_tables():
    """إنشاء جداول الموردين يدوياً"""
    with app.app_context():
        print("🔧 بدء إنشاء جداول الموردين يدوياً...\n")
        
        # 1. فحص الجداول الموجودة
        print("======================================================================")
        print("🔍 الخطوة 1: فحص الجداول الموجودة...")
        print("======================================================================")
        
        conn = sqlite3.connect(app.config['SQLALCHEMY_DATABASE_URI'].replace('sqlite:///', ''))
        cursor = conn.cursor()
        
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        existing_tables = [row[0] for row in cursor.fetchall()]
        
        print(f"   الجداول الموجودة: {len(existing_tables)} جدول")
        
        # 2. حذف الجداول القديمة إذا كانت موجودة
        print("\n======================================================================")
        print("🗑️  الخطوة 2: حذف الجداول القديمة...")
        print("======================================================================")
        
        old_tables = ['payment_allocations', 'supplier_payments', 'supplier_invoices', 'supplier_debts', 'suppliers']
        
        for table_name in old_tables:
            if table_name in existing_tables:
                try:
                    cursor.execute(f"DROP TABLE IF EXISTS {table_name}")
                    print(f"   ✅ تم حذف جدول {table_name}")
                except Exception as e:
                    print(f"   ⚠️  فشل حذف جدول {table_name}: {e}")
        
        conn.commit()
        
        # 3. إنشاء جدول suppliers
        print("\n======================================================================")
        print("🏗️  الخطوة 3: إنشاء جدول suppliers...")
        print("======================================================================")
        
        suppliers_sql = """
        CREATE TABLE suppliers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name VARCHAR(100) NOT NULL,
            code VARCHAR(20) UNIQUE,
            phone VARCHAR(20),
            email VARCHAR(100),
            address TEXT,
            tax_id VARCHAR(50),
            contact_person VARCHAR(100),
            payment_terms VARCHAR(200),
            notes TEXT,
            showroom_id INTEGER NOT NULL,
            is_active BOOLEAN DEFAULT 1,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME,
            created_by VARCHAR(100),
            FOREIGN KEY (showroom_id) REFERENCES showrooms (id)
        )
        """
        
        try:
            cursor.execute(suppliers_sql)
            print("   ✅ تم إنشاء جدول suppliers")
        except Exception as e:
            print(f"   ❌ فشل إنشاء جدول suppliers: {e}")
            return False
        
        # 4. إنشاء جدول supplier_debts
        print("\n======================================================================")
        print("🏗️  الخطوة 4: إنشاء جدول supplier_debts...")
        print("======================================================================")
        
        supplier_debts_sql = """
        CREATE TABLE supplier_debts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            supplier_id INTEGER NOT NULL UNIQUE,
            total_debt DECIMAL(10,2) DEFAULT 0,
            paid_amount DECIMAL(10,2) DEFAULT 0,
            remaining_debt DECIMAL(10,2) DEFAULT 0,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME,
            FOREIGN KEY (supplier_id) REFERENCES suppliers (id) ON DELETE CASCADE
        )
        """
        
        try:
            cursor.execute(supplier_debts_sql)
            print("   ✅ تم إنشاء جدول supplier_debts")
        except Exception as e:
            print(f"   ❌ فشل إنشاء جدول supplier_debts: {e}")
            return False
        
        # 5. إنشاء جدول supplier_invoices
        print("\n======================================================================")
        print("🏗️  الخطوة 5: إنشاء جدول supplier_invoices...")
        print("======================================================================")
        
        supplier_invoices_sql = """
        CREATE TABLE supplier_invoices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            invoice_number VARCHAR(50) NOT NULL,
            supplier_id INTEGER NOT NULL,
            showroom_id INTEGER NOT NULL,
            invoice_date DATE NOT NULL,
            due_date DATE,
            total_amount DECIMAL(10,2) NOT NULL,
            final_amount DECIMAL(10,2) NOT NULL,
            debt_status VARCHAR(20) DEFAULT 'unpaid',
            debt_amount DECIMAL(10,2) DEFAULT 0,
            paid_amount DECIMAL(10,2) DEFAULT 0,
            is_active BOOLEAN DEFAULT 1,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME,
            created_by VARCHAR(100),
            FOREIGN KEY (supplier_id) REFERENCES suppliers (id) ON DELETE CASCADE,
            FOREIGN KEY (showroom_id) REFERENCES showrooms (id)
        )
        """
        
        try:
            cursor.execute(supplier_invoices_sql)
            print("   ✅ تم إنشاء جدول supplier_invoices")
        except Exception as e:
            print(f"   ❌ فشل إنشاء جدول supplier_invoices: {e}")
            return False
        
        # 6. إنشاء جدول supplier_payments
        print("\n======================================================================")
        print("🏗️  الخطوة 6: إنشاء جدول supplier_payments...")
        print("======================================================================")
        
        supplier_payments_sql = """
        CREATE TABLE supplier_payments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            supplier_id INTEGER NOT NULL,
            debt_id INTEGER,
            amount DECIMAL(10,2) NOT NULL,
            payment_date DATE NOT NULL,
            payment_method VARCHAR(50),
            payment_type VARCHAR(20) DEFAULT 'flexible',
            allocation_method VARCHAR(20) DEFAULT 'auto_fifo',
            reference_number VARCHAR(100),
            notes TEXT,
            is_active BOOLEAN DEFAULT 1,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME,
            created_by VARCHAR(100),
            FOREIGN KEY (supplier_id) REFERENCES suppliers (id) ON DELETE CASCADE,
            FOREIGN KEY (debt_id) REFERENCES supplier_debts (id)
        )
        """
        
        try:
            cursor.execute(supplier_payments_sql)
            print("   ✅ تم إنشاء جدول supplier_payments")
        except Exception as e:
            print(f"   ❌ فشل إنشاء جدول supplier_payments: {e}")
            return False
        
        # 7. إنشاء جدول payment_allocations
        print("\n======================================================================")
        print("🏗️  الخطوة 7: إنشاء جدول payment_allocations...")
        print("======================================================================")
        
        payment_allocations_sql = """
        CREATE TABLE payment_allocations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            payment_id INTEGER NOT NULL,
            invoice_id INTEGER NOT NULL,
            allocated_amount DECIMAL(10,2) NOT NULL,
            allocation_date DATETIME DEFAULT CURRENT_TIMESTAMP,
            allocation_method VARCHAR(20) DEFAULT 'auto_fifo',
            notes TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (payment_id) REFERENCES supplier_payments (id) ON DELETE CASCADE,
            FOREIGN KEY (invoice_id) REFERENCES supplier_invoices (id) ON DELETE CASCADE
        )
        """
        
        try:
            cursor.execute(payment_allocations_sql)
            print("   ✅ تم إنشاء جدول payment_allocations")
        except Exception as e:
            print(f"   ❌ فشل إنشاء جدول payment_allocations: {e}")
            return False
        
        conn.commit()
        conn.close()
        
        # 8. التحقق من الجداول الجديدة
        print("\n======================================================================")
        print("🔍 الخطوة 8: التحقق من الجداول الجديدة...")
        print("======================================================================")
        
        conn = sqlite3.connect(app.config['SQLALCHEMY_DATABASE_URI'].replace('sqlite:///', ''))
        cursor = conn.cursor()
        
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE '%supplier%'")
        new_tables = [row[0] for row in cursor.fetchall()]
        
        print(f"   الجداول الجديدة: {new_tables}")
        
        required_tables = ['suppliers', 'supplier_debts', 'supplier_invoices', 'supplier_payments', 'payment_allocations']
        all_created = True
        
        for table_name in required_tables:
            if table_name in new_tables:
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
        
        # 9. اختبار إضافة مورد تجريبي
        print("\n======================================================================")
        print("🧪 الخطوة 9: اختبار إضافة مورد تجريبي...")
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
        
        # 10. تسجيل العملية
        print("\n======================================================================")
        print("📝 الخطوة 10: تسجيل العملية...")
        print("======================================================================")
        
        try:
            audit_log = AuditLog(
                table_name='system',
                record_id=0,
                action='manual_create_supplier_tables',
                reason='إنشاء جداول الموردين يدوياً',
                notes='تم إنشاء جميع جداول الموردين يدوياً بنجاح',
                showroom_id=None,
                user_name='system'
            )
            db.session.add(audit_log)
            db.session.commit()
            
            print("   ✅ تم تسجيل العملية في سجل التدقيق")
            
        except Exception as e:
            print(f"   ⚠️  فشل تسجيل العملية: {e}")
        
        print("\n======================================================================")
        print("✅ تم إنشاء جداول الموردين بنجاح!")
        print("======================================================================")
        print("\n📝 الملاحظات:")
        print("   1. تم إنشاء جميع الجداول يدوياً")
        print("   2. تم اختبار النظام")
        print("   3. النظام جاهز للاستخدام")
        print("\n🎯 يمكنك الآن إضافة موردين جدد بدون مشاكل!")
        
        return True

if __name__ == '__main__':
    manual_create_supplier_tables()
