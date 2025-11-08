#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Migration: إضافة حقول مصدر التسعير وبيانات المستحقات
التاريخ: 2025-11-08
الوصف: إضافة rate_source إلى جدول stage، و pricing_notes / calculated_at إلى جدول technician_dues
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app, db
from sqlalchemy import text


def migrate_add_technician_pricing_metadata():
    """إضافة الحقول الجديدة مع الحفاظ على التوافق"""
    with app.app_context():
        print("=" * 70)
        print("🚀 بدء Migration: تحديث حقول التسعير للفنيين والمراحل")
        print("=" * 70)

        try:
            # تحديث جدول stage
            stage_columns = [
                row[1] for row in db.session.execute(text("PRAGMA table_info(stage)")).fetchall()
            ]
            if 'rate_source' not in stage_columns:
                print("\n📝 إضافة الحقل rate_source إلى جدول stage...")
                db.session.execute(text("ALTER TABLE stage ADD COLUMN rate_source VARCHAR(30)"))
                print("✅ تمت إضافة rate_source")
            else:
                print("\n⏭️  الحقل rate_source موجود مسبقاً")

            # تحديث جدول technician_dues
            dues_columns = [
                row[1] for row in db.session.execute(text("PRAGMA table_info(technician_dues)")).fetchall()
            ]

            if 'pricing_notes' not in dues_columns:
                print("\n📝 إضافة الحقل pricing_notes إلى جدول technician_dues...")
                db.session.execute(text("ALTER TABLE technician_dues ADD COLUMN pricing_notes TEXT"))
                print("✅ تمت إضافة pricing_notes")
            else:
                print("\n⏭️  الحقل pricing_notes موجود مسبقاً")

            if 'calculated_at' not in dues_columns:
                print("\n📝 إضافة الحقل calculated_at إلى جدول technician_dues...")
                db.session.execute(text("ALTER TABLE technician_dues ADD COLUMN calculated_at DATETIME"))
                print("✅ تمت إضافة calculated_at")
            else:
                print("\n⏭️  الحقل calculated_at موجود مسبقاً")

            db.session.commit()

            print("\n" + "=" * 70)
            print("✅ انتهى Migration بنجاح!")
            print("=" * 70)

        except Exception as exc:
            db.session.rollback()
            print(f"\n❌ حدث خطأ أثناء تنفيذ migration: {exc}")
            raise


if __name__ == '__main__':
    migrate_add_technician_pricing_metadata()

