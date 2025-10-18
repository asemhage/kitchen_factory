"""
سكربت إصلاح نظام الصالات
يقوم بإنشاء جدول showrooms والبيانات الأولية
"""

from app import app, db, Showroom, User
from werkzeug.security import generate_password_hash
from datetime import datetime, timezone
import sys

def fix_showroom_system():
    """إصلاح نظام الصالات بالكامل"""
    
    print("\n" + "="*70)
    print("🔧 سكربت إصلاح نظام الصالات")
    print("="*70 + "\n")
    
    try:
        with app.app_context():
            # 1. إنشاء جميع الجداول
            print("📊 الخطوة 1: إنشاء جميع الجداول...")
            db.create_all()
            print("   ✅ تم إنشاء الجداول بنجاح\n")
            
            # 2. التحقق من وجود صالات
            print("📋 الخطوة 2: التحقق من الصالات الموجودة...")
            existing_showrooms = Showroom.query.all()
            
            if existing_showrooms:
                print(f"   ✅ وُجدت {len(existing_showrooms)} صالة موجودة:")
                for s in existing_showrooms:
                    status = "نشطة" if s.is_active else "معطلة"
                    print(f"      - {s.name} ({s.code}) - {status}")
                print()
            else:
                print("   ⚠️  لا توجد صالات، سيتم إنشاء صالة افتراضية...\n")
                
                # 3. إنشاء صالة افتراضية
                print("🏪 الخطوة 3: إنشاء صالة افتراضية...")
                default_showroom = Showroom(
                    name='الصالة الرئيسية',
                    code='MAIN',
                    address='العنوان الافتراضي',
                    phone='0912345678',
                    manager_name='المدير العام',
                    is_active=True,
                    created_at=datetime.now(timezone.utc)
                )
                db.session.add(default_showroom)
                db.session.commit()
                print("   ✅ تم إنشاء الصالة الافتراضية (ID: 1)\n")
            
            # 4. التحقق من المستخدمين
            print("👥 الخطوة 4: التحقق من المستخدمين...")
            admin_user = User.query.filter_by(username='admin').first()
            
            if admin_user:
                print(f"   ✅ المستخدم admin موجود (Role: {admin_user.role})")
                
                # تحديث showroom_id للمستخدمين الموجودين
                users_without_showroom = User.query.filter(
                    User.showroom_id.is_(None),
                    User.role != 'مدير'
                ).all()
                
                if users_without_showroom:
                    print(f"   ⚠️  {len(users_without_showroom)} مستخدم بدون صالة، سيتم تحديثهم...")
                    default_showroom = Showroom.query.first()
                    for user in users_without_showroom:
                        user.showroom_id = default_showroom.id
                    db.session.commit()
                    print("   ✅ تم تحديث المستخدمين\n")
            else:
                print("   ⚠️  المستخدم admin غير موجود، سيتم إنشاؤه...")
                admin = User(
                    username='admin',
                    password=generate_password_hash('admin123'),
                    role='مدير',
                    showroom_id=None,  # المديرون لا يرتبطون بصالة محددة
                    is_active=True,
                    last_login=None
                )
                db.session.add(admin)
                db.session.commit()
                print("   ✅ تم إنشاء المستخدم admin")
                print("   📝 Username: admin")
                print("   📝 Password: admin123\n")
            
            # 5. إحصائيات نهائية
            print("📊 الخطوة 5: الإحصائيات النهائية...")
            total_showrooms = Showroom.query.count()
            active_showrooms = Showroom.query.filter_by(is_active=True).count()
            total_users = User.query.filter_by(is_active=True).count()
            
            print(f"   ✅ إجمالي الصالات: {total_showrooms}")
            print(f"   ✅ الصالات النشطة: {active_showrooms}")
            print(f"   ✅ إجمالي المستخدمين النشطين: {total_users}\n")
            
            print("="*70)
            print("✅ تم إصلاح نظام الصالات بنجاح!")
            print("="*70)
            print("\n🚀 يمكنك الآن تشغيل التطبيق:")
            print("   python app.py")
            print("\n🔗 ثم زيارة:")
            print("   http://127.0.0.1:5000/showrooms\n")
            
            return True
            
    except Exception as e:
        print(f"\n❌ حدث خطأ: {str(e)}")
        print(f"📝 التفاصيل: {type(e).__name__}")
        db.session.rollback()
        return False

if __name__ == '__main__':
    success = fix_showroom_system()
    sys.exit(0 if success else 1)

