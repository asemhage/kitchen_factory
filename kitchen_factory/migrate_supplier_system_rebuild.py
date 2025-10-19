"""
سكريبت ترحيل قاعدة البيانات - إعادة بناء نظام الموردين
تاريخ: 2025-10-19
الهدف: حذف الجداول القديمة وإنشاء الجداول الجديدة لنظام الدفع المرن
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from app import app, db
from datetime import datetime, timezone

def migrate_supplier_system():
    """حذف الجداول القديمة وإنشاء الجداول الجديدة"""
    
    print("\n" + "="*70)
    print("🔄 بدء ترحيل نظام الموردين - إعادة بناء كاملة")
    print("="*70 + "\n")
    
    with app.app_context():
        try:
            # 1. حذف الجداول القديمة
            print("🗑️  الخطوة 1: حذف الجداول القديمة...")
            
            old_tables = [
                'purchase_invoice_items',  # يجب حذف الجداول التابعة أولاً
                'supplier_payments',
                'purchase_invoices',
                'suppliers'
            ]
            
            for table in old_tables:
                try:
                    db.session.execute(db.text(f"DROP TABLE IF EXISTS {table}"))
                    print(f"   ✅ تم حذف جدول {table}")
                except Exception as e:
                    print(f"   ⚠️  تحذير عند حذف {table}: {str(e)}")
            
            db.session.commit()
            print("   ✅ تم حذف جميع الجداول القديمة بنجاح\n")
            
            # 2. إنشاء الجداول الجديدة
            print("🏗️  الخطوة 2: إنشاء الجداول الجديدة...")
            
            # إنشاء جميع الجداول
            db.create_all()
            
            new_tables = ['suppliers', 'supplier_debts', 'supplier_invoices', 'supplier_payments', 'payment_allocations']
            
            from sqlalchemy import inspect
            inspector = inspect(db.engine)
            existing_tables = inspector.get_table_names()
            
            all_created = True
            for table in new_tables:
                if table in existing_tables:
                    print(f"   ✅ جدول {table} تم إنشاؤه")
                else:
                    print(f"   ❌ فشل إنشاء جدول {table}")
                    all_created = False
            
            if not all_created:
                print("\n   ⚠️  تحذير: بعض الجداول لم يتم إنشاؤها!")
                return False
            
            # 3. التحقق من البنية
            print("\n🔍 الخطوة 3: التحقق من بنية الجداول الجديدة...")
            
            # فحص جدول suppliers
            columns = [col['name'] for col in inspector.get_columns('suppliers')]
            required_columns = ['id', 'name', 'showroom_id', 'is_active', 'created_at']
            missing = [col for col in required_columns if col not in columns]
            
            if missing:
                print(f"   ⚠️  أعمدة مفقودة في جدول suppliers: {', '.join(missing)}")
            else:
                print(f"   ✅ جدول suppliers يحتوي على جميع الأعمدة المطلوبة")
            
            # فحص جدول supplier_debts
            columns = [col['name'] for col in inspector.get_columns('supplier_debts')]
            required_columns = ['id', 'supplier_id', 'total_debt', 'paid_amount', 'remaining_debt']
            missing = [col for col in required_columns if col not in columns]
            
            if missing:
                print(f"   ⚠️  أعمدة مفقودة في جدول supplier_debts: {', '.join(missing)}")
            else:
                print(f"   ✅ جدول supplier_debts يحتوي على جميع الأعمدة المطلوبة")
            
            # فحص جدول supplier_payments
            columns = [col['name'] for col in inspector.get_columns('supplier_payments')]
            required_columns = ['id', 'supplier_id', 'debt_id', 'amount', 'payment_type', 'allocation_method']
            missing = [col for col in required_columns if col not in columns]
            
            if missing:
                print(f"   ⚠️  أعمدة مفقودة في جدول supplier_payments: {', '.join(missing)}")
            else:
                print(f"   ✅ جدول supplier_payments يحتوي على جميع الأعمدة المطلوبة")
            
            # فحص جدول payment_allocations
            columns = [col['name'] for col in inspector.get_columns('payment_allocations')]
            required_columns = ['id', 'payment_id', 'invoice_id', 'allocated_amount', 'allocation_method']
            missing = [col for col in required_columns if col not in columns]
            
            if missing:
                print(f"   ⚠️  أعمدة مفقودة في جدول payment_allocations: {', '.join(missing)}")
            else:
                print(f"   ✅ جدول payment_allocations يحتوي على جميع الأعمدة المطلوبة")
            
            # 4. عرض الإحصائيات
            print("\n📊 الخطوة 4: إحصائيات النظام الجديد...")
            
            from app import Supplier, SupplierDebt, SupplierInvoice, SupplierPayment, PaymentAllocation
            
            suppliers_count = Supplier.query.count()
            debts_count = SupplierDebt.query.count()
            invoices_count = SupplierInvoice.query.count()
            payments_count = SupplierPayment.query.count()
            allocations_count = PaymentAllocation.query.count()
            
            print(f"   • الموردين: {suppliers_count}")
            print(f"   • الديون: {debts_count}")
            print(f"   • الفواتير: {invoices_count}")
            print(f"   • المدفوعات: {payments_count}")
            print(f"   • التوزيعات: {allocations_count}")
            
            print("\n" + "="*70)
            print("✅ تم إكمال إعادة البناء بنجاح!")
            print("="*70 + "\n")
            
            print("📝 الملاحظات:")
            print("   1. تم حذف الجداول القديمة بالكامل")
            print("   2. تم إنشاء الجداول الجديدة بنجاح")
            print("   3. النظام الجديد جاهز للاستخدام")
            print("   4. النظام يدعم الدفع المرن والتوزيع التلقائي")
            print("\n⚠️  تحذير: جميع بيانات الموردين القديمة تم حذفها!")
            print("   (هذا متوقع حيث لا توجد بيانات إنتاج)\n")
            
        except Exception as e:
            print(f"\n❌ خطأ أثناء الترحيل: {str(e)}")
            import traceback
            traceback.print_exc()
            db.session.rollback()
            return False
    
    return True

if __name__ == '__main__':
    print("\n🚀 بدء عملية إعادة البناء الكاملة...\n")
    print("⚠️  تحذير: سيتم حذف جميع بيانات الموردين القديمة!")
    print("   (هذا آمن لأنه لا توجد بيانات إنتاج)\n")
    
    success = migrate_supplier_system()
    
    if success:
        print("\n✅ تمت إعادة البناء بنجاح!\n")
        sys.exit(0)
    else:
        print("\n❌ فشلت إعادة البناء!\n")
        sys.exit(1)
