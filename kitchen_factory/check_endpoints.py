#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
سكريبت فحص endpoints - التحقق من جميع نقاط النهاية المطلوبة في templates
تاريخ: 2025-10-19
"""

import re
import os
from pathlib import Path

def extract_endpoints_from_templates():
    """استخراج جميع endpoints من templates"""
    templates_dir = Path('templates')
    endpoints = set()
    
    # نمط البحث عن url_for
    pattern = r"url_for\(['\"]([^'\"]+)['\"]"
    
    for template_file in templates_dir.rglob('*.html'):
        try:
            with open(template_file, 'r', encoding='utf-8') as f:
                content = f.read()
                matches = re.findall(pattern, content)
                for match in matches:
                    endpoints.add(match)
        except Exception as e:
            print(f"⚠️  خطأ في قراءة {template_file}: {e}")
    
    return sorted(endpoints)

def extract_routes_from_app():
    """استخراج جميع routes من app.py"""
    routes = set()
    
    # نمط البحث عن @app.route
    pattern = r"def\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*\("
    
    try:
        with open('app.py', 'r', encoding='utf-8') as f:
            content = f.read()
            matches = re.findall(pattern, content)
            for match in matches:
                routes.add(match)
    except Exception as e:
        print(f"❌ خطأ في قراءة app.py: {e}")
    
    return sorted(routes)

def check_endpoints():
    """فحص endpoints والتحقق من التطابق"""
    print("🔍 فحص endpoints في النظام...\n")
    print("=" * 80)
    
    # استخراج البيانات
    print("📋 استخراج endpoints من templates...")
    template_endpoints = extract_endpoints_from_templates()
    print(f"   ✅ تم العثور على {len(template_endpoints)} endpoint في templates\n")
    
    print("📋 استخراج routes من app.py...")
    app_routes = extract_routes_from_app()
    print(f"   ✅ تم العثور على {len(app_routes)} route في app.py\n")
    
    # التحليل
    print("=" * 80)
    print("📊 تحليل النتائج:\n")
    
    # Endpoints مفقودة
    missing_endpoints = [ep for ep in template_endpoints if ep not in app_routes]
    
    # Endpoints موجودة
    existing_endpoints = [ep for ep in template_endpoints if ep in app_routes]
    
    # عرض النتائج
    if missing_endpoints:
        print(f"❌ Endpoints مفقودة ({len(missing_endpoints)}):")
        print("-" * 80)
        for i, endpoint in enumerate(missing_endpoints, 1):
            print(f"   {i}. {endpoint}")
        print()
    else:
        print("✅ جميع endpoints موجودة!\n")
    
    print(f"✅ Endpoints موجودة ({len(existing_endpoints)}):")
    print("-" * 80)
    
    # تجميع حسب الفئة
    categories = {
        'نظام الموردين': [],
        'نظام الطلبات': [],
        'نظام المواد': [],
        'نظام الصالات': [],
        'نظام المستخدمين': [],
        'التقارير': [],
        'النظام العام': []
    }
    
    for endpoint in existing_endpoints:
        if any(x in endpoint for x in ['supplier', 'invoice', 'payment']):
            categories['نظام الموردين'].append(endpoint)
        elif any(x in endpoint for x in ['order', 'stage', 'cost']):
            categories['نظام الطلبات'].append(endpoint)
        elif any(x in endpoint for x in ['material', 'pricing']):
            categories['نظام المواد'].append(endpoint)
        elif 'showroom' in endpoint:
            categories['نظام الصالات'].append(endpoint)
        elif any(x in endpoint for x in ['user', 'login', 'logout']):
            categories['نظام المستخدمين'].append(endpoint)
        elif 'report' in endpoint or endpoint.endswith('_list'):
            categories['التقارير'].append(endpoint)
        else:
            categories['النظام العام'].append(endpoint)
    
    for category, endpoints in categories.items():
        if endpoints:
            print(f"\n📌 {category} ({len(endpoints)}):")
            for endpoint in endpoints:
                print(f"   • {endpoint}")
    
    # ملخص نهائي
    print("\n" + "=" * 80)
    print("📈 الملخص النهائي:")
    print("=" * 80)
    print(f"   • إجمالي endpoints في templates: {len(template_endpoints)}")
    print(f"   • endpoints موجودة في app.py: {len(existing_endpoints)}")
    print(f"   • endpoints مفقودة: {len(missing_endpoints)}")
    
    if missing_endpoints:
        print(f"\n   ⚠️  نسبة التطابق: {(len(existing_endpoints)/len(template_endpoints)*100):.1f}%")
        print(f"   ❌ يوجد {len(missing_endpoints)} endpoint مفقود!")
    else:
        print(f"\n   ✅ نسبة التطابق: 100%")
        print("   ✅ جميع endpoints موجودة ومتطابقة!")
    
    print("=" * 80)
    
    return len(missing_endpoints) == 0

if __name__ == '__main__':
    os.chdir(os.path.dirname(__file__))
    success = check_endpoints()
    exit(0 if success else 1)

