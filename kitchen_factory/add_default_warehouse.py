"""
سكريبت لإضافة مخزن افتراضي
"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from app import app, db, Warehouse
from datetime import datetime, timezone

def add_warehouse():
    with app.app_context():
        # التحقق من وجود مخزن افتراضي
        existing = Warehouse.query.filter_by(is_default=True).first()
        if existing:
            print(f"✅ يوجد مخزن افتراضي بالفعل: {existing.name}")
            return
        
        # إنشاء مخزن افتراضي
        warehouse = Warehouse(
            name='المخزن الرئيسي',
            code='MAIN-WH',
            location='المصنع الرئيسي',
            description='المخزن الرئيسي للمصنع - مخزن موحد لجميع الصالات',
            is_active=True,
            is_default=True,
            created_at=datetime.now(timezone.utc),
            created_by='system'
        )
        
        db.session.add(warehouse)
        db.session.commit()
        
        print(f"✅ تم إضافة المخزن الافتراضي: {warehouse.name} (ID: {warehouse.id})")

if __name__ == '__main__':
    add_warehouse()



