"""
Migration: إنشاء OrderCost لجميع OrderMaterial الموجودة
التاريخ: 2025-10-16
الهدف: ربط تكاليف المواد الحالية مع OrderCost
"""

from app import app, db, OrderMaterial, OrderCost
from datetime import datetime

def migrate_create_material_costs():
    """إنشاء OrderCost لجميع OrderMaterial التي ليس لها OrderCost مرتبط"""
    
    with app.app_context():
        print("🚀 بدء migration: إنشاء OrderCost للمواد الحالية...")
        print("=" * 60)
        
        # 1. جلب جميع OrderMaterial
        all_order_materials = OrderMaterial.query.all()
        total_count = len(all_order_materials)
        
        print(f"📊 إجمالي OrderMaterial: {total_count}")
        
        created_count = 0
        skipped_count = 0
        error_count = 0
        
        for om in all_order_materials:
            try:
                # التحقق: هل يوجد OrderCost مرتبط؟
                existing_cost = OrderCost.query.filter_by(
                    order_material_id=om.id
                ).first()
                
                if existing_cost:
                    skipped_count += 1
                    print(f"⏭️  تخطي OrderMaterial#{om.id} - OrderCost موجود مسبقاً")
                    continue
                
                # التحقق من وجود المادة والطلب
                if not om.material or not om.order:
                    error_count += 1
                    print(f"❌ خطأ OrderMaterial#{om.id} - مادة أو طلب مفقود")
                    continue
                
                # إنشاء OrderCost جديد
                order_cost = OrderCost(
                    order_id=om.order_id,
                    cost_type='مواد',
                    description=f'تكلفة مادة: {om.material.name} ({om.quantity_needed} {om.material.unit})',
                    amount=om.total_cost or 0,
                    order_material_id=om.id,
                    date=om.added_at.date() if om.added_at else datetime.now().date(),
                    showroom_id=om.showroom_id
                )
                db.session.add(order_cost)
                created_count += 1
                
                print(f"✅ أُنشئ OrderCost لـ OrderMaterial#{om.id} - {om.material.name}")
                
                # حفظ كل 50 سجل
                if created_count % 50 == 0:
                    db.session.commit()
                    print(f"💾 حُفظ {created_count} سجل...")
                    
            except Exception as e:
                error_count += 1
                print(f"❌ خطأ في OrderMaterial#{om.id}: {str(e)}")
                continue
        
        # حفظ البقية
        db.session.commit()
        
        print("=" * 60)
        print(f"✅ تم إنشاء {created_count} سجل OrderCost جديد")
        print(f"⏭️  تم تخطي {skipped_count} سجل موجود مسبقاً")
        print(f"❌ حدثت {error_count} أخطاء")
        print(f"📊 الإجمالي: {created_count + skipped_count + error_count} من {total_count}")
        print("=" * 60)
        
        # التحقق النهائي
        print("\n🔍 التحقق النهائي:")
        total_order_costs = OrderCost.query.filter_by(cost_type='مواد').count()
        print(f"📊 إجمالي OrderCost من نوع 'مواد': {total_order_costs}")
        
        linked_costs = OrderCost.query.filter(OrderCost.order_material_id.isnot(None)).count()
        print(f"🔗 OrderCost المربوطة بـ OrderMaterial: {linked_costs}")
        
        print("\n✅ انتهى Migration بنجاح!")

if __name__ == '__main__':
    migrate_create_material_costs()

