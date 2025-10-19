#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
سكريبت اختبار إنشاء قاعدة البيانات
تاريخ: 2025-10-19
"""

import sys
import os
from datetime import datetime, timezone
import sqlite3

# إضافة المسار الجذر للمشروع لتمكين استيراد app
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from kitchen_factory.app import app, db, Supplier, SupplierDebt, SupplierInvoice, SupplierPayment, PaymentAllocation

def test_db_creation():
    """اختبار إنشاء قاعدة البيانات"""
    with app.app_context():
        print("🧪 بدء اختبار إنشاء قاعدة البيانات...\n")
        
        # 1. فحص الجداول الموجودة قبل الإنشاء
        print("======================================================================")
        print("🔍 الخطوة 1: فحص الجداول الموجودة...")
        print("======================================================================")
        
        conn = sqlite3.connect(app.config['SQLALCHEMY_DATABASE_URI'].replace('sqlite:///', ''))
        cursor = conn.cursor()
        
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE '%supplier%'")
        existing_tables = [row[0] for row in cursor.fetchall()]
        
        print(f"   الجداول الموجودة: {existing_tables}")
        conn.close()
        
        # 2. محاولة إنشاء الجداول
        print("\n======================================================================")
        print("🏗️  الخطوة 2: محاولة إنشاء الجداول...")
        print("======================================================================")
        
        try:
            # محاولة إنشاء جدول واحد فقط
            print("   محاولة إنشاء جدول PaymentAllocation...")
            
            # إنشاء الجدول يدوياً أولاً
            conn = sqlite3.connect(app.config['SQLALCHEMY_DATABASE_URI'].replace('sqlite:///', ''))
            cursor = conn.cursor()
            
            # حذف الجدول إذا كان موجوداً
            cursor.execute("DROP TABLE IF EXISTS payment_allocations")
            
            # إنشاء الجدول
            cursor.execute("""
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
            """)
            
            conn.commit()
            conn.close()
            
            print("   ✅ تم إنشاء جدول payment_allocations يدوياً")
            
        except Exception as e:
            print(f"   ❌ فشل إنشاء الجدول يدوياً: {e}")
            return False
        
        # 3. اختبار db.create_all()
        print("\n======================================================================")
        print("🔧 الخطوة 3: اختبار db.create_all()...")
        print("======================================================================")
        
        try:
            # محاولة إنشاء جميع الجداول
            db.create_all()
            print("   ✅ تم تنفيذ db.create_all() بنجاح")
            
        except Exception as e:
            print(f"   ❌ فشل db.create_all(): {e}")
            return False
        
        # 4. التحقق من الجداول بعد الإنشاء
        print("\n======================================================================")
        print("🔍 الخطوة 4: التحقق من الجداول بعد الإنشاء...")
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
        
        if all_created:
            print("\n✅ تم إنشاء جميع الجداول بنجاح!")
            return True
        else:
            print("\n❌ فشل إنشاء بعض الجداول")
            return False

if __name__ == '__main__':
    test_db_creation()
