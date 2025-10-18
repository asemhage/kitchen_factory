"""
سكريبت توليد بيانات تجريبية شاملة
يولد 20 طلبية مع جميع البيانات المرتبطة:
- طلبيات بحالات متنوعة
- عملاء
- مواد الطلبيات والاستهلاك
- فواتير الشراء والدفعات
- مراحل الإنتاج
- الفنيين والمستحقات
"""

import random
from datetime import datetime, timedelta, timezone
from app import app, db, Order, Customer, OrderMaterial, Material, Stage
from app import PurchaseInvoice, PurchaseInvoiceItem, SupplierPayment, Supplier
from app import Payment, Technician, TechnicianDue, Showroom, User, Warehouse

def generate_random_date(start_days_ago=180, end_days_ago=0):
    """توليد تاريخ عشوائي"""
    days_ago = random.randint(end_days_ago, start_days_ago)
    return datetime.now(timezone.utc) - timedelta(days=days_ago)

def create_sample_data():
    """إنشاء البيانات التجريبية"""
    
    print("🚀 بدء توليد البيانات التجريبية...")
    
    with app.app_context():
        # 1. التحقق من وجود البيانات الأساسية
        print("\n📋 التحقق من البيانات الأساسية...")
        
        showroom = Showroom.query.first()
        if not showroom:
            print("❌ لا توجد صالات! الرجاء إضافة صالة أولاً.")
            return
        
        warehouse = Warehouse.query.first()
        if not warehouse:
            print("❌ لا يوجد مخزن! الرجاء إضافة مخزن أولاً.")
            return
        
        user = User.query.filter_by(role='مدير').first()
        if not user:
            print("❌ لا يوجد مدير! الرجاء إضافة مستخدم مدير أولاً.")
            return
        
        # 2. إنشاء موردين إذا لم يكونوا موجودين
        print("\n👥 إنشاء الموردين...")
        suppliers = []
        supplier_names = [
            ('شركة الخشب المثالي', 'خشب وألواح'),
            ('مؤسسة الحديد والألمنيوم', 'حديد وألمنيوم'),
            ('معرض الإكسسوارات الحديثة', 'إكسسوارات ومفصلات'),
            ('شركة الدهانات المتقدمة', 'دهانات ومواد تشطيب')
        ]
        
        for idx, (name, notes_category) in enumerate(supplier_names, 1):
            supplier = Supplier.query.filter_by(name=name).first()
            if not supplier:
                supplier = Supplier(
                    name=name,
                    code=f"SUP{idx:03d}",
                    contact_person=f"مدير {name}",
                    phone=f"091{random.randint(1000000, 9999999)}",
                    email=f"supplier{idx}@example.com",
                    address='طرابلس، ليبيا',
                    payment_terms='30 يوم',
                    notes=f'تخصص: {notes_category}',
                    showroom_id=showroom.id,
                    is_active=True
                )
                db.session.add(supplier)
                suppliers.append(supplier)
                print(f"  ✅ تم إنشاء المورد: {name}")
            else:
                suppliers.append(supplier)
                print(f"  ℹ️  المورد موجود: {name}")
        
        db.session.commit()
        
        # 3. إنشاء مواد إذا لم تكن موجودة
        print("\n📦 إنشاء المواد...")
        materials = []
        material_data = [
            ('خشب MDF 18mm', 'متر مربع', 120.0, 150.0, supplier_names[0][0]),
            ('خشب MDF 16mm', 'متر مربع', 100.0, 130.0, supplier_names[0][0]),
            ('ألواح HPL', 'متر مربع', 250.0, 320.0, supplier_names[0][0]),
            ('مفصلات هيدروليك', 'قطعة', 15.0, 25.0, supplier_names[2][0]),
            ('سكك أدراج', 'زوج', 35.0, 50.0, supplier_names[2][0]),
            ('مقابض ألمنيوم', 'قطعة', 8.0, 15.0, supplier_names[2][0]),
            ('دهان لاكيه أبيض', 'لتر', 80.0, 110.0, supplier_names[3][0]),
            ('ألمنيوم بروفايل', 'متر', 45.0, 65.0, supplier_names[1][0]),
            ('زجاج شفاف 6mm', 'متر مربع', 180.0, 250.0, supplier_names[1][0]),
            ('سيليكون شفاف', 'أنبوب', 12.0, 20.0, supplier_names[3][0])
        ]
        
        for name, unit, cost, price, supplier_name in material_data:
            material = Material.query.filter_by(name=name).first()
            if not material:
                supplier = Supplier.query.filter_by(name=supplier_name).first()
                material = Material(
                    name=name,
                    unit=unit,
                    cost_price=cost,
                    purchase_price=cost,
                    selling_price=price,
                    unit_price=price,
                    quantity_available=random.randint(100, 500),
                    min_quantity=20,
                    warehouse_id=warehouse.id,
                    is_active=True
                )
                db.session.add(material)
                materials.append(material)
                print(f"  ✅ تم إنشاء المادة: {name}")
            else:
                materials.append(material)
                print(f"  ℹ️  المادة موجودة: {name}")
        
        db.session.commit()
        
        # 4. إنشاء فنيين
        print("\n👷 إنشاء الفنيين...")
        technicians = []
        technician_names = [
            ('محمد أحمد', 'تصنيع'),
            ('خالد علي', 'تركيب'),
            ('يوسف سالم', 'كلاهما'),
            ('عمر حسن', 'تصنيع'),
            ('أحمد محمود', 'تركيب')
        ]
        
        for name, spec in technician_names:
            tech = Technician.query.filter_by(name=name).first()
            if not tech:
                tech = Technician(
                    name=name,
                    phone=f"092{random.randint(1000000, 9999999)}",
                    national_id=f"{random.randint(100000000000, 999999999999)}",
                    specialization=spec,
                    manufacturing_rate_per_meter=random.randint(8, 15),
                    installation_rate_per_meter=random.randint(10, 18),
                    status='نشط',
                    hire_date=generate_random_date(365, 180).date()
                )
                db.session.add(tech)
                technicians.append(tech)
                print(f"  ✅ تم إنشاء الفني: {name}")
            else:
                technicians.append(tech)
                print(f"  ℹ️  الفني موجود: {name}")
        
        db.session.commit()
        
        # 5. إنشاء العملاء والطلبيات
        print("\n📝 إنشاء الطلبيات...")
        
        statuses = ['مفتوح', 'قيد التنفيذ', 'مكتمل', 'مسلّم', 'ملغي']
        status_weights = [2, 3, 4, 9, 2]  # أوزان للتوزيع الواقعي
        
        customer_names = [
            'أحمد محمد العبيدي', 'فاطمة سالم القذافي', 'يوسف خالد الزنتاني',
            'مريم علي الشريف', 'عمر حسن البوسيفي', 'نورة عبدالله المبروك',
            'سامي إبراهيم الترهوني', 'هدى محمود الفيتوري', 'طارق سعيد الكيلاني',
            'ليلى فرج المقريف', 'كريم عادل الشكشوكي', 'سعاد منصور الحصادي',
            'وليد جمعة المغربي', 'رانيا صالح العريبي', 'ماجد عثمان السنوسي',
            'سلمى فتحي الفاخري', 'ناصر يونس الزليطني', 'آمنة رمضان البرعصي',
            'زياد ماجد الورفلي', 'دلال حميد الغماري'
        ]
        
        for i in range(20):
            # إنشاء العميل
            customer_name = customer_names[i]
            customer = Customer.query.filter_by(name=customer_name).first()
            if not customer:
                customer = Customer(
                    name=customer_name,
                    phone=f"091{random.randint(1000000, 9999999)}",
                    address=random.choice(['طرابلس', 'بنغازي', 'مصراتة', 'الزاوية', 'صبراتة']),
                    email=f"customer{i+1}@example.com"
                )
                db.session.add(customer)
                db.session.flush()
            
            # إنشاء الطلبية
            status = random.choices(statuses, weights=status_weights)[0]
            order_date = generate_random_date(120, 10)
            
            # حساب التواريخ بناءً على الحالة
            if status == 'مفتوح':
                start_date = None
                end_date = None
                delivery_date = (order_date + timedelta(days=random.randint(30, 60))).date()
            elif status == 'قيد التنفيذ':
                start_date = (order_date + timedelta(days=random.randint(3, 10))).date()
                end_date = None
                delivery_date = (order_date + timedelta(days=random.randint(30, 60))).date()
            elif status in ['مكتمل', 'مسلّم']:
                start_date = (order_date + timedelta(days=random.randint(2, 7))).date()
                end_date = (order_date + timedelta(days=random.randint(20, 45))).date()
                delivery_date = end_date
            else:  # ملغي
                start_date = None
                end_date = None
                delivery_date = None
            
            order = Order(
                customer_id=customer.id,
                showroom_id=showroom.id,
                order_date=order_date.date(),
                delivery_date=delivery_date,
                deadline=(order_date + timedelta(days=random.randint(45, 75))).date(),
                meters=random.randint(8, 35),
                total_value=random.uniform(3000, 15000),
                status=status,
                start_date=start_date,
                end_date=end_date,
                received_by=user.username if status != 'ملغي' else None,
                is_archived=False
            )
            db.session.add(order)
            db.session.flush()
            
            print(f"  ✅ طلبية #{order.id}: {customer_name} - {status}")
            
            # إضافة مواد للطلبية (إذا لم تكن ملغاة)
            if status != 'ملغي':
                num_materials = random.randint(3, 7)
                selected_materials = random.sample(materials, min(num_materials, len(materials)))
                
                for material in selected_materials:
                    quantity = random.uniform(5, 50)
                    discount_percentage = random.choice([0, 5, 10, 15]) if random.random() > 0.7 else 0
                    
                    consumed = quantity if status in ['مكتمل', 'مسلّم'] else (quantity * 0.5 if status == 'قيد التنفيذ' else 0)
                    order_material = OrderMaterial(
                        order_id=order.id,
                        material_id=material.id,
                        quantity_needed=quantity,
                        quantity_consumed=consumed,
                        quantity_used=consumed,  # للتوافق مع الكود القديم
                        quantity_shortage=0 if consumed >= quantity else (quantity - consumed),
                        unit_price=material.selling_price,
                        unit_cost=material.selling_price,  # نفس unit_price
                        status='complete' if status in ['مكتمل', 'مسلّم'] else ('partial' if status == 'قيد التنفيذ' else 'pending'),
                        showroom_id=showroom.id
                    )
                    db.session.add(order_material)
            
            # إضافة مراحل (بالترتيب الصحيح)
            stages_list = ['تصميم', 'استلام العربون', 'حصر المتطلبات', 'التصنيع', 'التركيب', 'التسليم النهائي']
            
            for stage_name in stages_list:
                if status == 'مفتوح':
                    progress = 100 if stage_name == 'تصميم' else 0
                elif status == 'قيد التنفيذ':
                    if stage_name in ['تصميم', 'حصر المتطلبات', 'استلام العربون']:
                        progress = 100
                    elif stage_name == 'التصنيع':
                        progress = random.randint(30, 80)
                    else:
                        progress = 0
                elif status in ['مكتمل', 'مسلّم']:
                    progress = 100
                else:  # ملغي
                    progress = 0
                
                stage = Stage(
                    order_id=order.id,
                    stage_name=stage_name,
                    progress=progress,
                    notes=f"{stage_name} - {progress}%",
                    order_meters=order.meters if stage_name in ['التصنيع', 'التركيب'] else None,
                    showroom_id=showroom.id
                )
                
                # إضافة فني للمراحل المكتملة
                if progress == 100 and stage_name in ['التصنيع', 'التركيب'] and technicians:
                    tech = random.choice([t for t in technicians if stage_name in t.specialization or t.specialization == 'كلاهما'])
                    if stage_name == 'التصنيع':
                        stage.manufacturing_technician_id = tech.id
                        stage.manufacturing_start_date = start_date
                        stage.manufacturing_end_date = end_date
                    else:
                        stage.installation_technician_id = tech.id
                        stage.installation_start_date = end_date
                        stage.installation_end_date = (datetime.strptime(str(end_date), '%Y-%m-%d') + timedelta(days=2)).date() if end_date else None
                
                db.session.add(stage)
            
            # إضافة دفعات للطلبيات المكتملة/المسلمة
            if status in ['مكتمل', 'مسلّم', 'قيد التنفيذ']:
                total = order.total_value
                # عربون
                deposit = total * random.uniform(0.2, 0.3)
                payment1 = Payment(
                    order_id=order.id,
                    amount=deposit,
                    payment_type='عربون',
                    payment_date=(order_date + timedelta(days=1)).date(),
                    payment_method='نقد',
                    received_by=user.username,
                    notes='عربون',
                    showroom_id=showroom.id
                )
                db.session.add(payment1)
                
                # دفعات إضافية للمكتملة
                if status in ['مكتمل', 'مسلّم']:
                    remaining = total - deposit
                    num_payments = random.randint(1, 3)
                    for j in range(num_payments):
                        amount = remaining / num_payments if j < num_payments - 1 else remaining - sum([remaining / num_payments] * (num_payments - 1))
                        payment = Payment(
                            order_id=order.id,
                            amount=amount,
                            payment_type='دفعة' if j < num_payments - 1 else 'باقي المبلغ',
                            payment_date=(datetime.strptime(str(delivery_date), '%Y-%m-%d') - timedelta(days=random.randint(1, 5))).date() if delivery_date else order_date.date(),
                            payment_method=random.choice(['نقد', 'بنك', 'شيك']),
                            received_by=user.username,
                            notes=f'دفعة {j+2}',
                            showroom_id=showroom.id
                        )
                        db.session.add(payment)
        
        db.session.commit()
        
        # 6. إنشاء فواتير شراء
        print("\n🧾 إنشاء فواتير الشراء...")
        
        for i in range(15):
            supplier = random.choice(suppliers)
            invoice_date = generate_random_date(90, 10)
            
            invoice = PurchaseInvoice(
                invoice_number=f"INV-{random.randint(1000, 9999)}",
                supplier_id=supplier.id,
                invoice_date=invoice_date.date(),
                due_date=(invoice_date + timedelta(days=30)).date(),
                total_amount=0,
                status='open',
                notes=f'فاتورة شراء {i+1}',
                showroom_id=showroom.id
            )
            db.session.add(invoice)
            db.session.flush()
            
            # إضافة مواد للفاتورة
            num_items = random.randint(2, 5)
            selected_materials = random.sample(materials, min(num_items, len(materials)))
            
            total = 0
            for material in selected_materials:
                quantity = random.uniform(10, 100)
                price = material.cost_price * random.uniform(0.9, 1.1)
                subtotal = quantity * price
                total += subtotal
                
                item = PurchaseInvoiceItem(
                    invoice_id=invoice.id,
                    material_id=material.id,
                    quantity=quantity,
                    purchase_price=price,
                    discount_percent=0
                )
                db.session.add(item)
            
            invoice.total_amount = total
            invoice.final_amount = total  # نفس القيمة بدون خصومات/ضرائب
            
            # إضافة دفعات
            if random.random() > 0.3:
                paid = total * random.uniform(0.3, 1.0)
                invoice.status = 'paid' if paid >= total else 'partial'
                
                payment = SupplierPayment(
                    invoice_id=invoice.id,
                    supplier_id=supplier.id,
                    amount=paid,
                    payment_date=(invoice_date + timedelta(days=random.randint(1, 20))).date(),
                    payment_method=random.choice(['نقد', 'بنك', 'شيك']),
                    paid_by=user.username,
                    notes='دفعة'
                )
                db.session.add(payment)
            
            print(f"  ✅ فاتورة #{invoice.id}: {supplier.name} - {total:.2f} د.ل")
        
        db.session.commit()
        
        print("\n✅ تم توليد البيانات بنجاح!")
        print(f"\n📊 الإحصائيات:")
        print(f"  - الطلبيات: {Order.query.count()}")
        print(f"  - العملاء: {Customer.query.count()}")
        print(f"  - المواد: {Material.query.count()}")
        print(f"  - الفنيين: {Technician.query.count()}")
        print(f"  - فواتير الشراء: {PurchaseInvoice.query.count()}")
        print(f"  - الموردين: {Supplier.query.count()}")

if __name__ == '__main__':
    try:
        create_sample_data()
        print("\n🎉 العملية اكتملت بنجاح!")
    except Exception as e:
        print(f"\n❌ خطأ: {str(e)}")
        import traceback
        traceback.print_exc()

