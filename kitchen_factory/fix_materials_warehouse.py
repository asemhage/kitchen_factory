"""
سكريبت لربط المواد الموجودة بالمخزن الافتراضي
"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from app import app, db, Material, Warehouse

def fix_materials():
    with app.app_context():
        # الحصول على المخزن الافتراضي
        warehouse = Warehouse.query.filter_by(is_default=True).first()
        
        if not warehouse:
            print("❌ لا يوجد مخزن افتراضي. قم بتشغيل add_default_warehouse.py أولاً")
            return
        
        # الحصول على المواد غير المرتبطة بمخزن
        materials_without_warehouse = Material.query.filter(
            Material.warehouse_id.is_(None)
        ).all()
        
        if not materials_without_warehouse:
            print("✅ جميع المواد مرتبطة بمخازن بالفعل")
            return
        
        print(f"🔧 سيتم ربط {len(materials_without_warehouse)} مادة بالمخزن الافتراضي: {warehouse.name}")
        
        for material in materials_without_warehouse:
            material.warehouse_id = warehouse.id
            print(f"   ✓ {material.name}")
        
        db.session.commit()
        
        print(f"\n✅ تم ربط {len(materials_without_warehouse)} مادة بالمخزن الافتراضي بنجاح!")

if __name__ == '__main__':
    fix_materials()



