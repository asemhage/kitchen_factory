# هيكل قاعدة البيانات - نظام إدارة مصنع المطابخ

## نظرة عامة
هذا النظام يستخدم SQLite كقاعدة بيانات مع Flask-SQLAlchemy كـ ORM. قاعدة البيانات تحتوي على **21 جدول رئيسي** تدعم إدارة الطلبات، المواد، المستخدمين، المدفوعات، الموردين، المخازن، إدارة الفنيين والمستحقات، ونظام أرشفة الطلبيات.

---

## 1. جدول الصالات (Showroom)

### الوظيفة
إدارة الصالات المختلفة وفصل البيانات والصلاحيات بينها

### الحقول
| اسم الحقل | النوع | وصف | ملاحظات |
|-----------|-------|------|---------|
| `id` | Integer | المعرف الفريد | Primary Key |
| `name` | String(100) | اسم الصالة | Unique, Not Null |
| `code` | String(20) | كود الصالة | Unique |
| `address` | String(200) | العنوان | Nullable |
| `phone` | String(20) | رقم الهاتف | Nullable |
| `manager_name` | String(100) | اسم المدير | Nullable |
| `notes` | Text | ملاحظات | Nullable |
| `is_active` | Boolean | حالة التفعيل | Default: True |
| `deleted_at` | DateTime | تاريخ الحذف (Soft Delete) | Nullable |
| `deleted_by` | String(100) | من قام بالحذف | Nullable |
| `created_at` | DateTime | تاريخ الإنشاء | Default: utcnow |
| `updated_at` | DateTime | تاريخ التحديث | Auto-update |

### العلاقات
- **One-to-Many** مع `User`: صالة واحدة لها عدة مستخدمين
- **One-to-Many** مع `Order`: صالة واحدة لها عدة طلبات

---

## 2. جدول المستخدمين (User)

### الوظيفة
إدارة حسابات المستخدمين وصلاحياتهم في النظام

### الحقول
| اسم الحقل | النوع | وصف | ملاحظات |
|-----------|-------|------|---------|
| `id` | Integer | المعرف الفريد | Primary Key |
| `username` | String(100) | اسم المستخدم | Unique, Not Null |
| `password` | String(200) | كلمة المرور المشفرة | Not Null |
| `role` | String(50) | دور المستخدم | مدير، موظف استقبال، مسؤول مخزن، مسؤول إنتاج، مسؤول العمليات |
| `showroom_id` | Integer | معرف الصالة | Foreign Key → Showroom.id, Nullable للمديرين |
| `is_active` | Boolean | حالة التفعيل | Default: True |
| `last_login` | DateTime | آخر تسجيل دخول | Nullable |

### العلاقات
- **Many-to-One** مع `Showroom`: مستخدم واحد ينتمي لصالة واحدة (أو NULL للمديرين)

### ملاحظات
- المديرون (`showroom_id = NULL`) يمكنهم الوصول لجميع الصالات
- باقي الموظفين مرتبطون بصالة واحدة فقط

---

## 3. جدول العملاء (Customer)

### الوظيفة
تخزين معلومات العملاء - **مشترك بين جميع الصالات**

### الحقول
| اسم الحقل | النوع | وصف | ملاحظات |
|-----------|-------|------|---------|
| `id` | Integer | المعرف الفريد | Primary Key |
| `name` | String(100) | اسم العميل | Not Null |
| `phone` | String(20) | رقم الهاتف | Nullable |
| `address` | String(200) | العنوان | Nullable |

### العلاقات
- **One-to-Many** مع `Order`: عميل واحد يمكن أن يكون له عدة طلبات (في صالات مختلفة)

### ملاحظات
- العميل **غير مرتبط بصالة محددة** - يمكنه الطلب من أي صالة
- الطلبات نفسها مرتبطة بالصالات

---

## 4. جدول الطلبات (Order)

### الوظيفة
الجدول الرئيسي لتخزين معلومات الطلبات ومراحل تنفيذها

**ملاحظة**: اسم الجدول في قاعدة البيانات هو `orders`

### الحقول
| اسم الحقل | النوع | وصف | ملاحظات |
|-----------|-------|------|---------|
| `id` | Integer | المعرف الفريد | Primary Key |
| `customer_id` | Integer | معرف العميل | Foreign Key → Customer.id |
| `order_date` | Date | تاريخ الطلب | Not Null, Default: اليوم |
| `delivery_date` | Date | تاريخ التسليم المتوقع | Nullable |
| `deadline` | Date | الموعد النهائي للتسليم | Nullable |
| `meters` | Integer | عدد الأمتار المطلوبة | Not Null |
| `total_value` | Float | قيمة الطلبية الإجمالية | Default: 0.0 |
| `status` | String(50) | حالة الطلب | مفتوح، قيد التنفيذ، مكتمل، مسلّم |
| `received_by` | String(100) | اسم الموظف المستلم للطلب | Nullable |
| `start_date` | Date | تاريخ بدء التنفيذ | Nullable |
| `end_date` | Date | تاريخ انتهاء التنفيذ | Nullable |
| `showroom_id` | Integer | معرف الصالة | Foreign Key → Showroom.id, Not Null |

### الخصائص المحسوبة (Properties)

#### خصائص الدفع والفواتير:
- `total_price`: مجموع التكاليف المسجلة (قديم - استخدم total_cost بدلاً منه)
- `total_paid`: مجموع المدفوعات
- `remaining_amount`: المبلغ المتبقي
- `payment_status`: حالة الدفع (غير محدد، غير مدفوع، مدفوع جزئياً، مدفوع بالكامل)

#### خصائص التكاليف والربح (محدثة 2025-10-16):
- `total_materials_cost`: تكلفة المواد الفعلية من OrderMaterial (مجموع total_cost)
- `total_additional_costs`: التكاليف الإضافية (عمالة، نقل، أخرى) من OrderCost
- `total_cost`: إجمالي التكاليف الفعلية للطلبية (مواد + إضافات)
- `profit`: الربح الصافي (total_value - total_cost)
- `profit_margin`: هامش الربح % (profit / total_value × 100)

#### خصائص المواد:
- `materials_summary`: ملخص شامل لحالة المواد (total, complete, partial, pending, has_shortage, total_shortage_value)
- `shortage_materials`: قائمة المواد الناقصة فقط
- `materials_ready`: هل جميع المواد جاهزة؟

### العلاقات
- **Many-to-One** مع `Customer`: طلب واحد ينتمي لعميل واحد
- **Many-to-One** مع `Showroom`: طلب واحد ينتمي لصالة واحدة
- **One-to-One** مع `ReceivedOrder`: طلب واحد له سجل استلام واحد
- **One-to-Many** مع `Stage`: طلب واحد له عدة مراحل
- **One-to-Many** مع `OrderCost`: طلب واحد له عدة تكاليف
- **One-to-Many** مع `Payment`: طلب واحد له عدة مدفوعات
- **One-to-Many** مع `Document`: طلب واحد له عدة ملفات
- **One-to-Many** مع `OrderMaterial`: طلب واحد له عدة مواد
- **One-to-Many** مع `MaterialConsumption`: طلب واحد له عدة استهلاكات

### الفهارس
- `idx_showroom_status`: على (showroom_id, status)
- `idx_showroom_date`: على (showroom_id, order_date)
- `idx_customer_showroom`: على (customer_id, showroom_id)

---

## 5. جدول المخازن (Warehouse)

### الوظيفة
إدارة أماكن التخزين المتعددة - **مخزن موحد لجميع الصالات**

### الحقول
| اسم الحقل | النوع | وصف | ملاحظات |
|-----------|-------|------|---------|
| `id` | Integer | المعرف الفريد | Primary Key |
| `name` | String(100) | اسم المخزن | Not Null |
| `code` | String(20) | كود المخزن الفريد | Unique |
| `location` | String(200) | الموقع/العنوان | Nullable |
| `description` | Text | وصف المخزن | Nullable |
| `capacity` | Float | السعة | Nullable |
| `manager_name` | String(100) | اسم مسؤول المخزن | Nullable |
| `phone` | String(20) | رقم الهاتف | Nullable |
| `notes` | Text | ملاحظات | Nullable |
| `is_active` | Boolean | حالة التفعيل | Default: True |
| `is_default` | Boolean | المخزن الافتراضي | Default: False |
| `created_at` | DateTime | تاريخ الإنشاء | Default: utcnow |
| `created_by` | String(100) | من أنشأه | Nullable |
| `updated_at` | DateTime | تاريخ التحديث | Auto-update |

### العلاقات
- **One-to-Many** مع `Material`: مخزن واحد يحتوي على عدة مواد

### ملاحظات
- المخازن **موحدة** وليست مرتبطة بصالة محددة
- جميع الصالات تستخدم نفس المخازن

---

## 6. جدول المواد (Material)

### الوظيفة
إدارة المواد الخام والمخزون المتاح مع نظام تسعير مرن

### الحقول
| اسم الحقل | النوع | وصف | ملاحظات |
|-----------|-------|------|---------|
| `id` | Integer | المعرف الفريد | Primary Key |
| `name` | String(100) | اسم المادة | Not Null |
| `unit` | String(50) | وحدة القياس | متر، قطعة، لتر، كيلو |
| `quantity_available` | Float | الكمية المتاحة في المخزون | Default: 0 |
| `unit_price` | Float | سعر الوحدة (للتوافق) | Default: 0 |
| `cost_price` | Float | سعر التكلفة (المحسوب) | Default: 0 |
| `purchase_price` | Float | آخر سعر شراء | Default: 0 |
| `selling_price` | Float | سعر البيع | Default: 0 |
| `cost_price_mode` | String(30) | سياسة التسعير | purchase_price_default, weighted_average, last_invoice |
| `allow_manual_price_edit` | Boolean | السماح بتعديل السعر يدوياً | Default: True |
| `price_locked` | Boolean | السعر مقفل (معدل يدوياً) | Default: False |
| `price_updated_at` | DateTime | تاريخ تحديث السعر | Default: utcnow |
| `price_updated_by` | String(100) | من قام بتحديث السعر | Nullable |
| `warehouse_id` | Integer | معرف المخزن | Foreign Key → Warehouse.id, Not Null |
| `storage_location` | String(100) | الموقع داخل المخزن | Nullable |
| `min_quantity` | Float | الحد الأدنى للتنبيه | Default: 0 |
| `max_quantity` | Float | الحد الأقصى | Nullable |
| `is_active` | Boolean | حالة التفعيل | Default: True |
| `deleted_at` | DateTime | تاريخ الحذف (Soft Delete) | Nullable |

### العلاقات
- **Many-to-One** مع `Warehouse`: مادة واحدة تنتمي لمخزن واحد
- **One-to-Many** مع `OrderMaterial`: مادة واحدة تستخدم في عدة طلبات
- **One-to-Many** مع `MaterialConsumption`: مادة واحدة لها عدة استهلاكات

### ملاحظات
- **المواد مرتبطة بالمخازن** وليس بالصالات
- نظام تسعير مرن مع 3 سياسات مختلفة

---

## 7. جدول الموردين (Supplier)

### الوظيفة
إدارة الموردين وتتبع معاملاتهم

### الحقول
| اسم الحقل | النوع | وصف | ملاحظات |
|-----------|-------|------|---------|
| `id` | Integer | المعرف الفريد | Primary Key |
| `name` | String(100) | اسم المورد | Not Null |
| `code` | String(20) | كود المورد الفريد | Unique |
| `phone` | String(20) | رقم الهاتف | Nullable |
| `email` | String(100) | البريد الإلكتروني | Nullable |
| `address` | String(200) | العنوان | Nullable |
| `tax_id` | String(50) | الرقم الضريبي | Nullable |
| `payment_terms` | String(100) | شروط الدفع | Nullable |
| `credit_limit` | Float | حد الائتمان | Default: 0 |
| `notes` | Text | ملاحظات | Nullable |
| `is_active` | Boolean | حالة التفعيل | Default: True |
| `showroom_id` | Integer | معرف الصالة | Foreign Key → Showroom.id |
| `created_at` | DateTime | تاريخ الإنشاء | Default: utcnow |
| `updated_at` | DateTime | تاريخ التحديث | Auto-update |
| `created_by` | String(100) | من أنشأه | Nullable |

### الخصائص المحسوبة
- `total_debt`: إجمالي الديون المتبقية لهذا المورد

### العلاقات
- **Many-to-One** مع `Showroom`: مورد واحد مرتبط بصالة واحدة
- **One-to-Many** مع `PurchaseInvoice`: مورد واحد له عدة فواتير شراء
- **One-to-Many** مع `SupplierPayment`: مورد واحد له عدة دفعات

---

## 8. جدول فواتير الشراء (PurchaseInvoice)

### الوظيفة
تسجيل مشتريات المواد من الموردين

### الحقول
| اسم الحقل | النوع | وصف | ملاحظات |
|-----------|-------|------|---------|
| `id` | Integer | المعرف الفريد | Primary Key |
| `invoice_number` | String(50) | رقم الفاتورة | Unique, Not Null |
| `supplier_id` | Integer | معرف المورد | Foreign Key → Supplier.id, Not Null |
| `showroom_id` | Integer | معرف الصالة | Foreign Key → Showroom.id, Not Null |
| `invoice_date` | Date | تاريخ الفاتورة | Not Null, Default: اليوم |
| `due_date` | Date | تاريخ الاستحقاق | Nullable |
| `total_amount` | Float | إجمالي قبل الخصم والضريبة | Default: 0 |
| `discount_amount` | Float | قيمة الخصم | Default: 0 |
| `tax_amount` | Float | قيمة الضريبة | Default: 0 |
| `final_amount` | Float | المبلغ النهائي | Default: 0 |
| `status` | String(20) | حالة الفاتورة | open, partial, paid, overdue, cancelled |
| `notes` | Text | ملاحظات | Nullable |
| `is_active` | Boolean | حالة التفعيل | Default: True |
| `cancelled_at` | DateTime | تاريخ الإلغاء | Nullable |
| `cancelled_by` | String(100) | من قام بالإلغاء | Nullable |
| `cancellation_reason` | Text | سبب الإلغاء | Nullable |
| `created_at` | DateTime | تاريخ الإنشاء | Default: utcnow |
| `created_by` | String(100) | من أنشأها | Nullable |
| `updated_at` | DateTime | تاريخ التحديث | Auto-update |

### الخصائص المحسوبة
- `paid_amount`: المبلغ المدفوع (محسوب من الدفعات)
- `remaining_amount`: المبلغ المتبقي

### العلاقات
- **Many-to-One** مع `Supplier`: فاتورة واحدة تنتمي لمورد واحد
- **Many-to-One** مع `Showroom`: فاتورة واحدة تنتمي لصالة واحدة
- **One-to-Many** مع `PurchaseInvoiceItem`: فاتورة واحدة لها عدة عناصر
- **One-to-Many** مع `SupplierPayment`: فاتورة واحدة لها عدة دفعات

### الفهارس
- `idx_supplier_showroom`: على (supplier_id, showroom_id)
- `idx_invoice_date`: على (invoice_date)
- `idx_invoice_status`: على (status)

---

## 9. جدول عناصر فاتورة الشراء (PurchaseInvoiceItem)

### الوظيفة
تفاصيل المواد المشتراة في كل فاتورة

### الحقول
| اسم الحقل | النوع | وصف | ملاحظات |
|-----------|-------|------|---------|
| `id` | Integer | المعرف الفريد | Primary Key |
| `invoice_id` | Integer | معرف الفاتورة | Foreign Key → PurchaseInvoice.id, Not Null |
| `material_id` | Integer | معرف المادة | Foreign Key → Material.id, Not Null |
| `quantity` | Float | الكمية | Not Null |
| `purchase_price` | Float | سعر الشراء للوحدة | Not Null |
| `discount_percent` | Float | نسبة الخصم | Default: 0 |
| `discount_amount` | Float | قيمة الخصم | Default: 0 |
| `notes` | String(200) | ملاحظات | Nullable |

### الخصائص المحسوبة
- `line_total`: إجمالي السطر (الكمية × السعر - الخصم)

### العلاقات
- **Many-to-One** مع `PurchaseInvoice`: عنصر واحد ينتمي لفاتورة واحدة
- **Many-to-One** مع `Material`: عنصر واحد مرتبط بمادة واحدة

### التحققات (Validators)
- `quantity` و `purchase_price` يجب أن تكون أرقاماً موجبة

---

## 10. جدول دفعات الموردين (SupplierPayment)

### الوظيفة
تسجيل المدفوعات للموردين

### الحقول
| اسم الحقل | النوع | وصف | ملاحظات |
|-----------|-------|------|---------|
| `id` | Integer | المعرف الفريد | Primary Key |
| `supplier_id` | Integer | معرف المورد | Foreign Key → Supplier.id, Not Null |
| `invoice_id` | Integer | معرف الفاتورة | Foreign Key → PurchaseInvoice.id, Not Null |
| `amount` | Float | المبلغ | Not Null, > 0 |
| `payment_method` | String(50) | طريقة الدفع | نقد، بنك، شيك، تحويل، آجل |
| `payment_date` | Date | تاريخ الدفع | Not Null, Default: اليوم |
| `reference_number` | String(50) | رقم المرجع/الشيك | Nullable |
| `notes` | Text | ملاحظات | Nullable |
| `paid_by` | String(100) | الموظف الذي سجل الدفع | Not Null |
| `is_active` | Boolean | حالة التفعيل | Default: True |
| `cancelled_at` | DateTime | تاريخ الإلغاء | Nullable |
| `cancelled_by` | String(100) | من قام بالإلغاء | Nullable |
| `created_at` | DateTime | تاريخ الإنشاء | Default: utcnow |

### العلاقات
- **Many-to-One** مع `Supplier`: دفعة واحدة تنتمي لمورد واحد
- **Many-to-One** مع `PurchaseInvoice`: دفعة واحدة تنتمي لفاتورة واحدة

### التحققات
- `amount` يجب أن يكون رقماً موجباً

---

## 11. جدول إعدادات النظام (SystemSettings)

### الوظيفة
إعدادات النظام المركزية للتحكم في سلوك النظام

### الحقول
| اسم الحقل | النوع | وصف | ملاحظات |
|-----------|-------|------|---------|
| `id` | Integer | المعرف الفريد | Primary Key |
| `key` | String(100) | مفتاح الإعداد | Unique, Not Null |
| `value` | Text | قيمة الإعداد | Nullable |
| `value_type` | String(20) | نوع القيمة | string, int, float, bool, json |
| `category` | String(50) | فئة الإعداد | pricing, inventory, general, permissions |
| `description` | String(200) | وصف الإعداد | Nullable |
| `showroom_id` | Integer | معرف الصالة | Foreign Key → Showroom.id, Nullable |
| `is_active` | Boolean | حالة التفعيل | Default: True |
| `is_system` | Boolean | إعداد نظام لا يمكن حذفه | Default: False |
| `created_at` | DateTime | تاريخ الإنشاء | Default: utcnow |
| `created_by` | String(100) | من أنشأه | Nullable |
| `updated_at` | DateTime | تاريخ التحديث | Auto-update |
| `updated_by` | String(100) | من حدثه | Nullable |

### الخصائص المحسوبة
- `typed_value`: إرجاع القيمة بالنوع الصحيح (int, float, bool, json, string)

### ملاحظات
- `showroom_id = NULL`: إعداد على مستوى النظام
- `showroom_id` بقيمة: إعداد خاص بصالة معينة

---

## 12. جدول سجل التدقيق (AuditLog)

### الوظيفة
تتبع جميع التغييرات المهمة في النظام

### الحقول
| اسم الحقل | النوع | وصف | ملاحظات |
|-----------|-------|------|---------|
| `id` | Integer | المعرف الفريد | Primary Key |
| `table_name` | String(50) | اسم الجدول | Not Null |
| `record_id` | Integer | معرف السجل | Not Null |
| `action` | String(20) | نوع العملية | create, update, delete, cancel |
| `field_name` | String(50) | اسم الحقل (للتحديثات) | Nullable |
| `old_value` | Text | القيمة القديمة | Nullable |
| `new_value` | Text | القيمة الجديدة | Nullable |
| `user_id` | Integer | معرف المستخدم | Foreign Key → User.id |
| `user_name` | String(100) | اسم المستخدم (نسخة) | Nullable |
| `showroom_id` | Integer | معرف الصالة | Foreign Key → Showroom.id |
| `timestamp` | DateTime | وقت التغيير | Default: utcnow |
| `ip_address` | String(50) | عنوان IP | Nullable |
| `reason` | Text | سبب التغيير | Nullable |
| `notes` | Text | ملاحظات إضافية | Nullable |

### العلاقات
- **Many-to-One** مع `User`: سجل واحد ينتمي لمستخدم واحد
- **Many-to-One** مع `Showroom`: سجل واحد ينتمي لصالة واحدة

### الفهارس
- `idx_audit_table_record`: على (table_name, record_id)
- `idx_audit_user`: على (user_id)
- `idx_audit_timestamp`: على (timestamp)
- `idx_audit_action`: على (action)

---

## 13. جدول مواد الطلب (OrderMaterial)

### الوظيفة
ربط الطلبات بالمواد مع نظام خصم تلقائي وتتبع النقص

### الحقول
| اسم الحقل | النوع | وصف | ملاحظات |
|-----------|-------|------|---------|
| `id` | Integer | المعرف الفريد | Primary Key |
| `order_id` | Integer | معرف الطلب | Foreign Key → Order.id, Not Null |
| `material_id` | Integer | معرف المادة | Foreign Key → Material.id, Not Null |
| `quantity_needed` | Float | الكمية المطلوبة كلياً | Not Null, Default: 0 |
| `quantity_consumed` | Float | الكمية المخصومة من المخزون | Default: 0 |
| `quantity_shortage` | Float | الكمية الناقصة (يجب شراؤها) | Default: 0 |
| `quantity_used` | Float | للتوافق مع الكود القديم | نفس quantity_consumed |
| `unit_price` | Float | سعر الوحدة عند الخصم | Nullable |
| `unit_cost` | Float | نفس unit_price | Nullable |
| `total_cost` | Float | التكلفة الإجمالية | Nullable |
| `status` | String(20) | حالة المادة | complete, partial, pending |
| `added_at` | DateTime | تاريخ الإضافة | Default: utcnow |
| `consumed_at` | DateTime | تاريخ أول خصم | Nullable |
| `completed_at` | DateTime | تاريخ اكتمال المادة | Nullable |
| `batch_date` | Date | تاريخ الاستخدام (للتوافق) | Default: اليوم |
| `added_by` | String(100) | من أضافها | Nullable |
| `modified_by` | String(100) | من عدلها | Nullable |
| `price_modified_at` | DateTime | تاريخ تعديل السعر | Nullable |
| `notes` | Text | ملاحظات | Nullable |
| `showroom_id` | Integer | معرف الصالة | Foreign Key → Showroom.id, Not Null |

### الخصائص المحسوبة
- `is_complete`: هل تم توفير المادة بالكامل؟
- `completion_percentage`: نسبة الإنجاز (0-100%)
- `has_shortage`: هل هناك نقص؟

### العلاقات
- **Many-to-One** مع `Order`: مادة طلب واحدة تنتمي لطلب واحد
- **Many-to-One** مع `Material`: مادة طلب واحدة تنتمي لمادة واحدة
- **One-to-Many** مع `OrderCost`: مادة طلب واحدة لها عدة تكاليف

### الفهارس
- `idx_order_material`: على (order_id, material_id)
- `idx_material_order`: على (material_id, order_id)
- `idx_om_status`: على (status)
- `idx_om_shortage`: على (quantity_shortage)

### ملاحظات
- نظام الخصم التلقائي: عند إضافة مادة، يتم خصم الكمية المتاحة تلقائياً
- الحالات: `complete` (متوفرة بالكامل), `partial` (جزئياً), `pending` (غير متوفرة)

---

## 14. جدول المراحل (Stage)

### الوظيفة
تتبع مراحل تنفيذ الطلبات وتقدم العمل

### الحقول
| اسم الحقل | النوع | وصف | ملاحظات |
|-----------|-------|------|---------|
| `id` | Integer | المعرف الفريد | Primary Key |
| `order_id` | Integer | معرف الطلب | Foreign Key → Order.id, Not Null |
| `stage_name` | String(100) | اسم المرحلة | تصميم، استلام العربون، قطع، تجميع، تسليم |
| `stage_type` | String(20) | نوع المرحلة | 'طلب' أو 'إنتاج' |
| `start_date` | Date | تاريخ بدء المرحلة | Nullable |
| `end_date` | Date | تاريخ انتهاء المرحلة | Nullable |
| `progress` | Integer | نسبة التقدم | 0-100 |
| `assigned_to` | String(100) | الموظف المسؤول | Nullable |
| `notes` | Text | ملاحظات المرحلة | Nullable |
| `showroom_id` | Integer | معرف الصالة | Foreign Key → Showroom.id, Not Null |

### العلاقات
- **Many-to-One** مع `Order`: مرحلة واحدة تنتمي لطلب واحد
- **One-to-Many** مع `MaterialConsumption`: مرحلة واحدة لها عدة استهلاكات للمواد

---

## 15. جدول المرفقات (Document)

### الوظيفة
تخزين معلومات الملفات المرفقة مع الطلبات

### الحقول
| اسم الحقل | النوع | وصف | ملاحظات |
|-----------|-------|------|---------|
| `id` | Integer | المعرف الفريد | Primary Key |
| `order_id` | Integer | معرف الطلب | Foreign Key → Order.id, Not Null |
| `file_path` | String(200) | مسار الملف في النظام | Not Null |
| `showroom_id` | Integer | معرف الصالة | Foreign Key → Showroom.id, Not Null |

### العلاقات
- **Many-to-One** مع `Order`: مرفق واحد ينتمي لطلب واحد

---

## 16. جدول استلام الطلبات (ReceivedOrder)

### الوظيفة
تسجيل تفاصيل استلام الطلبات من العملاء

### الحقول
| اسم الحقل | النوع | وصف | ملاحظات |
|-----------|-------|------|---------|
| `id` | Integer | المعرف الفريد | Primary Key |
| `order_id` | Integer | معرف الطلب | Foreign Key → Order.id, Not Null |
| `received_date` | Date | تاريخ الاستلام | Not Null, Default: اليوم |
| `estimated_materials` | Text | المواد المقدرة للطلب | Nullable |
| `notes` | Text | ملاحظات الاستلام | Nullable |
| `showroom_id` | Integer | معرف الصالة | Foreign Key → Showroom.id, Not Null |

### العلاقات
- **One-to-One** مع `Order`: سجل استلام واحد ينتمي لطلب واحد

---

## 17. جدول استهلاك المواد (MaterialConsumption)

### الوظيفة
تتبع استهلاك المواد في مراحل الإنتاج المختلفة

**⚠️ ملاحظة مهمة (2025-10-16):** 
- هذا الجدول للتتبع التفصيلي بالمراحل فقط (اختياري)
- **ليس** للحسابات الأساسية - استخدم `OrderMaterial` للحسابات
- تم تعطيل الإنشاء التلقائي عند إضافة مادة للطلب (كان يسبب ازدواجية)
- يُستخدم فقط عند الحاجة لتسجيل الاستهلاك الفعلي في مرحلة محددة

### الحقول
| اسم الحقل | النوع | وصف | ملاحظات |
|-----------|-------|------|---------|
| `id` | Integer | المعرف الفريد | Primary Key |
| `order_id` | Integer | معرف الطلب | Foreign Key → Order.id, Not Null |
| `stage_id` | Integer | معرف المرحلة | Foreign Key → Stage.id, Not Null |
| `material_id` | Integer | معرف المادة | Foreign Key → Material.id, Not Null |
| `quantity_used` | Float | الكمية المستهلكة | Not Null |
| `unit_price` | Float | سعر الوحدة عند الاستخدام | Not Null |
| `batch_date` | Date | تاريخ الاستهلاك | Default: اليوم |
| `showroom_id` | Integer | معرف الصالة | Foreign Key → Showroom.id, Not Null |

### العلاقات
- **Many-to-One** مع `Order`: استهلاك واحد ينتمي لطلب واحد
- **Many-to-One** مع `Stage`: استهلاك واحد ينتمي لمرحلة واحدة
- **Many-to-One** مع `Material`: استهلاك واحد ينتمي لمادة واحدة

---

## 18. جدول تكاليف الطلبات (OrderCost)

### الوظيفة
تسجيل جميع التكاليف المرتبطة بالطلبات (مواد، عمالة، نقل، أخرى)

**⚠️ تحديث مهم (2025-10-16):** يتم إنشاء OrderCost تلقائياً عند إضافة مادة للطلبية، مع ربطها بـ OrderMaterial

### الحقول
| اسم الحقل | النوع | وصف | ملاحظات |
|-----------|-------|------|---------|
| `id` | Integer | المعرف الفريد | Primary Key |
| `order_id` | Integer | معرف الطلب | Foreign Key → Order.id, Not Null |
| `cost_type` | String(50) | نوع التكلفة | مواد، عمالة، نقل، أخرى |
| `description` | String(200) | وصف التكلفة | Nullable |
| `amount` | Float | مبلغ التكلفة | Not Null |
| `date` | Date | تاريخ التكلفة | Default: اليوم |
| `order_material_id` | Integer | معرف مادة الطلب | Foreign Key → OrderMaterial.id, **مُفعّل الآن** |
| `showroom_id` | Integer | معرف الصالة | Foreign Key → Showroom.id, Not Null |

### العلاقات
- **Many-to-One** مع `Order`: تكلفة واحدة تنتمي لطلب واحد
- **Many-to-One** مع `OrderMaterial`: تكلفة واحدة تنتمي لمادة طلب واحدة (للتكاليف من نوع "مواد")

### الآلية الجديدة (2025-10-16)
1. **عند إضافة مادة:** يتم إنشاء OrderCost تلقائياً بـ:
   - `cost_type = 'مواد'`
   - `amount = OrderMaterial.total_cost`
   - `order_material_id = OrderMaterial.id` (الربط المباشر)
   
2. **عند حذف مادة:** يتم حذف OrderCost المرتبط تلقائياً

3. **التكاليف اليدوية:** يمكن إضافة تكاليف (عمالة، نقل، أخرى) يدوياً بدون ربطها بمادة

---

## 19. جدول المدفوعات (Payment)

### الوظيفة
تسجيل جميع المدفوعات المستلمة من العملاء

### الحقول
| اسم الحقل | النوع | وصف | ملاحظات |
|-----------|-------|------|---------|
| `id` | Integer | المعرف الفريد | Primary Key |
| `order_id` | Integer | معرف الطلب | Foreign Key → Order.id, Not Null |
| `amount` | Float | مبلغ الدفع | Not Null |
| `payment_type` | String(50) | نوع الدفع | عربون، دفعة، باقي المبلغ |
| `payment_method` | String(50) | طريقة الدفع | نقد، بنك، شيك، كارت |
| `payment_date` | Date | تاريخ الدفع | Not Null, Default: اليوم |
| `notes` | Text | ملاحظات الدفع | Nullable |
| `received_by` | String(100) | الموظف المستلم | Not Null |
| `receipt_number` | String(100) | رقم الإيصال | Nullable |
| `showroom_id` | Integer | معرف الصالة | Foreign Key → Showroom.id, Not Null |

### العلاقات
- **Many-to-One** مع `Order`: دفعة واحدة تنتمي لطلب واحد

---

## ملاحظات مهمة

### 1. التغييرات الرئيسية
- ✅ **جدول Order**: تم تغيير اسم الجدول من `order` إلى `orders` (2025-01-07)
- ✅ **المواد**: مرتبطة بـ `warehouse_id` وليس `showroom_id` (نظام مخزن موحد)
- ✅ **العملاء**: مشتركون بين جميع الصالات (غير مرتبطين بصالة محددة)
- ✅ **نظام الموردين**: مكتمل وفعال (7 جداول جديدة)

### 2. العلاقات المتداخلة
- `Order` هو الجدول الرئيسي الذي تربط به معظم الجداول الأخرى
- `Material` و `Stage` لهما علاقات متعددة مع جداول مختلفة
- `OrderCost` يمكن أن ترتبط بـ `Order` مباشرة أو عبر `OrderMaterial`

### 3. الخصائص المحسوبة
- `Order` يحتوي على عدة خصائص محسوبة للمبالغ المالية وحالة الدفع والمواد
- `PurchaseInvoice` لها خصائص محسوبة للمبالغ المدفوعة والمتبقية
- `OrderMaterial` لها خصائص لتتبع نسبة الإنجاز والنقص

### 4. التواريخ
- معظم الجداول تستخدم `datetime.now(timezone.utc)` كقيمة افتراضية
- تم توحيد استخدام UTC في جميع أنحاء النظام

### 5. نظام الفصل بين الصالات
- البيانات التشغيلية (طلبات، مراحل، دفعات، تكاليف) مرتبطة بـ `showroom_id`
- البيانات المشتركة (عملاء، مواد، مخازن) غير مرتبطة بصالة محددة
- الموردين مرتبطون بصالات لكن المخازن موحدة

---

## 19. جدول الفنيين (Technician)

### الوظيفة
إدارة بيانات الفنيين المسؤولين عن التصنيع والتركيب.

### الحقول الرئيسية
- `name` - اسم الفني (مطلوب)
- `phone` - رقم الهاتف
- `email` - البريد الإلكتروني  
- `national_id` - رقم الهوية
- `specialization` - التخصص (تصنيع، تركيب، كلاهما)
- `status` - الحالة (نشط، متوقف، مفصول) افتراضي: 'نشط'
- `hire_date` - تاريخ التعيين
- `bank_name` - اسم البنك
- `bank_account` - رقم الحساب البنكي
- `manufacturing_rate_per_meter` - سعر متر التصنيع (افتراضي: 0)
- `installation_rate_per_meter` - سعر متر التركيب (افتراضي: 0)

### العلاقات
- `dues` → TechnicianDue (واحد إلى متعدد)
- `payments_received` → TechnicianPayment (واحد إلى متعدد)

### الخصائص المحسوبة
- `total_dues` - إجمالي المستحقات غير المدفوعة
- `pending_dues` - قائمة المستحقات غير المدفوعة
- `total_paid` - إجمالي المبالغ المدفوعة

---

## 20. جدول مستحقات الفنيين (TechnicianDue)

### الوظيفة
تتبع المستحقات المالية للفنيين عن كل طلبية/مرحلة.

### الحقول الرئيسية
- `technician_id` - معرف الفني (FK إلى Technician)
- `order_id` - معرف الطلبية (FK إلى Order)
- `stage_id` - معرف المرحلة (FK إلى Stage)
- `due_type` - نوع المستحق ('manufacturing' أو 'installation')
- `meters` - عدد الأمتار
- `rate_per_meter` - السعر لكل متر
- `amount` - المبلغ الإجمالي (مطلوب)
- `is_paid` - هل تم الدفع؟ (افتراضي: false)
- `paid_at` - تاريخ الدفع
- `payment_id` - معرف الدفعة (FK إلى TechnicianPayment)

### الفهارس
- `idx_tech_due_paid` على `is_paid`
- `idx_tech_due_tech` على `technician_id`
- `idx_tech_due_order` على `order_id`

---

## 21. جدول دفعات الفنيين (TechnicianPayment)

### الوظيفة
تسجيل المدفوعات المالية للفنيين.

### الحقول الرئيسية
- `technician_id` - معرف الفني (FK إلى Technician)
- `amount` - المبلغ (مطلوب، يجب أن يكون موجب)
- `payment_date` - تاريخ الدفع (مطلوب)
- `payment_method` - طريقة الدفع (نقداً، تحويل بنكي، شيك)
- `reference_number` - رقم المرجع/التحويل/الشيك
- `notes` - ملاحظات
- `paid_by` - من قام بالدفع
- `is_active` - هل الدفعة نشطة؟ (افتراضي: true)

### العلاقات
- `technician` ← Technician
- `dues_paid` → TechnicianDue (واحد إلى متعدد)

### التحقق
- `amount` يجب أن يكون أكبر من صفر

---

## تحديثات على الجداول الموجودة

### Stage (تحديث)
#### حقول جديدة للفنيين:
- `manufacturing_technician_id` - معرف فني التصنيع (FK إلى Technician)
- `installation_technician_id` - معرف فني التركيب (FK إلى Technician)
- `manufacturing_assigned_at` - تاريخ تكليف التصنيع
- `installation_assigned_at` - تاريخ تكليف التركيب
- `manufacturing_start_date` - تاريخ بدء التصنيع الفعلي
- `manufacturing_end_date` - تاريخ انتهاء التصنيع
- `installation_start_date` - تاريخ بدء التركيب
- `installation_end_date` - تاريخ انتهاء التركيب
- `order_meters` - عدد الأمتار للطلبية (لحساب المستحقات)

#### علاقات جديدة:
- `manufacturing_technician` ← Technician
- `installation_technician` ← Technician

### Order (تحديث)
#### حقول جديدة للأرشفة:
- `is_archived` - هل الطلبية مؤرشفة؟ (افتراضي: false)
- `archived_at` - تاريخ الأرشفة
- `archived_by` - من قام بالأرشفة
- `archive_notes` - ملاحظات الأرشفة

#### علاقات جديدة:
- `technician_dues` → TechnicianDue (واحد إلى متعدد)

---

## الفهارس الجديدة

### جداول الفنيين
- `idx_tech_status` على `technicians.status`
- `idx_tech_payment_tech` على `technician_payments.technician_id`
- `idx_stage_tech_mfg` على `stage.manufacturing_technician_id`
- `idx_stage_tech_inst` على `stage.installation_technician_id`

---

## إعدادات النظام الجديدة

تم إضافة إعدادات جديدة لإدارة الفنيين:

```sql
-- إعدادات الفنيين
INSERT INTO system_settings (key, value, value_type, category, description) VALUES
('default_manufacturing_rate', '50.0', 'float', 'technicians', 'سعر المتر الافتراضي للتصنيع (د.ل)'),
('default_installation_rate', '30.0', 'float', 'technicians', 'سعر المتر الافتراضي للتركيب (د.ل)'),
('auto_create_dues', 'true', 'boolean', 'technicians', 'إنشاء المستحقات تلقائياً عند إكمال المرحلة');
```

---

## تحديثات المراحل

تم تحديث المراحل من 5 إلى 6 مراحل:

### المراحل السابقة (5 مراحل)
1. تصميم
2. استلام العربون  
3. **قطع** ← تم تغييرها
4. **تجميع** ← تم تغييرها
5. تسليم

### المراحل الجديدة (6 مراحل)
1. تصميم
2. استلام العربون
3. **حصر المتطلبات** ← جديد (كان: قطع)
4. **التصنيع** ← جديد (كان: تجميع)
5. **التركيب** ← جديد تماماً
6. تسليم

### تغييرات الصلاحيات
- **استلام العربون**: انتقل من المحاسب إلى **موظف الاستقبال**
- **مسؤول العمليات**: دور جديد يجمع صلاحيات مسؤول المخزن + مسؤول الإنتاج

---

**آخر تحديث**: 2025-10-14  
**عدد الجداول**: 21 جدول رئيسي  
**التحديثات الجديدة**: ✅ إدارة الفنيين، نظام الأرشفة، تحديث المراحل
**الحالة**: ✅ محدّث ومطابق للكود الفعلي
