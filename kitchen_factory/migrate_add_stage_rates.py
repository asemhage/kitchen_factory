#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Migration: إضافة حقول أسعار الفنيين إلى جدول Stage
التاريخ: 2025-10-18
الوصف: إضافة manufacturing_rate و installation_rate لتخزين أسعار المتر قابلة للتعديل
"""

import sys
import os

# إضافة المسار الحالي إلى sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app, db
from sqlalchemy import text

def migrate_add_stage_rates():
    """إضافة حقول الأسعار إلى جدول stages"""
    
    with app.app_context():
        print("=" * 60)
        print("🚀 بدء migration: إضافة أسعار الفنيين إلى جدول Stage")
        print("=" * 60)
        
        try:
            # التحقق من وجود الحقول
            result = db.session.execute(text("PRAGMA table_info(stage)"))
            columns = [row[1] for row in result.fetchall()]
            
            # إضافة manufacturing_rate إذا لم يكن موجوداً
            if 'manufacturing_rate' not in columns:
                print("\n📝 إضافة حقل manufacturing_rate...")
                db.session.execute(text(
                    "ALTER TABLE stage ADD COLUMN manufacturing_rate FLOAT"
                ))
                print("✅ تمت إضافة manufacturing_rate")
            else:
                print("\n⏭️  manufacturing_rate موجود بالفعل")
            
            # إضافة installation_rate إذا لم يكن موجوداً
            if 'installation_rate' not in columns:
                print("\n📝 إضافة حقل installation_rate...")
                db.session.execute(text(
                    "ALTER TABLE stage ADD COLUMN installation_rate FLOAT"
                ))
                print("✅ تمت إضافة installation_rate")
            else:
                print("\n⏭️  installation_rate موجود بالفعل")
            
            db.session.commit()
            
            print("\n" + "=" * 60)
            print("✅ انتهى Migration بنجاح!")
            print("=" * 60)
            
        except Exception as e:
            db.session.rollback()
            print(f"\n❌ خطأ: {str(e)}")
            raise

if __name__ == '__main__':
    migrate_add_stage_rates()

