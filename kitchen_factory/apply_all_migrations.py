#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
سكريبت تطبيق جميع التغييرات
التاريخ: 2025-10-14
الوصف: هذا السكريبت يقوم بتنفيذ جميع تحديثات المراحل، الأرشفة، ونظام الفنيين
"""

import os
import sys
import sqlite3
import importlib.util
import traceback
from datetime import datetime

def create_backup(db_path):
    """إنشاء نسخة احتياطية من قاعدة البيانات"""
    try:
        backup_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = f"{db_path}.backup_{backup_timestamp}"
        
        if os.path.exists(db_path):
            import shutil
            shutil.copy2(db_path, backup_path)
            print(f"✅ تم إنشاء نسخة احتياطية: {backup_path}")
            return True, backup_path
        else:
            print(f"❌ قاعدة البيانات غير موجودة: {db_path}")
            return False, None
    except Exception as e:
        print(f"❌ فشل إنشاء النسخة الاحتياطية: {str(e)}")
        return False, None

def import_and_run(script_path, script_name):
    """استيراد وتشغيل سكريبت خارجي"""
    try:
        # استيراد السكريبت
        spec = importlib.util.spec_from_file_location(script_name, script_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        
        # تنفيذ الدالة الرئيسية في السكريبت
        if hasattr(module, script_name):
            print(f"🔄 تنفيذ {script_name}...")
            result = getattr(module, script_name)()
            return result
        else:
            print(f"❌ لم يتم العثور على الدالة الرئيسية في {script_name}")
            return False
    except Exception as e:
        print(f"❌ فشل تنفيذ {script_name}: {str(e)}")
        traceback.print_exc()
        return False

def apply_all_migrations():
    """تنفيذ جميع عمليات الترحيل"""
    
    print("=" * 70)
    print("🚀 بدء تطبيق جميع التحديثات")
    print("=" * 70)
    
    # إنشاء نسخة احتياطية
    db_path = 'instance/kitchen_factory.db'
    success, backup_path = create_backup(db_path)
    if not success:
        return False
    
    # قائمة السكريبتات التي سيتم تنفيذها بالترتيب
    scripts_to_run = [
        {"path": "migrate_production_stages.py", "name": "migrate_production_stages"},
        {"path": "create_technicians_tables.py", "name": "create_technicians_tables"}
    ]
    
    success_count = 0
    failure_count = 0
    
    for script in scripts_to_run:
        script_path = script["path"]
        script_name = script["name"]
        
        print("\n" + "-" * 50)
        print(f"🔄 جاري تنفيذ {script_path}...")
        
        if import_and_run(script_path, script_name):
            success_count += 1
            print(f"✅ اكتمل تنفيذ {script_path} بنجاح!")
        else:
            failure_count += 1
            print(f"❌ فشل تنفيذ {script_path}")
    
    print("\n" + "=" * 70)
    print(f"📊 تقرير التنفيذ: {success_count} نجاح، {failure_count} فشل من أصل {len(scripts_to_run)}")
    print("=" * 70)
    
    if failure_count > 0:
        print(f"\n⚠️ فشلت بعض العمليات. يمكنك استعادة النسخة الاحتياطية من: {backup_path}")
        return False
    else:
        print("\n✅ تم تطبيق جميع التحديثات بنجاح!")
        return True

if __name__ == "__main__":
    print("\n🔄 سكريبت تطبيق جميع التحديثات")
    print("   التاريخ: 2025-10-14\n")
    
    # تأكيد من المستخدم
    if len(sys.argv) > 1 and sys.argv[1] == "--force":
        apply_all_migrations()
    else:
        response = input("⚠️ سيقوم هذا السكريبت بتطبيق جميع التحديثات. هل تريد المتابعة؟ (yes/no): ")
        if response.lower() in ["yes", "y", "نعم"]:
            success = apply_all_migrations()
            if not success:
                print("\n❌ فشلت عملية التحديث!")
                sys.exit(1)
        else:
            print("\n❌ تم إلغاء العملية")
            sys.exit(0)
