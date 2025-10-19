#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
سكريبت اختبار شامل لنظام الموردين
تاريخ: 2025-10-19
"""

import sys
import os
from datetime import datetime, timezone, timedelta
import random

# إضافة المسار الجذر للمشروع لتمكين استيراد app
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from kitchen_factory.app import app, db, Supplier, SupplierDebt, SupplierInvoice, SupplierPayment, PaymentAllocation, Showroom, User, AuditLog

def test_supplier_system():
    """اختبار شامل لنظام الموردين"""
    with app.app_context():
        print("🧪 بدء الاختبار الشامل لنظام الموردين...\n")
        
        test_results = {
            'passed': 0,
            'failed': 0,
            'total': 0
        }
        
        def run_test(test_name, test_func):
            """تشغيل اختبار واحد"""
            test_results['total'] += 1
            try:
                result = test_func()
                if result:
                    print(f"   ✅ {test_name}")
                    test_results['passed'] += 1
                    return True
                else:
                    print(f"   ❌ {test_name}")
                    test_results['failed'] += 1
                    return False
            except Exception as e:
                print(f"   ❌ {test_name}: {e}")
                test_results['failed'] += 1
                return False
        
        # 1. اختبار إنشاء الموردين
        print("======================================================================")
        print("🔍 الاختبار 1: إنشاء الموردين...")
        print("======================================================================")
        
        def test_create_supplier():
            """اختبار إنشاء مورد جديد"""
            # الحصول على صالة افتراضية
            showroom = Showroom.query.first()
            if not showroom:
                return False
            
            supplier = Supplier(
                name=f"مورد اختبار {random.randint(1000, 9999)}",
                code=f"TEST{random.randint(100, 999)}",
                phone="123456789",
                email="test@example.com",
                showroom_id=showroom.id,
                created_by="test_system"
            )
            
            db.session.add(supplier)
            db.session.flush()
            
            # إنشاء سجل دين
            debt = SupplierDebt(
                supplier_id=supplier.id,
                total_debt=0,
                paid_amount=0,
                remaining_debt=0
            )
            
            db.session.add(debt)
            db.session.commit()
            
            return supplier.id is not None
        
        run_test("إنشاء مورد جديد", test_create_supplier)
        
        # 2. اختبار إضافة الفواتير
        print("\n======================================================================")
        print("🔍 الاختبار 2: إضافة الفواتير...")
        print("======================================================================")
        
        def test_create_invoice():
            """اختبار إنشاء فاتورة جديدة"""
            supplier = Supplier.query.filter_by(is_active=True).first()
            if not supplier:
                return False
            
            invoice = SupplierInvoice(
                invoice_number=f"INV-{random.randint(1000, 9999)}",
                supplier_id=supplier.id,
                showroom_id=supplier.showroom_id,
                invoice_date=datetime.now(timezone.utc).date(),
                total_amount=1000.0,
                final_amount=1000.0,
                debt_amount=1000.0,
                created_by="test_system"
            )
            
            db.session.add(invoice)
            db.session.commit()
            
            # تحديث دين المورد
            if supplier.debt:
                supplier.debt.total_debt += 1000.0
                supplier.debt.remaining_debt += 1000.0
                db.session.commit()
            
            return invoice.id is not None
        
        run_test("إنشاء فاتورة جديدة", test_create_invoice)
        
        # 3. اختبار المدفوعات المرنة
        print("\n======================================================================")
        print("🔍 الاختبار 3: المدفوعات المرنة...")
        print("======================================================================")
        
        def test_flexible_payment():
            """اختبار الدفع المرن"""
            supplier = Supplier.query.filter_by(is_active=True).first()
            if not supplier or not supplier.debt:
                return False
            
            # إنشاء دفعة مرنة
            payment = SupplierPayment(
                supplier_id=supplier.id,
                debt_id=supplier.debt.id,
                amount=500.0,
                payment_method="نقد",
                payment_type="flexible",
                allocation_method="auto_fifo",
                created_by="test_system"
            )
            
            db.session.add(payment)
            db.session.flush()
            
            # توزيع الدفعة على الفواتير
            invoices = SupplierInvoice.query.filter_by(
                supplier_id=supplier.id,
                is_active=True
            ).filter(
                SupplierInvoice.debt_status.in_(['unpaid', 'partial'])
            ).order_by(SupplierInvoice.invoice_date.asc()).all()
            
            remaining_payment = 500.0
            for invoice in invoices:
                if remaining_payment <= 0:
                    break
                
                invoice_remaining = invoice.remaining_amount
                if invoice_remaining <= 0:
                    continue
                
                allocated = min(remaining_payment, invoice_remaining)
                
                # تحديث الفاتورة
                invoice.paid_amount += allocated
                invoice.debt_status = 'paid' if invoice.paid_amount >= invoice.debt_amount else 'partial'
                
                # إنشاء توزيع
                allocation = PaymentAllocation(
                    payment_id=payment.id,
                    invoice_id=invoice.id,
                    allocated_amount=allocated,
                    allocation_method='auto_fifo'
                )
                
                db.session.add(allocation)
                remaining_payment -= allocated
            
            # تحديث دين المورد
            supplier.debt.paid_amount += (500.0 - remaining_payment)
            supplier.debt.remaining_debt = supplier.debt.total_debt - supplier.debt.paid_amount
            
            db.session.commit()
            
            return payment.id is not None
        
        run_test("دفع مرن مع توزيع تلقائي", test_flexible_payment)
        
        # 4. اختبار الخصائص المحسوبة
        print("\n======================================================================")
        print("🔍 الاختبار 4: الخصائص المحسوبة...")
        print("======================================================================")
        
        def test_computed_properties():
            """اختبار الخصائص المحسوبة"""
            supplier = Supplier.query.filter_by(is_active=True).first()
            if not supplier:
                return False
            
            # اختبار الخصائص
            total_debt = supplier.total_debt
            total_paid = supplier.total_paid
            
            # اختبار فاتورة
            invoice = SupplierInvoice.query.filter_by(supplier_id=supplier.id).first()
            if invoice:
                remaining = invoice.remaining_amount
                is_paid = invoice.is_fully_paid
                
                return isinstance(total_debt, (int, float)) and isinstance(total_paid, (int, float))
            
            return True
        
        run_test("الخصائص المحسوبة", test_computed_properties)
        
        # 5. اختبار التقارير
        print("\n======================================================================")
        print("🔍 الاختبار 5: التقارير...")
        print("======================================================================")
        
        def test_reports():
            """اختبار التقارير"""
            # اختبار إحصائيات الموردين
            suppliers_count = Supplier.query.filter_by(is_active=True).count()
            invoices_count = SupplierInvoice.query.filter_by(is_active=True).count()
            payments_count = SupplierPayment.query.filter_by(is_active=True).count()
            
            return suppliers_count > 0 and invoices_count > 0 and payments_count > 0
        
        run_test("التقارير والإحصائيات", test_reports)
        
        # 6. اختبار الأداء
        print("\n======================================================================")
        print("🔍 الاختبار 6: الأداء...")
        print("======================================================================")
        
        def test_performance():
            """اختبار الأداء"""
            import time
            
            start_time = time.time()
            
            # اختبار استعلام معقد
            suppliers = Supplier.query.filter_by(is_active=True).all()
            for supplier in suppliers:
                if supplier.debt:
                    debt_amount = supplier.debt.remaining_debt
                if supplier.invoices:
                    invoice_count = len(supplier.invoices)
            
            end_time = time.time()
            execution_time = end_time - start_time
            
            # يجب أن يكون الاستعلام سريعاً (أقل من ثانية)
            return execution_time < 1.0
        
        run_test("أداء الاستعلامات", test_performance)
        
        # 7. اختبار سلامة البيانات
        print("\n======================================================================")
        print("🔍 الاختبار 7: سلامة البيانات...")
        print("======================================================================")
        
        def test_data_integrity():
            """اختبار سلامة البيانات"""
            # التحقق من أن جميع الموردين لديهم سجلات ديون
            suppliers = Supplier.query.filter_by(is_active=True).all()
            for supplier in suppliers:
                if not supplier.debt:
                    return False
            
            # التحقق من أن المبالغ متسقة
            for supplier in suppliers:
                if supplier.debt:
                    expected_remaining = supplier.debt.total_debt - supplier.debt.paid_amount
                    if abs(supplier.debt.remaining_debt - expected_remaining) > 0.01:
                        return False
            
            return True
        
        run_test("سلامة البيانات", test_data_integrity)
        
        # 8. تنظيف البيانات التجريبية
        print("\n======================================================================")
        print("🧹 تنظيف البيانات التجريبية...")
        print("======================================================================")
        
        try:
            # حذف البيانات التجريبية
            test_suppliers = Supplier.query.filter(Supplier.name.like('مورد اختبار%')).all()
            for supplier in test_suppliers:
                # حذف التوزيعات
                PaymentAllocation.query.filter(
                    PaymentAllocation.payment_id.in_(
                        [p.id for p in supplier.payments]
                    )
                ).delete()
                
                # حذف المدفوعات
                SupplierPayment.query.filter_by(supplier_id=supplier.id).delete()
                
                # حذف الفواتير
                SupplierInvoice.query.filter_by(supplier_id=supplier.id).delete()
                
                # حذف الديون
                SupplierDebt.query.filter_by(supplier_id=supplier.id).delete()
                
                # حذف المورد
                db.session.delete(supplier)
            
            db.session.commit()
            print("   ✅ تم تنظيف البيانات التجريبية")
            
        except Exception as e:
            print(f"   ⚠️  فشل تنظيف البيانات: {e}")
        
        # 9. تسجيل نتائج الاختبار
        print("\n======================================================================")
        print("📝 تسجيل نتائج الاختبار...")
        print("======================================================================")
        
        try:
            audit_log = AuditLog(
                table_name='system',
                record_id=0,
                action='test_supplier_system',
                reason='اختبار شامل لنظام الموردين',
                notes=f'تم اجتياز {test_results["passed"]} اختبار من أصل {test_results["total"]}',
                showroom_id=None,
                user_name='test_system'
            )
            db.session.add(audit_log)
            db.session.commit()
            
            print("   ✅ تم تسجيل نتائج الاختبار")
            
        except Exception as e:
            print(f"   ⚠️  فشل تسجيل النتائج: {e}")
        
        # 10. عرض النتائج النهائية
        print("\n======================================================================")
        print("📊 نتائج الاختبار الشامل")
        print("======================================================================")
        
        success_rate = (test_results['passed'] / test_results['total']) * 100 if test_results['total'] > 0 else 0
        
        print(f"   • إجمالي الاختبارات: {test_results['total']}")
        print(f"   • نجح: {test_results['passed']}")
        print(f"   • فشل: {test_results['failed']}")
        print(f"   • معدل النجاح: {success_rate:.1f}%")
        
        if success_rate >= 90:
            print("\n✅ النظام جاهز للإنتاج!")
        elif success_rate >= 70:
            print("\n⚠️  النظام يحتاج تحسينات طفيفة")
        else:
            print("\n❌ النظام يحتاج إصلاحات كبيرة")
        
        return success_rate >= 90

if __name__ == '__main__':
    test_supplier_system()
