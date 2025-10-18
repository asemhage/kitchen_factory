"""
سكريبت تشخيصي لمشكلة إضافة فاتورة شراء
يتحقق من جميع المتطلبات المسبقة
"""
import sys
import os

# إضافة المسار الحالي
sys.path.insert(0, os.path.dirname(__file__))

from app import app, db, Warehouse, Material, Supplier, User, Showroom

def diagnose():
    with app.app_context():
        print("\n" + "="*70)
        print("🔍 تشخيص مشكلة إضافة فاتورة شراء")
        print("="*70 + "\n")
        
        issues = []
        warnings = []
        success = []
        
        # 1. التحقق من المخازن
        print("1️⃣  فحص المخازن...")
        warehouses = Warehouse.query.filter_by(is_active=True).all()
        if not warehouses:
            issues.append("❌ لا توجد مخازن نشطة في النظام")
            print("   ❌ لا توجد مخازن نشطة")
        else:
            print(f"   ✅ عدد المخازن النشطة: {len(warehouses)}")
            success.append(f"✅ المخازن: {len(warehouses)}")
            for wh in warehouses:
                print(f"      - {wh.name} (ID: {wh.id})" + (" [افتراضي]" if wh.is_default else ""))
            
            # التحقق من المخزن الافتراضي
            default_warehouse = Warehouse.query.filter_by(is_default=True).first()
            if not default_warehouse:
                warnings.append("⚠️  لا يوجد مخزن افتراضي محدد")
                print("   ⚠️  لا يوجد مخزن افتراضي")
        
        # 2. التحقق من المواد
        print("\n2️⃣  فحص المواد...")
        materials = Material.query.filter_by(is_active=True).all()
        if not materials:
            issues.append("❌ لا توجد مواد نشطة في النظام")
            print("   ❌ لا توجد مواد نشطة")
        else:
            print(f"   ✅ عدد المواد النشطة: {len(materials)}")
            success.append(f"✅ المواد: {len(materials)}")
            
            # التحقق من ارتباط المواد بالمخازن
            materials_without_warehouse = [m for m in materials if not m.warehouse_id]
            if materials_without_warehouse:
                issues.append(f"❌ {len(materials_without_warehouse)} مادة غير مرتبطة بمخزن")
                print(f"   ❌ {len(materials_without_warehouse)} مادة غير مرتبطة بمخزن:")
                for m in materials_without_warehouse[:5]:  # عرض أول 5
                    print(f"      - {m.name} (ID: {m.id})")
            else:
                print("   ✅ جميع المواد مرتبطة بمخازن")
                success.append("✅ جميع المواد مرتبطة بمخازن")
        
        # 3. التحقق من الموردين
        print("\n3️⃣  فحص الموردين...")
        suppliers = Supplier.query.filter_by(is_active=True).all()
        if not suppliers:
            issues.append("❌ لا يوجد موردين نشطين في النظام")
            print("   ❌ لا يوجد موردين نشطين")
        else:
            print(f"   ✅ عدد الموردين النشطين: {len(suppliers)}")
            success.append(f"✅ الموردين: {len(suppliers)}")
            for sup in suppliers[:5]:  # عرض أول 5
                print(f"      - {sup.name} (ID: {sup.id})")
        
        # 4. التحقق من الصالات
        print("\n4️⃣  فحص الصالات...")
        showrooms = Showroom.query.filter_by(is_active=True).all()
        if not showrooms:
            issues.append("❌ لا توجد صالات نشطة في النظام")
            print("   ❌ لا توجد صالات نشطة")
        else:
            print(f"   ✅ عدد الصالات النشطة: {len(showrooms)}")
            success.append(f"✅ الصالات: {len(showrooms)}")
            for sr in showrooms:
                print(f"      - {sr.name} (ID: {sr.id})")
        
        # 5. التحقق من المستخدمين
        print("\n5️⃣  فحص المستخدمين...")
        warehouse_managers = User.query.filter_by(role='مسؤول مخزن', is_active=True).all()
        managers = User.query.filter_by(role='مدير', is_active=True).all()
        
        if not warehouse_managers and not managers:
            issues.append("❌ لا يوجد مستخدمين بصلاحية إضافة فواتير")
            print("   ❌ لا يوجد مستخدمين بصلاحية إضافة فواتير")
        else:
            print(f"   ✅ مدراء: {len(managers)}, مسؤولي مخزن: {len(warehouse_managers)}")
            success.append(f"✅ المستخدمين المصرح لهم: {len(managers) + len(warehouse_managers)}")
        
        # 6. عرض النتيجة النهائية
        print("\n" + "="*70)
        print("📊 ملخص التشخيص")
        print("="*70 + "\n")
        
        if issues:
            print("🚨 المشاكل الحرجة:")
            for issue in issues:
                print(f"   {issue}")
            print()
        
        if warnings:
            print("⚠️  تحذيرات:")
            for warning in warnings:
                print(f"   {warning}")
            print()
        
        if success:
            print("✅ ما يعمل بشكل صحيح:")
            for s in success:
                print(f"   {s}")
            print()
        
        # التوصيات
        print("="*70)
        print("💡 التوصيات")
        print("="*70 + "\n")
        
        if not warehouses:
            print("1. يجب إضافة مخزن واحد على الأقل:")
            print("   python add_default_warehouse.py")
            print()
        
        if materials and any(not m.warehouse_id for m in materials):
            print("2. يجب ربط المواد الموجودة بمخزن:")
            print("   python fix_materials_warehouse.py")
            print()
        
        if not suppliers:
            print("3. يجب إضافة مورد واحد على الأقل عبر الواجهة:")
            print("   /supplier/new")
            print()
        
        if not showrooms:
            print("4. يجب إضافة صالة واحدة على الأقل:")
            print("   /showroom/new")
            print()
        
        if issues:
            print("\n❌ لا يمكن إضافة فواتير حتى يتم حل المشاكل أعلاه\n")
            return False
        else:
            print("\n✅ النظام جاهز لإضافة فواتير الشراء!\n")
            return True

if __name__ == '__main__':
    diagnose()



