#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
سكريبت إصلاح مشكلة تكرار سجلات الديون للموردين
تاريخ: 2025-10-19
"""

import sys
import os
from datetime import datetime, timezone
import sqlite3

# إضافة المسار الجذر للمشروع لتمكين استيراد app
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from kitchen_factory.app import app, db, Supplier, SupplierDebt, AuditLog

def fix_supplier_debt_duplicates():
    """إصلاح مشكلة تكرار سجلات الديون"""
    with app.app_context():
        print("🔧 بدء إصلاح مشكلة تكرار سجلات الديون...\n")
        
        # 1. فحص السجلات المكررة
        print("======================================================================")
        print("🔍 الخطوة 1: فحص السجلات المكررة...")
        print("======================================================================")
        
        # البحث عن سجلات الديون المكررة
        conn = sqlite3.connect(app.config['SQLALCHEMY_DATABASE_URI'].replace('sqlite:///', ''))
        cursor = conn.cursor()
        
        # فحص السجلات المكررة
        cursor.execute("""
            SELECT supplier_id, COUNT(*) as count 
            FROM supplier_debts 
            GROUP BY supplier_id 
            HAVING COUNT(*) > 1
        """)
        
        duplicates = cursor.fetchall()
        
        if duplicates:
            print(f"   ⚠️  تم العثور على {len(duplicates)} مورد له سجلات ديون مكررة:")
            for supplier_id, count in duplicates:
                print(f"   • المورد {supplier_id}: {count} سجل دين")
        else:
            print("   ✅ لا توجد سجلات مكررة")
        
        # 2. حذف السجلات المكررة
        print("\n======================================================================")
        print("🗑️  الخطوة 2: حذف السجلات المكررة...")
        print("======================================================================")
        
        deleted_count = 0
        for supplier_id, count in duplicates:
            # الاحتفاظ بأحدث سجل وحذف الباقي
            cursor.execute("""
                DELETE FROM supplier_debts 
                WHERE supplier_id = ? 
                AND id NOT IN (
                    SELECT id FROM supplier_debts 
                    WHERE supplier_id = ? 
                    ORDER BY created_at DESC 
                    LIMIT 1
                )
            """, (supplier_id, supplier_id))
            
            deleted = cursor.rowcount
            deleted_count += deleted
            print(f"   ✅ تم حذف {deleted} سجل مكرر للمورد {supplier_id}")
        
        conn.commit()
        
        # 3. إنشاء سجلات الديون المفقودة
        print("\n======================================================================")
        print("➕ الخطوة 3: إنشاء سجلات الديون المفقودة...")
        print("======================================================================")
        
        # البحث عن الموردين بدون سجلات ديون
        cursor.execute("""
            SELECT s.id, s.name 
            FROM suppliers s 
            LEFT JOIN supplier_debts sd ON s.id = sd.supplier_id 
            WHERE sd.id IS NULL AND s.is_active = 1
        """)
        
        suppliers_without_debt = cursor.fetchall()
        
        created_count = 0
        for supplier_id, supplier_name in suppliers_without_debt:
            cursor.execute("""
                INSERT INTO supplier_debts (supplier_id, total_debt, paid_amount, remaining_debt, created_at, updated_at)
                VALUES (?, 0.0, 0.0, 0.0, ?, NULL)
            """, (supplier_id, datetime.now(timezone.utc).isoformat()))
            
            created_count += 1
            print(f"   ✅ تم إنشاء سجل دين للمورد {supplier_name} (ID: {supplier_id})")
        
        conn.commit()
        conn.close()
        
        # 4. التحقق النهائي
        print("\n======================================================================")
        print("🔍 الخطوة 4: التحقق النهائي...")
        print("======================================================================")
        
        # فحص السجلات مرة أخرى
        conn = sqlite3.connect(app.config['SQLALCHEMY_DATABASE_URI'].replace('sqlite:///', ''))
        cursor = conn.cursor()
        
        cursor.execute("SELECT COUNT(*) FROM suppliers WHERE is_active = 1")
        active_suppliers = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM supplier_debts")
        debt_records = cursor.fetchone()[0]
        
        cursor.execute("""
            SELECT COUNT(*) 
            FROM suppliers s 
            LEFT JOIN supplier_debts sd ON s.id = sd.supplier_id 
            WHERE s.is_active = 1 AND sd.id IS NULL
        """)
        missing_debts = cursor.fetchone()[0]
        
        conn.close()
        
        print(f"   • الموردين النشطين: {active_suppliers}")
        print(f"   • سجلات الديون: {debt_records}")
        print(f"   • الموردين بدون سجلات ديون: {missing_debts}")
        
        if missing_debts == 0 and debt_records == active_suppliers:
            print("   ✅ تم إصلاح المشكلة بنجاح!")
            
            # تسجيل في سجل التدقيق
            audit_log = AuditLog(
                user_id=None,
                action='fix_supplier_debt_duplicates',
                reason='إصلاح مشكلة تكرار سجلات الديون',
                details=f'تم حذف {deleted_count} سجل مكرر وإنشاء {created_count} سجل جديد',
                showroom_id=None,
                created_at=datetime.now(timezone.utc)
            )
            db.session.add(audit_log)
            db.session.commit()
            
            print("\n✅ تم إصلاح المشكلة بنجاح!")
            return True
        else:
            print("   ❌ لا تزال هناك مشاكل في قاعدة البيانات")
            return False

if __name__ == '__main__':
    fix_supplier_debt_duplicates()
