
from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify, send_file
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from flask_migrate import Migrate
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy.orm import validates
from datetime import datetime, timezone, timedelta
import os
from werkzeug.utils import secure_filename
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfutils
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase import pdfmetrics
from arabic_reshaper import reshape
from bidi.algorithm import get_display
import io
import re

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-here'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///kitchen_factory.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max upload size

# إضافة datetime إلى سياق القوالب
@app.context_processor
def inject_datetime():
    return {'datetime': datetime}

@app.context_processor
def inject_showrooms():
    """تمرير قائمة الصالات إلى جميع القوالب"""
    if current_user.is_authenticated and current_user.role == 'مدير':
        showrooms = Showroom.query.filter_by(is_active=True).all()
        return {'showrooms': showrooms}
    return {'showrooms': []}

# تأكد من وجود مجلد الملفات المرفوعة
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

db = SQLAlchemy(app)
migrate = Migrate(app, db)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# دالة مساعدة لتنظيف أسماء العملاء للاستخدام في أسماء الملفات
def clean_customer_name(name):
    """تنظيف اسم العميل ليكون مناسباً لاسم الملف"""
    if not name:
        return "unknown"
    
    # إزالة الأحرف الخاصة والمسافات الزائدة
    cleaned_name = re.sub(r'[^\w\s-]', '', name.strip())
    # استبدال المسافات بشرطات سفلية
    cleaned_name = re.sub(r'\s+', '_', cleaned_name)
    # تحديد الطول الأقصى لتجنب أسماء ملفات طويلة جداً
    if len(cleaned_name) > 30:
        cleaned_name = cleaned_name[:30]
    
    return cleaned_name if cleaned_name else "customer"

# نماذج قاعدة البيانات

# ==================== نموذج الصالة ====================
class Showroom(db.Model):
    """نموذج الصالة - لفصل البيانات والصلاحيات حسب الصالة"""
    __tablename__ = 'showrooms'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    code = db.Column(db.String(20), unique=True)  # كود قصير للصالة
    address = db.Column(db.String(200))
    phone = db.Column(db.String(20))
    manager_name = db.Column(db.String(100))
    notes = db.Column(db.Text)
    is_active = db.Column(db.Boolean, default=True)
    
    # Soft Delete
    deleted_at = db.Column(db.DateTime)
    deleted_by = db.Column(db.String(100))
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, onupdate=datetime.utcnow)
    
    # العلاقات
    users = db.relationship('User', back_populates='showroom', lazy=True)
    orders = db.relationship('Order', back_populates='showroom', lazy=True)

# ==================== نموذج المستخدم ====================
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(50), nullable=False)  # مدير، موظف استقبال، مسؤول مخزن، مسؤول إنتاج، مسؤول العمليات

    # حقول جديدة لفصل الصالات
    showroom_id = db.Column(db.Integer, db.ForeignKey('showrooms.id'), nullable=True)  # nullable للمديرين
    is_active = db.Column(db.Boolean, default=True)
    last_login = db.Column(db.DateTime)
    
    # العلاقات
    showroom = db.relationship('Showroom', back_populates='users')

# ==================== نموذج العميل ====================
class Customer(db.Model):
    """نموذج العميل - مشترك بين جميع الصالات"""
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(20))
    address = db.Column(db.String(200))

    # حقول جديدة
    email = db.Column(db.String(100))
    tax_id = db.Column(db.String(50))  # للشركات
    customer_type = db.Column(db.String(20), default='فرد')  # فرد، شركة
    notes = db.Column(db.Text)
    
    # ملاحظة: لا يوجد showroom_id - العملاء مشتركون بين الصالات
    
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Index للبحث السريع
    __table_args__ = (
        db.Index('idx_customer_phone', 'phone'),
        db.Index('idx_customer_name', 'name'),
    )

# ==================== نموذج الطلب ====================
class Order(db.Model):
    """نموذج الطلب - مرتبط بصالة واحدة"""
    __tablename__ = 'orders'
    
    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, db.ForeignKey('customer.id'), nullable=False)
    order_date = db.Column(db.Date, nullable=False, default=datetime.utcnow)
    delivery_date = db.Column(db.Date)
    deadline = db.Column(db.Date)  # الموعد النهائي لتسليم الطلب
    meters = db.Column(db.Integer, nullable=False)
    total_value = db.Column(db.Float, default=0.0)  # قيمة الطلبية الإجمالية
    status = db.Column(db.String(50), default='مفتوح')  # مفتوح، قيد التنفيذ، مكتمل، مسلّم
    received_by = db.Column(db.String(100))
    start_date = db.Column(db.Date)
    end_date = db.Column(db.Date)
    
    # حقل جديد - مهم: كل طلب مرتبط بصالة
    showroom_id = db.Column(db.Integer, db.ForeignKey('showrooms.id'), nullable=False)
    
    # حقول الأرشفة
    is_archived = db.Column(db.Boolean, default=False)  # هل الطلبية مؤرشفة؟
    archived_at = db.Column(db.DateTime)  # تاريخ الأرشفة
    archived_by = db.Column(db.String(100))  # من قام بالأرشفة
    archive_notes = db.Column(db.Text)  # ملاحظات الأرشفة
    
    # العلاقات
    customer = db.relationship('Customer', backref=db.backref('orders', lazy=True))
    showroom = db.relationship('Showroom', back_populates='orders')
    received_order = db.relationship('ReceivedOrder', backref=db.backref('received_order_ref', uselist=False), cascade="all, delete", lazy=True)
    stages = db.relationship('Stage', back_populates='order', cascade="all, delete")
    order_costs = db.relationship('OrderCost', backref=db.backref('order_cost', lazy=True), cascade="all, delete", overlaps="costs,order_cost")
    payments = db.relationship('Payment', backref=db.backref('order', lazy=True), cascade="all, delete")
    
    # Indexes للأداء
    __table_args__ = (
        db.Index('idx_showroom_status', 'showroom_id', 'status'),
        db.Index('idx_showroom_date', 'showroom_id', 'order_date'),
        db.Index('idx_customer_showroom', 'customer_id', 'showroom_id'),
    )
    
    @property
    def total_price(self):
        # حساب السعر الإجمالي بناءً على التكاليف المسجلة
        total = 0
        for cost in self.order_costs:
            total += cost.amount
        return total
    
    @property
    def total_paid(self):
        # إجمالي المدفوعات
        total = 0
        for payment in self.payments:
            total += payment.amount
        return total
    
    @property
    def remaining_amount(self):
        # المبلغ المتبقي
        return self.total_value - self.total_paid
    
    @property
    def payment_status(self):
        # حالة الدفع
        if self.total_value <= 0:
            return 'غير محدد'
        elif self.total_paid >= self.total_value:
            return 'مدفوع بالكامل'
        elif self.total_paid > 0:
            return 'مدفوع جزئياً'
        else:
            return 'غير مدفوع'
    
    @property
    def materials_summary(self):
        """ملخص شامل لحالة المواد"""
        materials = OrderMaterial.query.filter_by(order_id=self.id).all()
        
        if not materials:
            return {
                'total': 0,
                'complete': 0,
                'partial': 0,
                'pending': 0,
                'has_shortage': False,
                'total_shortage_value': 0
            }
        
        complete = sum(1 for m in materials if m.status == 'complete')
        partial = sum(1 for m in materials if m.status == 'partial')
        pending = sum(1 for m in materials if m.status == 'pending')
        has_shortage = any(m.quantity_shortage > 0 for m in materials)
        
        # حساب قيمة النقص الإجمالية
        total_shortage_value = sum(
            (m.quantity_shortage * (m.unit_cost or 0)) 
            for m in materials 
            if m.quantity_shortage > 0
        )
        
        return {
            'total': len(materials),
            'complete': complete,
            'partial': partial,
            'pending': pending,
            'has_shortage': has_shortage,
            'total_shortage_value': total_shortage_value
        }
    
    @property
    def shortage_materials(self):
        """المواد الناقصة فقط"""
        return OrderMaterial.query.filter_by(order_id=self.id).filter(
            OrderMaterial.quantity_shortage > 0
        ).all()
    
    @property
    def materials_ready(self):
        """هل جميع المواد جاهزة؟"""
        materials = OrderMaterial.query.filter_by(order_id=self.id).all()
        if not materials:
            return False
        return all(m.status == 'complete' for m in materials)
    
    # ==================== خصائص التكاليف والربح (مضافة 2025-10-16) ====================
    
    @property
    def total_materials_cost(self):
        """تكلفة المواد الفعلية من OrderMaterial"""
        return sum(
            (om.total_cost or 0) 
            for om in self.required_materials
        )
    
    @property
    def total_additional_costs(self):
        """التكاليف الإضافية (عمالة، نقل، أخرى) من OrderCost"""
        return sum(
            cost.amount 
            for cost in self.order_costs
            if cost.cost_type in ['عمالة', 'نقل', 'أخرى']
        )
    
    @property
    def total_cost(self):
        """إجمالي التكاليف الفعلية للطلبية (مواد + إضافية)"""
        return self.total_materials_cost + self.total_additional_costs
    
    @property
    def profit(self):
        """الربح الصافي (قيمة البيع - التكلفة)"""
        return self.total_value - self.total_cost
    
    @property
    def profit_margin(self):
        """هامش الربح %"""
        if self.total_value > 0:
            return round((self.profit / self.total_value) * 100, 2)
        return 0

# ==================== نموذج المادة ====================
class Warehouse(db.Model):
    """نموذج المخزن - لإدارة أماكن التخزين المتعددة"""
    __tablename__ = 'warehouses'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)  # اسم المخزن
    code = db.Column(db.String(20), unique=True)  # كود المخزن الفريد
    location = db.Column(db.String(200))  # الموقع/العنوان
    description = db.Column(db.Text)  # وصف المخزن
    capacity = db.Column(db.Float)  # السعة (اختياري)
    
    # معلومات الإدارة
    manager_name = db.Column(db.String(100))  # اسم مسؤول المخزن
    phone = db.Column(db.String(20))
    notes = db.Column(db.Text)
    
    # الحالة
    is_active = db.Column(db.Boolean, default=True)
    is_default = db.Column(db.Boolean, default=False)  # المخزن الافتراضي
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    created_by = db.Column(db.String(100))
    updated_at = db.Column(db.DateTime, onupdate=lambda: datetime.now(timezone.utc))
    
    # العلاقات
    materials = db.relationship('Material', back_populates='warehouse', lazy=True)
    
    def __repr__(self):
        return f'<Warehouse {self.name}>'


# ==================== نموذج إعدادات النظام ====================
class SystemSettings(db.Model):
    """إعدادات النظام المركزية - للتحكم في سلوك النظام"""
    __tablename__ = 'system_settings'
    
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(100), unique=True, nullable=False)  # مفتاح الإعداد
    value = db.Column(db.Text)  # قيمة الإعداد
    value_type = db.Column(db.String(20), default='string')  # string, int, float, bool, json
    category = db.Column(db.String(50))  # pricing, inventory, general, permissions
    description = db.Column(db.String(200))  # وصف الإعداد
    
    # الارتباط بالصالة (اختياري)
    showroom_id = db.Column(db.Integer, db.ForeignKey('showrooms.id'), nullable=True)
    # null = إعداد على مستوى النظام، قيمة = إعداد خاص بصالة معينة
    
    # الحالة
    is_active = db.Column(db.Boolean, default=True)
    is_system = db.Column(db.Boolean, default=False)  # إذا كان إعداد نظام لا يمكن حذفه
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    created_by = db.Column(db.String(100))
    updated_at = db.Column(db.DateTime, onupdate=lambda: datetime.now(timezone.utc))
    updated_by = db.Column(db.String(100))
    
    def __repr__(self):
        return f'<SystemSettings {self.key}={self.value}>'
    
    @property
    def typed_value(self):
        """إرجاع القيمة بالنوع الصحيح"""
        if self.value is None:
            return None
        
        if self.value_type == 'int':
            return int(self.value)
        elif self.value_type == 'float':
            return float(self.value)
        elif self.value_type == 'bool':
            return self.value.lower() in ('true', '1', 'yes', 'on')
        elif self.value_type == 'json':
            import json
            return json.loads(self.value)
        else:
            return self.value


# ==================== نموذج سجل التدقيق (Audit Log) ====================
class AuditLog(db.Model):
    """سجل التدقيق - لتتبع جميع التغييرات المهمة في النظام"""
    __tablename__ = 'audit_logs'
    
    id = db.Column(db.Integer, primary_key=True)
    
    # ما الذي تغير؟
    table_name = db.Column(db.String(50), nullable=False)  # اسم الجدول
    record_id = db.Column(db.Integer, nullable=False)  # معرف السجل
    action = db.Column(db.String(20), nullable=False)  # create, update, delete, cancel
    
    # تفاصيل التغيير
    field_name = db.Column(db.String(50))  # اسم الحقل (للتحديثات)
    old_value = db.Column(db.Text)  # القيمة القديمة
    new_value = db.Column(db.Text)  # القيمة الجديدة
    
    # من؟ متى؟ أين؟
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    user_name = db.Column(db.String(100))  # نسخة من اسم المستخدم
    showroom_id = db.Column(db.Integer, db.ForeignKey('showrooms.id'))
    timestamp = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    ip_address = db.Column(db.String(50))
    
    # سبب التغيير (اختياري)
    reason = db.Column(db.Text)
    notes = db.Column(db.Text)  # ملاحظات إضافية
    
    # العلاقات
    user = db.relationship('User', foreign_keys=[user_id])
    showroom = db.relationship('Showroom', foreign_keys=[showroom_id])
    
    # Indexes للأداء
    __table_args__ = (
        db.Index('idx_audit_table_record', 'table_name', 'record_id'),
        db.Index('idx_audit_user', 'user_id'),
        db.Index('idx_audit_timestamp', 'timestamp'),
        db.Index('idx_audit_action', 'action'),
    )
    
    def __repr__(self):
        return f'<AuditLog {self.action} on {self.table_name}({self.record_id}) by {self.user_name}>'


class Material(db.Model):
    """نموذج المادة - مع سياسة تسعير مرنة ومرتبط بالمخزن الموحد"""
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    unit = db.Column(db.String(50), nullable=False)  # متر، قطعة، لتر…
    quantity_available = db.Column(db.Float, default=0)
    
    # حقول الأسعار المحدثة
    unit_price = db.Column(db.Float, default=0)  # سعر الوحدة (للتوافق مع الكود القديم)
    cost_price = db.Column(db.Float, default=0)  # سعر التكلفة (المحسوب)
    purchase_price = db.Column(db.Float, default=0)  # آخر سعر شراء
    selling_price = db.Column(db.Float, default=0)  # سعر البيع (اختياري)
    
    # سياسة التسعير
    cost_price_mode = db.Column(db.String(30), default='purchase_price_default')
    # القيم: purchase_price_default, weighted_average, last_invoice
    
    allow_manual_price_edit = db.Column(db.Boolean, default=True)
    price_locked = db.Column(db.Boolean, default=False)  # إذا عُدّل يدوياً
    price_updated_at = db.Column(db.DateTime, default=datetime.utcnow)
    price_updated_by = db.Column(db.String(100))
    
    # ربط بالمخزن (بدلاً من الصالة)
    warehouse_id = db.Column(db.Integer, db.ForeignKey('warehouses.id'), nullable=False)
    
    # معلومات التخزين
    storage_location = db.Column(db.String(100))  # الموقع داخل المخزن (رف، صف، إلخ)
    min_quantity = db.Column(db.Float, default=0)  # الحد الأدنى للتنبيه
    max_quantity = db.Column(db.Float)  # الحد الأقصى (اختياري)
    
    # Soft Delete
    is_active = db.Column(db.Boolean, default=True)
    deleted_at = db.Column(db.DateTime)
    
    # العلاقات
    warehouse = db.relationship('Warehouse', back_populates='materials')

# ==================== نماذج الموردين والفواتير - النظام الجديد ====================

class Supplier(db.Model):
    """نموذج المورد الجديد - مع دعم الدفع المرن - مضاف 2025-10-19"""
    __tablename__ = 'suppliers'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    code = db.Column(db.String(20), unique=True)
    phone = db.Column(db.String(20))
    email = db.Column(db.String(100))
    address = db.Column(db.String(200))
    tax_id = db.Column(db.String(50))
    contact_person = db.Column(db.String(100))
    payment_terms = db.Column(db.String(100))
    notes = db.Column(db.Text)
    
    # ربط بالصالة
    showroom_id = db.Column(db.Integer, db.ForeignKey('showrooms.id'), nullable=False)
    
    # الحالة
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, onupdate=lambda: datetime.now(timezone.utc))
    created_by = db.Column(db.String(100))
    
    # العلاقات
    showroom = db.relationship('Showroom')
    invoices = db.relationship('SupplierInvoice', back_populates='supplier', lazy=True)
    payments = db.relationship('SupplierPayment', back_populates='supplier', lazy=True)
    debt = db.relationship('SupplierDebt', back_populates='supplier', uselist=False)
    
    # خصائص محسوبة
    @property
    def total_debt(self):
        """إجمالي الديون المتبقية"""
        return self.debt.remaining_debt if self.debt else 0
    
    @property
    def total_paid(self):
        """إجمالي المدفوعات"""
        return self.debt.paid_amount if self.debt else 0

class SupplierDebt(db.Model):
    """جدول ديون الموردين - تتبع إجمالي الديون والمدفوعات - مضاف 2025-10-19"""
    __tablename__ = 'supplier_debts'
    
    id = db.Column(db.Integer, primary_key=True)
    supplier_id = db.Column(db.Integer, db.ForeignKey('suppliers.id'), nullable=False, unique=True)
    total_debt = db.Column(db.Float, default=0)  # إجمالي الدين
    paid_amount = db.Column(db.Float, default=0)  # المبلغ المدفوع
    remaining_debt = db.Column(db.Float, default=0)  # الدين المتبقي
    
    # تلقائياً: remaining_debt = total_debt - paid_amount
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, onupdate=lambda: datetime.now(timezone.utc))
    
    # العلاقات
    supplier = db.relationship('Supplier', back_populates='debt')
    payments = db.relationship('SupplierPayment', back_populates='debt', lazy=True)

class SupplierInvoice(db.Model):
    """نموذج فاتورة المورد الجديد - مع دعم الدفع المرن - مضاف 2025-10-19"""
    __tablename__ = 'supplier_invoices'
    
    id = db.Column(db.Integer, primary_key=True)
    invoice_number = db.Column(db.String(50), unique=True, nullable=False)
    supplier_id = db.Column(db.Integer, db.ForeignKey('suppliers.id'), nullable=False)
    showroom_id = db.Column(db.Integer, db.ForeignKey('showrooms.id'), nullable=False)
    
    invoice_date = db.Column(db.Date, nullable=False, default=lambda: datetime.now(timezone.utc).date())
    due_date = db.Column(db.Date)  # تاريخ الاستحقاق
    
    # المبالغ
    total_amount = db.Column(db.Float, nullable=False, default=0)  # إجمالي قبل الخصم والضريبة
    discount_amount = db.Column(db.Float, default=0)  # قيمة الخصم
    tax_amount = db.Column(db.Float, default=0)  # قيمة الضريبة
    final_amount = db.Column(db.Float, nullable=False, default=0)  # المبلغ النهائي
    
    # حالة الدين
    debt_status = db.Column(db.String(20), default='unpaid')  # unpaid, partial, paid
    debt_amount = db.Column(db.Float, default=0)  # مبلغ الدين
    paid_amount = db.Column(db.Float, default=0)  # المبلغ المدفوع
    
    notes = db.Column(db.Text)
    
    # الحالة
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    created_by = db.Column(db.String(100))
    updated_at = db.Column(db.DateTime, onupdate=lambda: datetime.now(timezone.utc))
    
    # العلاقات
    supplier = db.relationship('Supplier', back_populates='invoices')
    showroom = db.relationship('Showroom')
    payment_allocations = db.relationship('PaymentAllocation', back_populates='invoice', lazy=True)
    
    # خصائص محسوبة
    @property
    def remaining_amount(self):
        """المبلغ المتبقي"""
        return self.debt_amount - self.paid_amount
    
    @property
    def is_fully_paid(self):
        """هل الفاتورة مدفوعة بالكامل؟"""
        return self.paid_amount >= self.debt_amount

class SupplierPayment(db.Model):
    """نموذج مدفوعات الموردين الجديد - مع دعم الدفع المرن - مضاف 2025-10-19"""
    __tablename__ = 'supplier_payments'
    
    id = db.Column(db.Integer, primary_key=True)
    supplier_id = db.Column(db.Integer, db.ForeignKey('suppliers.id'), nullable=False)
    debt_id = db.Column(db.Integer, db.ForeignKey('supplier_debts.id'), nullable=False)
    
    amount = db.Column(db.Float, nullable=False)  # مبلغ الدفع
    payment_date = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    payment_method = db.Column(db.String(50), default='نقد')  # نقد، شيك، تحويل
    reference_number = db.Column(db.String(100))  # رقم المرجع
    notes = db.Column(db.Text)
    
    # نوع الدفع
    payment_type = db.Column(db.String(20), default='flexible')  # flexible, specific_invoice
    allocation_method = db.Column(db.String(20), default='auto_fifo')  # auto_fifo, auto_priority, manual
    
    # معلومات الإضافة
    created_by = db.Column(db.String(100))
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    is_active = db.Column(db.Boolean, default=True)
    
    # العلاقات
    supplier = db.relationship('Supplier', back_populates='payments')
    debt = db.relationship('SupplierDebt', back_populates='payments')
    allocations = db.relationship('PaymentAllocation', back_populates='payment', lazy=True)
    
    # خصائص محسوبة
    @property
    def total_allocated(self):
        """إجمالي المبلغ الموزع على الفواتير"""
        return sum(a.allocated_amount for a in self.allocations)
    
    @property
    def unallocated_amount(self):
        """المبلغ غير الموزع"""
        return self.amount - self.total_allocated

class PaymentAllocation(db.Model):
    """جدول توزيع المدفوعات على الفواتير - نظام مرن - مضاف 2025-10-19"""
    __tablename__ = 'payment_allocations'
    
    id = db.Column(db.Integer, primary_key=True)
    payment_id = db.Column(db.Integer, db.ForeignKey('supplier_payments.id'), nullable=False)
    invoice_id = db.Column(db.Integer, db.ForeignKey('supplier_invoices.id'), nullable=False)
    allocated_amount = db.Column(db.Float, nullable=False)  # المبلغ المخصص لهذه الفاتورة
    
    # معلومات التوزيع
    allocation_date = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    allocation_method = db.Column(db.String(20))  # auto_fifo, auto_priority, manual
    notes = db.Column(db.Text)
    
    # العلاقات
    payment = db.relationship('SupplierPayment', back_populates='allocations')
    invoice = db.relationship('SupplierInvoice', back_populates='payment_allocations')
    
    # خصائص محسوبة
    @property
    def allocation_percentage(self):
        """نسبة التوزيع من إجمالي الدفع"""
        if self.payment and self.payment.amount > 0:
            return (self.allocated_amount / self.payment.amount) * 100
        return 0

# ==================== نماذج الفنيين والمستحقات ====================

class Technician(db.Model):
    """نموذج الفني - لإدارة الفنيين وتتبع مستحقاتهم"""
    __tablename__ = 'technicians'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(20))
    email = db.Column(db.String(120))
    national_id = db.Column(db.String(50))  # رقم الهوية
    
    # معلومات العمل
    specialization = db.Column(db.String(50))  # تصنيع، تركيب، كلاهما
    status = db.Column(db.String(20), default='نشط')  # نشط، متوقف، مفصول
    hire_date = db.Column(db.Date)
    
    # معلومات الحساب
    bank_name = db.Column(db.String(100))
    bank_account = db.Column(db.String(50))
    
    # الإعدادات
    payment_method = db.Column(db.String(20), default='per_meter')  # per_meter, per_order, fixed
    manufacturing_rate_per_meter = db.Column(db.Float, default=0)  # سعر متر التصنيع
    installation_rate_per_meter = db.Column(db.Float, default=0)   # سعر متر التركيب
    
    # ملاحظات
    notes = db.Column(db.Text)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, onupdate=lambda: datetime.now(timezone.utc))
    
    # العلاقات
    dues = db.relationship('TechnicianDue', back_populates='technician', lazy=True)
    payments_received = db.relationship('TechnicianPayment', back_populates='technician', lazy=True)
    
    @property
    def total_dues(self):
        """إجمالي المستحقات غير المدفوعة"""
        return sum([due.amount for due in self.pending_dues])
    
    @property
    def pending_dues(self):
        """المستحقات غير المدفوعة"""
        return [due for due in self.dues if not due.is_paid]
    
    @property
    def total_paid(self):
        """إجمالي المبالغ المدفوعة"""
        return sum([payment.amount for payment in self.payments_received if payment.is_active])


class TechnicianDue(db.Model):
    """نموذج مستحقات الفني - لتتبع المستحقات عن كل طلبية"""
    __tablename__ = 'technician_dues'
    
    id = db.Column(db.Integer, primary_key=True)
    technician_id = db.Column(db.Integer, db.ForeignKey('technicians.id'), nullable=False)
    order_id = db.Column(db.Integer, db.ForeignKey('orders.id'), nullable=False)
    stage_id = db.Column(db.Integer, db.ForeignKey('stage.id'), nullable=False)
    
    # نوع المستحق
    due_type = db.Column(db.String(20), nullable=False)  # 'manufacturing', 'installation'
    
    # التفاصيل
    meters = db.Column(db.Float)  # عدد الأمتار (إذا كان الحساب بالمتر)
    rate_per_meter = db.Column(db.Float)  # السعر لكل متر
    amount = db.Column(db.Float, nullable=False)  # المبلغ الإجمالي
    
    # الحالة
    is_paid = db.Column(db.Boolean, default=False)
    paid_at = db.Column(db.DateTime)
    payment_id = db.Column(db.Integer, db.ForeignKey('technician_payments.id'))
    
    # ملاحظات
    notes = db.Column(db.Text)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    
    # العلاقات
    technician = db.relationship('Technician', back_populates='dues')
    order = db.relationship('Order', backref='technician_dues')
    stage = db.relationship('Stage', backref='technician_dues')
    payment = db.relationship('TechnicianPayment', back_populates='dues_paid', foreign_keys=[payment_id])


class TechnicianPayment(db.Model):
    """نموذج دفعات الفني - لتسجيل المدفوعات للفنيين"""
    __tablename__ = 'technician_payments'
    
    id = db.Column(db.Integer, primary_key=True)
    technician_id = db.Column(db.Integer, db.ForeignKey('technicians.id'), nullable=False)
    
    # معلومات الدفع
    amount = db.Column(db.Float, nullable=False)
    payment_date = db.Column(db.Date, nullable=False)
    payment_method = db.Column(db.String(50))  # نقداً، تحويل بنكي، شيك
    
    # التفاصيل
    reference_number = db.Column(db.String(100))  # رقم التحويل/الشيك
    notes = db.Column(db.Text)
    
    # التدقيق
    paid_by = db.Column(db.String(100))  # من قام بالدفع
    is_active = db.Column(db.Boolean, default=True)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    
    # العلاقات
    technician = db.relationship('Technician', back_populates='payments_received')
    dues_paid = db.relationship('TechnicianDue', back_populates='payment', foreign_keys='TechnicianDue.payment_id')
    
    # Validators
    @validates('amount')
    def validate_amount(self, key, value):
        if value <= 0:
            raise ValueError("مبلغ الدفع يجب أن يكون رقماً موجباً")
        return value

# ==================== نماذج الطلبات والمواد ====================

class OrderMaterial(db.Model):
    """مواد الطلبية مع تتبع الخصم والنقص"""
    __tablename__ = 'order_material'
    
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('orders.id', ondelete='CASCADE'), nullable=False)
    material_id = db.Column(db.Integer, db.ForeignKey('material.id'), nullable=False)
    
    # الكميات - المفتاح الرئيسي
    quantity_needed = db.Column(db.Float, nullable=False, default=0)      # المطلوبة كلياً
    quantity_consumed = db.Column(db.Float, default=0)                    # المخصومة من المخزون
    quantity_shortage = db.Column(db.Float, default=0)                    # الناقصة (يجب شراؤها)
    
    # للتوافق مع الكود القديم
    quantity_used = db.Column(db.Float)  # نفس quantity_consumed
    
    # السعر
    unit_price = db.Column(db.Float)  # سعر الوحدة عند الخصم
    unit_cost = db.Column(db.Float)   # نفس unit_price
    total_cost = db.Column(db.Float)  # التكلفة الإجمالية
    
    # الحالة
    status = db.Column(db.String(20), default='pending')
    # القيم: 'complete', 'partial', 'pending'
    
    # التواريخ
    added_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    consumed_at = db.Column(db.DateTime)  # تاريخ أول خصم
    completed_at = db.Column(db.DateTime)  # تاريخ اكتمال المادة
    batch_date = db.Column(db.Date, default=datetime.utcnow)  # للتوافق
    
    # المستخدم
    added_by = db.Column(db.String(100))
    modified_by = db.Column(db.String(100))
    price_modified_at = db.Column(db.DateTime)
    
    # ملاحظات
    notes = db.Column(db.Text)
    
    # ربط بالصالة
    showroom_id = db.Column(db.Integer, db.ForeignKey('showrooms.id'), nullable=False)
    
    # العلاقات
    order = db.relationship('Order', backref=db.backref('required_materials', lazy=True, cascade="all, delete"))
    material = db.relationship('Material', backref=db.backref('order_usages', lazy=True))
    
    # الخصائص المحسوبة
    @property
    def is_complete(self):
        """هل تم توفير المادة بالكامل؟"""
        return self.quantity_shortage == 0 and self.quantity_consumed == self.quantity_needed
    
    @property
    def completion_percentage(self):
        """نسبة الإنجاز"""
        if not self.quantity_needed or self.quantity_needed == 0:
            return 0
        return round((self.quantity_consumed / self.quantity_needed) * 100, 2)
    
    @property
    def has_shortage(self):
        """هل هناك نقص؟"""
        return self.quantity_shortage > 0
    
    def __repr__(self):
        return f'<OrderMaterial Order#{self.order_id} Mat#{self.material_id}: {self.quantity_consumed}/{self.quantity_needed}>'

class Stage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('orders.id', ondelete='CASCADE'), nullable=False)
    stage_name = db.Column(db.String(100), nullable=False)  # اسم المرحلة
    stage_type = db.Column(db.String(20), nullable=False, default='طلب')  # 'طلب' أو 'إنتاج'
    start_date = db.Column(db.Date)
    end_date = db.Column(db.Date)
    progress = db.Column(db.Integer, default=0)  # نسبة مئوية
    assigned_to = db.Column(db.String(100))
    notes = db.Column(db.Text)
    
    # حقول الفنيين
    manufacturing_technician_id = db.Column(db.Integer, db.ForeignKey('technicians.id'))
    installation_technician_id = db.Column(db.Integer, db.ForeignKey('technicians.id'))
    
    # تواريخ تكليف الفنيين
    manufacturing_assigned_at = db.Column(db.DateTime)
    installation_assigned_at = db.Column(db.DateTime)
    
    # تواريخ بدء وانتهاء العمل الفعلي
    manufacturing_start_date = db.Column(db.DateTime)
    manufacturing_end_date = db.Column(db.DateTime)
    installation_start_date = db.Column(db.DateTime)
    installation_end_date = db.Column(db.DateTime)
    
    # معلومات الحساب
    order_meters = db.Column(db.Float)  # عدد الأمتار للطلبية (للحساب)
    
    # أسعار الفنيين (قابلة للتعديل) - مضاف 2025-10-18
    manufacturing_rate = db.Column(db.Float)  # سعر المتر للتصنيع
    installation_rate = db.Column(db.Float)   # سعر المتر للتركيب
    
    # ربط بالصالة
    showroom_id = db.Column(db.Integer, db.ForeignKey('showrooms.id'), nullable=False)
    
    # العلاقات
    order = db.relationship('Order', back_populates='stages')
    manufacturing_technician = db.relationship('Technician', foreign_keys=[manufacturing_technician_id])
    installation_technician = db.relationship('Technician', foreign_keys=[installation_technician_id])

class Document(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('orders.id', ondelete='CASCADE'), nullable=False)
    file_path = db.Column(db.String(200), nullable=False)
    
    # ربط بالصالة
    showroom_id = db.Column(db.Integer, db.ForeignKey('showrooms.id'), nullable=False)
    
    order = db.relationship('Order', backref=db.backref('documents', lazy=True))

class ReceivedOrder(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('orders.id', ondelete='CASCADE'), nullable=False)
    received_date = db.Column(db.Date, nullable=False, default=datetime.utcnow)
    estimated_materials = db.Column(db.Text)  # نصي لتخزين المواد المقدرة
    notes = db.Column(db.Text)
    
    # ربط بالصالة
    showroom_id = db.Column(db.Integer, db.ForeignKey('showrooms.id'), nullable=False)



class MaterialConsumption(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('orders.id', ondelete='CASCADE'), nullable=False)
    stage_id = db.Column(db.Integer, db.ForeignKey('stage.id'), nullable=False)
    material_id = db.Column(db.Integer, db.ForeignKey('material.id'), nullable=False)
    quantity_used = db.Column(db.Float, nullable=False)
    unit_price = db.Column(db.Float, nullable=False)  # سعر الوحدة عند وقت الاستخدام
    batch_date = db.Column(db.Date, default=datetime.utcnow)
    
    # ربط بالصالة
    showroom_id = db.Column(db.Integer, db.ForeignKey('showrooms.id'), nullable=False)
    
    order = db.relationship('Order', backref=db.backref('material_consumptions', lazy=True, cascade="all, delete"))
    stage = db.relationship('Stage', backref=db.backref('material_consumptions', lazy=True))
    material = db.relationship('Material', backref=db.backref('consumptions', lazy=True))

class OrderCost(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('orders.id', ondelete='CASCADE'), nullable=False)
    cost_type = db.Column(db.String(50), nullable=False)  # مواد، عمالة، نقل، إلخ
    description = db.Column(db.String(200))
    amount = db.Column(db.Float, nullable=False)
    date = db.Column(db.Date, default=datetime.utcnow)
    order_material_id = db.Column(db.Integer, db.ForeignKey('order_material.id'))  # للربط المباشر مع مادة الطلب
    
    # ربط بالصالة
    showroom_id = db.Column(db.Integer, db.ForeignKey('showrooms.id'), nullable=False)
    
    order = db.relationship('Order', backref=db.backref('costs', lazy=True, overlaps="order_cost"), overlaps="order_cost,order_costs")
    order_material = db.relationship('OrderMaterial', backref=db.backref('cost', lazy=True))

class Payment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('orders.id', ondelete='CASCADE'), nullable=False)
    amount = db.Column(db.Float, nullable=False)  # مبلغ الدفع
    payment_type = db.Column(db.String(50), nullable=False)  # نوع الدفع: عربون، دفعة، باقي المبلغ
    payment_method = db.Column(db.String(50), default='نقد')  # طريقة الدفع: نقد، بنك، شيك، إلخ
    payment_date = db.Column(db.Date, nullable=False, default=datetime.utcnow)
    notes = db.Column(db.Text)  # ملاحظات
    received_by = db.Column(db.String(100), nullable=False)  # الموظف المستلم
    receipt_number = db.Column(db.String(100))  # رقم الإيصال
    
    # ربط بالصالة
    showroom_id = db.Column(db.Integer, db.ForeignKey('showrooms.id'), nullable=False)

# ==================== نماذج الأرشفة ====================

class ArchiveMetadata(db.Model):
    """نموذج البيانات الوصفية للأرشفة"""
    __tablename__ = 'archive_metadata'
    
    id = db.Column(db.Integer, primary_key=True)
    source_table = db.Column(db.String(50), nullable=False)
    source_id = db.Column(db.Integer, nullable=False)
    archived_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    archived_by = db.Column(db.String(100), nullable=False)
    archive_reason = db.Column(db.String(500))
    archive_type = db.Column(db.String(20), default='automatic')  # manual, automatic, scheduled
    original_record_json = db.Column(db.Text)
    can_restore = db.Column(db.Boolean, default=True)
    restore_conditions = db.Column(db.Text)
    data_size_bytes = db.Column(db.Integer)
    checksum = db.Column(db.String(64))
    expires_at = db.Column(db.DateTime)
    
    def __repr__(self):
        return f'<ArchiveMetadata {self.source_table}:{self.source_id}>'


class ArchiveRelationship(db.Model):
    """نموذج العلاقات المؤرشفة"""
    __tablename__ = 'archive_relationships'
    
    id = db.Column(db.Integer, primary_key=True)
    parent_table = db.Column(db.String(50), nullable=False)
    parent_id = db.Column(db.Integer, nullable=False)
    child_table = db.Column(db.String(50), nullable=False)
    child_id = db.Column(db.Integer, nullable=False)
    relationship_type = db.Column(db.String(50))
    archived_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    archive_batch_id = db.Column(db.Integer, db.ForeignKey('archive_metadata.id'))
    
    metadata_record = db.relationship('ArchiveMetadata', backref='relationships')


class ArchiveStatistics(db.Model):
    """نموذج إحصائيات الأرشفة"""
    __tablename__ = 'archive_statistics'
    
    id = db.Column(db.Integer, primary_key=True)
    table_name = db.Column(db.String(50), nullable=False, unique=True)
    total_archived = db.Column(db.Integer, default=0)
    total_size_mb = db.Column(db.Float, default=0.0)
    last_archive_date = db.Column(db.DateTime)
    last_restore_date = db.Column(db.DateTime)
    average_archive_age_days = db.Column(db.Integer)
    archive_success_rate = db.Column(db.Float, default=100.0)
    last_updated = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    
    def __repr__(self):
        return f'<ArchiveStatistics {self.table_name}: {self.total_archived} records>'


class ArchiveOperationsLog(db.Model):
    """نموذج سجل عمليات الأرشفة"""
    __tablename__ = 'archive_operations_log'
    
    id = db.Column(db.Integer, primary_key=True)
    operation_type = db.Column(db.String(20), nullable=False)  # archive, restore, delete, verify, search
    table_name = db.Column(db.String(50))
    record_count = db.Column(db.Integer, default=0)
    operation_start = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    operation_end = db.Column(db.DateTime)
    duration_seconds = db.Column(db.Integer)
    status = db.Column(db.String(20), default='running')  # running, completed, failed, cancelled
    error_message = db.Column(db.Text)
    performed_by = db.Column(db.String(100))
    batch_size = db.Column(db.Integer)
    affected_records = db.Column(db.Text)  # JSON string
    performance_metrics = db.Column(db.Text)  # JSON string
    
    @property
    def is_completed(self):
        return self.status == 'completed'
    
    @property
    def duration_formatted(self):
        if self.duration_seconds:
            minutes, seconds = divmod(self.duration_seconds, 60)
            return f"{minutes}m {seconds}s"
        return "غير محدد"
    
    def __repr__(self):
        return f'<ArchiveOperation {self.operation_type}:{self.table_name}>'


class ArchiveScheduler(db.Model):
    """نموذج جدولة الأرشفة التلقائية"""
    __tablename__ = 'archive_scheduler'
    
    id = db.Column(db.Integer, primary_key=True)
    table_name = db.Column(db.String(50), nullable=False)
    schedule_name = db.Column(db.String(100), nullable=False)
    is_enabled = db.Column(db.Boolean, default=True)
    cron_expression = db.Column(db.String(100))
    archive_condition = db.Column(db.Text, nullable=False)
    batch_size = db.Column(db.Integer, default=100)
    max_records_per_run = db.Column(db.Integer, default=1000)
    last_run = db.Column(db.DateTime)
    next_run = db.Column(db.DateTime)
    success_count = db.Column(db.Integer, default=0)
    failure_count = db.Column(db.Integer, default=0)
    last_error = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    created_by = db.Column(db.String(100))
    
    @property
    def success_rate(self):
        total = self.success_count + self.failure_count
        if total == 0:
            return 100.0
        return (self.success_count / total) * 100
    
    def __repr__(self):
        return f'<ArchiveScheduler {self.schedule_name}>'

# إضافة النماذج كسمات للتطبيق للوصول السهل
app.User = User
app.Customer = Customer
app.Order = Order
app.Material = Material
app.OrderMaterial = OrderMaterial
app.Stage = Stage
app.Document = Document
app.ReceivedOrder = ReceivedOrder
app.MaterialConsumption = MaterialConsumption
app.OrderCost = OrderCost
app.Payment = Payment

# نماذج الأرشيف
app.ArchiveMetadata = ArchiveMetadata
app.ArchiveRelationship = ArchiveRelationship
app.ArchiveStatistics = ArchiveStatistics
app.ArchiveOperationsLog = ArchiveOperationsLog
app.ArchiveScheduler = ArchiveScheduler

@login_manager.user_loader
def load_user(user_id):
    user = db.session.get(User, int(user_id))
    if user and user.is_active:
        # تحديث آخر تسجيل دخول
        user.last_login = datetime.now(timezone.utc)
        try:
            db.session.commit()
        except:
            db.session.rollback()
    return user

# ==================== Helper Functions للصلاحيات والعزل ====================

def get_scoped_query(model_class, user=None):
    """
    ترجع Query مصفّى حسب showroom_id للمستخدم
    يستخدم لعزل البيانات بين الصالات تلقائياً
    """
    user = user or current_user
    query = model_class.query
    
    # تحقق: هل النموذج يحتوي على showroom_id؟
    if not hasattr(model_class, 'showroom_id'):
        return query
    
    # المدير يرى حسب الفلتر المختار
    if user.is_authenticated and user.role == 'مدير':
        showroom_filter = session.get('showroom_filter', 'all')
        if showroom_filter and showroom_filter != 'all':
            try:
                query = query.filter_by(showroom_id=int(showroom_filter))
            except (ValueError, TypeError):
                pass
    
    # موظفون آخرون يرون صالتهم فقط
    elif user.is_authenticated and user.showroom_id:
        query = query.filter_by(showroom_id=user.showroom_id)
    
    # تصفية Soft Delete
    if hasattr(model_class, 'is_active'):
        query = query.filter_by(is_active=True)
    
    return query


# ==================== Helper Functions للإعدادات ====================

def get_setting(key, default=None, showroom_id=None):
    """
    الحصول على قيمة إعداد من قاعدة البيانات
    
    Args:
        key: مفتاح الإعداد
        default: القيمة الافتراضية إذا لم يتم العثور على الإعداد
        showroom_id: معرف الصالة (اختياري)
    
    Returns:
        القيمة المحولة للنوع الصحيح أو default
    """
    try:
        setting = SystemSettings.query.filter_by(
            key=key,
            showroom_id=showroom_id,
            is_active=True
        ).first()
        
        if setting:
            return setting.typed_value
        
        # إذا لم نجد إعداد خاص بالصالة، نبحث عن إعداد عام
        if showroom_id is not None:
            setting = SystemSettings.query.filter_by(
                key=key,
                showroom_id=None,
                is_active=True
            ).first()
            if setting:
                return setting.typed_value
        
        return default
    except Exception as e:
        print(f"Error getting setting {key}: {e}")
        return default


def set_setting(key, value, value_type='string', category='general', 
                description='', showroom_id=None, user=None):
    """
    تعيين قيمة إعداد في قاعدة البيانات
    
    Args:
        key: مفتاح الإعداد
        value: القيمة الجديدة
        value_type: نوع القيمة (string, int, float, bool, json)
        category: فئة الإعداد
        description: وصف الإعداد
        showroom_id: معرف الصالة (اختياري)
        user: المستخدم الذي يقوم بالتعديل
    
    Returns:
        كائن SystemSettings
    """
    try:
        # البحث عن إعداد موجود
        setting = SystemSettings.query.filter_by(
            key=key,
            showroom_id=showroom_id
        ).first()
        
        # تحويل القيمة إلى نص
        if value_type == 'bool':
            str_value = 'true' if value else 'false'
        elif value_type == 'json':
            import json
            str_value = json.dumps(value)
        else:
            str_value = str(value)
        
        if setting:
            # تحديث إعداد موجود
            setting.value = str_value
            setting.value_type = value_type
            setting.category = category
            setting.description = description
            setting.updated_at = datetime.now(timezone.utc)
            setting.updated_by = user.username if user else 'system'
        else:
            # إنشاء إعداد جديد
            setting = SystemSettings(
                key=key,
                value=str_value,
                value_type=value_type,
                category=category,
                description=description,
                showroom_id=showroom_id,
                created_by=user.username if user else 'system'
            )
            db.session.add(setting)
        
        db.session.commit()
        return setting
    except Exception as e:
        db.session.rollback()
        print(f"Error setting {key}: {e}")
        return None


def init_default_settings():
    """إنشاء الإعدادات الافتراضية للنظام"""
    default_settings = [
        # إعدادات التسعير
        {
            'key': 'default_cost_price_mode',
            'value': 'purchase_price_default',
            'value_type': 'string',
            'category': 'pricing',
            'description': 'سياسة التسعير الافتراضية للمواد',
            'is_system': True
        },
        {
            'key': 'allow_manual_cost_edit',
            'value': 'true',
            'value_type': 'bool',
            'category': 'pricing',
            'description': 'السماح بتعديل أسعار التكلفة يدوياً',
            'is_system': True
        },
        # إعدادات المخزون
        {
            'key': 'low_stock_threshold',
            'value': '10',
            'value_type': 'int',
            'category': 'inventory',
            'description': 'الحد الأدنى للمخزون (تنبيه)',
            'is_system': True
        },
        {
            'key': 'enable_negative_stock',
            'value': 'false',
            'value_type': 'bool',
            'category': 'inventory',
            'description': 'السماح بالمخزون السالب',
            'is_system': True
        },
        # إعدادات عامة
        {
            'key': 'company_name',
            'value': 'مصنع المطابخ',
            'value_type': 'string',
            'category': 'general',
            'description': 'اسم الشركة',
            'is_system': False
        },
        {
            'key': 'currency_symbol',
            'value': 'د.ل',
            'value_type': 'string',
            'category': 'general',
            'description': 'رمز العملة',
            'is_system': False
        },
        # إعدادات الصلاحيات
        {
            'key': 'allow_reception_edit_prices',
            'value': 'false',
            'value_type': 'bool',
            'category': 'permissions',
            'description': 'السماح لموظفي الاستقبال بتعديل الأسعار',
            'is_system': True
        }
    ]
    
    for setting_data in default_settings:
        existing = SystemSettings.query.filter_by(
            key=setting_data['key'],
            showroom_id=None
        ).first()
        
        if not existing:
            setting = SystemSettings(**setting_data)
            db.session.add(setting)
    
    try:
        db.session.commit()
        print("✅ Default settings initialized successfully")
    except Exception as e:
        db.session.rollback()
        print(f"❌ Error initializing default settings: {e}")


# ==================== Helper Functions للـ Audit Log ====================

def log_change(table, record_id, action, field=None, old_val=None, new_val=None, reason=None, notes=None):
    """
    تسجيل تغيير في سجل التدقيق
    
    Args:
        table: اسم الجدول
        record_id: معرف السجل
        action: نوع العملية (create, update, delete, cancel)
        field: اسم الحقل المعدل (للتحديثات)
        old_val: القيمة القديمة
        new_val: القيمة الجديدة
        reason: سبب التغيير
        notes: ملاحظات إضافية
    
    Returns:
        كائن AuditLog أو None
    """
    try:
        # الحصول على معلومات المستخدم الحالي
        user_id = current_user.id if current_user.is_authenticated else None
        user_name = current_user.username if current_user.is_authenticated else 'system'
        showroom_id = current_user.showroom_id if current_user.is_authenticated else None
        
        # الحصول على عنوان IP
        from flask import request
        ip_address = request.remote_addr if request else None
        
        # تحويل القيم إلى نص
        old_value_str = str(old_val) if old_val is not None else None
        new_value_str = str(new_val) if new_val is not None else None
        
        # إنشاء سجل التدقيق
        log = AuditLog(
            table_name=table,
            record_id=record_id,
            action=action,
            field_name=field,
            old_value=old_value_str,
            new_value=new_value_str,
            user_id=user_id,
            user_name=user_name,
            showroom_id=showroom_id,
            ip_address=ip_address,
            reason=reason,
            notes=notes
        )
        
        db.session.add(log)
        db.session.commit()
        
        return log
    except Exception as e:
        print(f"❌ Error logging change: {e}")
        db.session.rollback()
        return None


def log_price_change(table, record_id, field, old_value, new_value, reason=None):
    """
    تسجيل تغيير في السعر (نوع خاص من التغييرات)
    
    Args:
        table: اسم الجدول
        record_id: معرف السجل
        field: اسم حقل السعر
        old_value: السعر القديم
        new_value: السعر الجديد
        reason: سبب التغيير
    """
    notes = f'تغيير سعر {field} من {old_value} إلى {new_value}'
    return log_change(
        table=table,
        record_id=record_id,
        action='update',
        field=field,
        old_val=old_value,
        new_val=new_value,
        reason=reason or 'تحديث السعر',
        notes=notes
    )


def log_quantity_change(table, record_id, old_qty, new_qty, reason=None):
    """
    تسجيل تغيير في الكمية
    
    Args:
        table: اسم الجدول
        record_id: معرف السجل
        old_qty: الكمية القديمة
        new_qty: الكمية الجديدة
        reason: سبب التغيير
    """
    diff = new_qty - old_qty
    action_type = 'إضافة' if diff > 0 else 'سحب'
    notes = f'{action_type} {abs(diff)} وحدة'
    
    return log_change(
        table=table,
        record_id=record_id,
        action='update',
        field='quantity_available',
        old_val=old_qty,
        new_val=new_qty,
        reason=reason or 'تحديث الكمية',
        notes=notes
    )


def get_audit_logs(table=None, record_id=None, user_id=None, action=None, limit=100):
    """
    الحصول على سجلات التدقيق مع فلترة
    
    Args:
        table: اسم الجدول (اختياري)
        record_id: معرف السجل (اختياري)
        user_id: معرف المستخدم (اختياري)
        action: نوع العملية (اختياري)
        limit: عدد السجلات الأقصى
    
    Returns:
        قائمة بسجلات التدقيق
    """
    query = AuditLog.query
    
    if table:
        query = query.filter_by(table_name=table)
    if record_id:
        query = query.filter_by(record_id=record_id)
    if user_id:
        query = query.filter_by(user_id=user_id)
    if action:
        query = query.filter_by(action=action)
    
    return query.order_by(AuditLog.timestamp.desc()).limit(limit).all()


# ==================== Helper Functions لنظام الأرشفة ====================

import hashlib
import json
from typing import List, Dict, Any, Optional
import logging

def get_archive_setting(key: str, default: Any = None, value_type: str = 'string') -> Any:
    """جلب إعداد نظام الأرشفة من إعدادات النظام"""
    value = get_setting(key, default)
    
    # تحويل القيمة للنوع المطلوب
    if value is None:
        return default
        
    try:
        if value_type == 'int':
            return int(value) if value != '' else default
        elif value_type == 'float':
            return float(value) if value != '' else default
        elif value_type == 'bool':
            if isinstance(value, bool):
                return value
            if isinstance(value, str):
                return value.lower() in ('true', '1', 'yes', 'on')
            return bool(value)
        else:  # string
            return str(value) if value is not None else default
    except (ValueError, TypeError):
        return default

def calculate_data_checksum(data: dict) -> str:
    """حساب checksum للبيانات للتحقق من السلامة"""
    try:
        json_str = json.dumps(data, sort_keys=True, ensure_ascii=False, default=str)
        return hashlib.sha256(json_str.encode('utf-8')).hexdigest()
    except Exception:
        return ""

def log_archive_operation(operation_type: str, table_name: str = None, 
                         record_count: int = 0, performed_by: str = None,
                         batch_size: int = None) -> ArchiveOperationsLog:
    """تسجيل عملية أرشفة في السجل"""
    operation = ArchiveOperationsLog(
        operation_type=operation_type,
        table_name=table_name,
        record_count=record_count,
        performed_by=performed_by or (current_user.username if current_user.is_authenticated else 'system'),
        batch_size=batch_size,
        status='running'
    )
    
    db.session.add(operation)
    db.session.commit()
    return operation

def complete_archive_operation(operation: ArchiveOperationsLog, 
                             status: str = 'completed',
                             error_message: str = None,
                             affected_records: List = None,
                             performance_metrics: Dict = None):
    """إكمال عملية أرشفة وتحديث السجل"""
    operation.operation_end = datetime.now(timezone.utc)
    operation.duration_seconds = int((operation.operation_end - operation.operation_start).total_seconds())
    operation.status = status
    operation.error_message = error_message
    
    if affected_records:
        operation.affected_records = json.dumps(affected_records, default=str)
    
    if performance_metrics:
        operation.performance_metrics = json.dumps(performance_metrics, default=str)
    
    db.session.commit()

def update_archive_statistics(table_name: str, archived_count: int = 0, 
                            size_mb: float = 0, operation_type: str = 'archive'):
    """تحديث إحصائيات الأرشفة"""
    stats = ArchiveStatistics.query.filter_by(table_name=table_name).first()
    
    if not stats:
        stats = ArchiveStatistics(
            table_name=table_name,
            total_archived=0,
            total_size_mb=0,
            archive_success_rate=100.0
        )
        db.session.add(stats)
    
    if operation_type == 'archive':
        stats.total_archived += archived_count
        stats.total_size_mb += size_mb
        stats.last_archive_date = datetime.now(timezone.utc)
    elif operation_type == 'restore':
        stats.total_archived = max(0, stats.total_archived - archived_count)
        stats.last_restore_date = datetime.now(timezone.utc)
    
    stats.last_updated = datetime.now(timezone.utc)
    db.session.commit()

def create_archive_metadata(source_table: str, source_id: int, 
                          original_record: dict, archive_reason: str,
                          archive_type: str = 'automatic') -> ArchiveMetadata:
    """إنشاء بيانات وصفية للأرشفة"""
    
    # تحويل البيانات إلى JSON وحساب الchecksum
    json_data = json.dumps(original_record, default=str, ensure_ascii=False)
    checksum = calculate_data_checksum(original_record)
    data_size = len(json_data.encode('utf-8'))
    
    # تحديد تاريخ انتهاء الصلاحية
    retention_years = get_archive_setting('archive_retention_years', 7, 'int')
    expires_at = datetime.now(timezone.utc).replace(year=datetime.now().year + retention_years)
    
    metadata = ArchiveMetadata(
        source_table=source_table,
        source_id=source_id,
        archived_by=current_user.username if current_user.is_authenticated else 'system',
        archive_reason=archive_reason,
        archive_type=archive_type,
        original_record_json=json_data,
        data_size_bytes=data_size,
        checksum=checksum,
        expires_at=expires_at
    )
    
    db.session.add(metadata)
    db.session.flush()  # للحصول على المعرف
    return metadata

def get_record_by_table_and_id(table_name: str, record_id: int) -> dict:
    """جلب سجل من جدول محدد بناءً على المعرف"""
    
    # خريطة الجداول والنماذج
    table_models = {
        'orders': Order,
        'stages': Stage,
        'order_material': OrderMaterial,
        'received_order': ReceivedOrder,
        'technician_dues': TechnicianDue,
        'technician_payment': TechnicianPayment,
        'audit_logs': AuditLog,
    }
    
    model_class = table_models.get(table_name)
    if not model_class:
        raise Exception(f"جدول غير مدعوم: {table_name}")
    
    record = model_class.query.get(record_id)
    if not record:
        return None
    
    # تحويل السجل إلى dictionary
    result = {}
    for column in model_class.__table__.columns:
        value = getattr(record, column.name)
        if isinstance(value, datetime):
            result[column.name] = value.isoformat()
        else:
            result[column.name] = value
    
    return result

def archive_record_to_table(source_table: str, record_data: dict, metadata_id: int) -> bool:
    """أرشفة سجل إلى جدول الأرشيف المقابل"""
    
    # خريطة جداول الأرشيف
    archive_tables = {
        'orders': 'archive_orders',
        'stages': 'archive_stages',
        'order_material': 'archive_order_material',
        'received_order': 'archive_received_order',
        'technician_dues': 'archive_technician_due',
        'technician_payment': 'archive_technician_payment',
        'audit_logs': 'archive_audit_log',
    }
    
    archive_table = archive_tables.get(source_table)
    if not archive_table:
        raise Exception(f"جدول أرشيف غير موجود لـ: {source_table}")
    
    try:
        # إضافة معلومات الأرشفة
        record_data['archive_metadata_id'] = metadata_id
        record_data['archived_at'] = datetime.now(timezone.utc).isoformat()
        
        # بناء استعلام الإدراج
        columns = list(record_data.keys())
        placeholders = ', '.join(['?' for _ in columns])
        values = [record_data[col] for col in columns]
        
        query = f"INSERT INTO {archive_table} ({', '.join(columns)}) VALUES ({placeholders})"
        
        # تنفيذ الاستعلام
        db.session.execute(query, values)
        return True
        
    except Exception as e:
        print(f"خطأ في أرشفة السجل إلى {archive_table}: {str(e)}")
        return False

def archive_related_records(source_table: str, parent_id: int, metadata_id: int) -> int:
    """أرشفة السجلات المرتبطة بالسجل الرئيسي"""
    
    # قواعد العلاقات للجداول
    relationships_config = {
        'orders': [
            {'table': 'stages', 'foreign_key': 'order_id'},
            {'table': 'order_material', 'foreign_key': 'order_id'},
            {'table': 'received_order', 'foreign_key': 'order_id'},
        ]
    }
    
    relationships = relationships_config.get(source_table, [])
    total_archived = 0
    
    for rel in relationships:
        try:
            # جلب السجلات المرتبطة
            related_records = db.session.execute(
                f"SELECT * FROM {rel['table']} WHERE {rel['foreign_key']} = ?",
                [parent_id]
            ).fetchall()
            
            for record in related_records:
                # تحويل السجل إلى dictionary
                record_dict = dict(record._mapping) if hasattr(record, '_mapping') else dict(record)
                
                # أرشفة السجل
                if archive_record_to_table(rel['table'], record_dict, metadata_id):
                    # تسجيل العلاقة
                    relationship = ArchiveRelationship(
                        parent_table=source_table,
                        parent_id=parent_id,
                        child_table=rel['table'],
                        child_id=record_dict['id'],
                        relationship_type='one_to_many',
                        archive_batch_id=metadata_id
                    )
                    db.session.add(relationship)
                    total_archived += 1
        
        except Exception as e:
            print(f"خطأ في أرشفة السجلات المرتبطة من {rel['table']}: {str(e)}")
    
    return total_archived

def delete_original_records(source_table: str, parent_id: int):
    """حذف السجلات من الجداول الأصلية بعد الأرشفة"""
    
    # حذف السجلات المرتبطة أولاً (بناءً على العلاقات)
    relationships_config = {
        'orders': [
            {'table': 'received_order', 'foreign_key': 'order_id'},
            {'table': 'order_material', 'foreign_key': 'order_id'},
            {'table': 'stages', 'foreign_key': 'order_id'}
        ]
    }
    
    related_tables = relationships_config.get(source_table, [])
    
    # حذف السجلات المرتبطة
    for rel in related_tables:
        try:
            db.session.execute(f"DELETE FROM {rel['table']} WHERE {rel['foreign_key']} = ?", [parent_id])
        except Exception as e:
            print(f"خطأ في حذف السجلات من {rel['table']}: {str(e)}")
    
    # حذف السجل الرئيسي
    try:
        db.session.execute(f"DELETE FROM {source_table} WHERE id = ?", [parent_id])
        db.session.commit()
        return True
    except Exception as e:
        db.session.rollback()
        print(f"خطأ في حذف السجل الرئيسي من {source_table}: {str(e)}")
        return False

def archive_single_record(source_table: str, record_id: int, 
                        archive_reason: str = 'تلقائية',
                        archive_type: str = 'automatic') -> bool:
    """أرشفة سجل واحد مع جميع البيانات المرتبطة"""
    
    try:
        # بدء عملية الأرشفة في السجل
        operation = log_archive_operation('archive', source_table, 1)
        
        # جلب السجل الأصلي
        original_record = get_record_by_table_and_id(source_table, record_id)
        if not original_record:
            raise Exception(f"السجل {record_id} غير موجود في جدول {source_table}")
        
        # إنشاء البيانات الوصفية
        metadata = create_archive_metadata(
            source_table, record_id, original_record, archive_reason, archive_type
        )
        
        # أرشفة السجل الرئيسي
        if not archive_record_to_table(source_table, original_record, metadata.id):
            raise Exception("فشل في أرشفة السجل الرئيسي")
        
        # أرشفة السجلات المرتبطة
        related_count = archive_related_records(source_table, record_id, metadata.id)
        
        # حذف السجلات من الجداول الأصلية
        if not delete_original_records(source_table, record_id):
            raise Exception("فشل في حذف السجلات الأصلية")
        
        # تحديث الإحصائيات
        update_archive_statistics(source_table, 1, metadata.data_size_bytes / (1024 * 1024))
        
        # إكمال العملية
        complete_archive_operation(
            operation, 
            'completed',
            affected_records=[record_id],
            performance_metrics={
                'main_record': 1,
                'related_records': related_count,
                'data_size_mb': metadata.data_size_bytes / (1024 * 1024)
            }
        )
        
        return True
        
    except Exception as e:
        complete_archive_operation(operation, 'failed', str(e))
        db.session.rollback()
        return False

def get_eligible_records_for_archive(table_name: str, limit: int = 100) -> List[int]:
    """الحصول على قائمة بالسجلات المؤهلة للأرشفة"""
    
    # شروط الأرشفة لكل جدول
    archive_conditions = {
        'orders': {
            'days': get_archive_setting('order_auto_archive_days', 90, 'int'),
            'condition': "status = 'مسلّم' AND delivery_date IS NOT NULL"
        },
        'technician_dues': {
            'days': get_archive_setting('technician_payment_archive_days', 180, 'int'),
            'condition': "is_paid = 1 AND paid_at IS NOT NULL"
        },
        'audit_logs': {
            'days': get_archive_setting('audit_log_archive_days', 180, 'int'),
            'condition': "action NOT LIKE 'login%'"
        }
    }
    
    config = archive_conditions.get(table_name)
    if not config:
        return []
    
    try:
        # بناء الاستعلام
        date_condition = "DATE('now', '-{} days')".format(config['days'])
        
        if table_name == 'orders':
            date_field = 'delivery_date'
        elif table_name == 'technician_dues':
            date_field = 'paid_at'
        elif table_name == 'audit_logs':
            date_field = 'timestamp'
        else:
            date_field = 'created_at'
        
        query = f"""
            SELECT id FROM {table_name} 
            WHERE {config['condition']}
            AND {date_field} <= {date_condition}
            AND id NOT IN (
                SELECT source_id FROM archive_metadata 
                WHERE source_table = '{table_name}'
            )
            LIMIT {limit}
        """
        
        from sqlalchemy import text
        result = db.session.execute(text(query)).fetchall()
        return [row[0] for row in result]
        
    except Exception as e:
        print(f"خطأ في جلب السجلات المؤهلة للأرشفة من {table_name}: {str(e)}")
        return []

def restore_archived_record(source_table: str, record_id: int, 
                          restore_reason: str = 'طلب استعادة') -> bool:
    """استعادة سجل من الأرشيف إلى النظام الرئيسي"""
    
    try:
        # البحث عن البيانات الوصفية
        metadata = ArchiveMetadata.query.filter_by(
            source_table=source_table, 
            source_id=record_id
        ).first()
        
        if not metadata:
            raise Exception(f"لا يوجد سجل مؤرشف للمعرف {record_id} في جدول {source_table}")
        
        if not metadata.can_restore:
            raise Exception(f"السجل {record_id} لا يمكن استعادته: {metadata.restore_conditions}")
        
        # تسجيل بداية عملية الاستعادة
        operation = log_archive_operation('restore', source_table, 1)
        
        # استعادة السجل الرئيسي
        if not restore_main_record(source_table, record_id, metadata.id):
            raise Exception("فشل في استعادة السجل الرئيسي")
        
        # استعادة السجلات المرتبطة
        restored_count = restore_related_records(source_table, record_id, metadata.id)
        
        # حذف السجلات من الأرشيف
        delete_archived_records(source_table, record_id, metadata.id)
        
        # تحديث الإحصائيات
        update_archive_statistics(source_table, -1, operation_type='restore')
        
        # إكمال العملية
        complete_archive_operation(
            operation,
            'completed',
            affected_records=[record_id],
            performance_metrics={
                'main_record': 1,
                'related_records': restored_count,
                'restore_reason': restore_reason
            }
        )
        
        return True
        
    except Exception as e:
        complete_archive_operation(operation, 'failed', str(e))
        return False

def restore_main_record(source_table: str, record_id: int, metadata_id: int) -> bool:
    """استعادة السجل الرئيسي من الأرشيف"""
    
    archive_tables = {
        'orders': 'archive_orders',
        'stages': 'archive_stages',
        'order_material': 'archive_order_material',
        'received_order': 'archive_received_order',
        'technician_dues': 'archive_technician_due',
        'technician_payment': 'archive_technician_payment',
        'audit_logs': 'archive_audit_log',
    }
    
    archive_table = archive_tables.get(source_table)
    if not archive_table:
        return False
    
    try:
        # جلب السجل من الأرشيف
        archived_record = db.session.execute(
            f"SELECT * FROM {archive_table} WHERE archive_metadata_id = ? LIMIT 1",
            [metadata_id]
        ).fetchone()
        
        if not archived_record:
            return False
        
        # تحويل إلى dictionary وإزالة حقول الأرشفة
        record_dict = dict(archived_record._mapping) if hasattr(archived_record, '_mapping') else dict(archived_record)
        record_dict.pop('archive_metadata_id', None)
        record_dict.pop('archived_at', None)
        
        # إدراج في الجدول الأصلي
        columns = list(record_dict.keys())
        placeholders = ', '.join(['?' for _ in columns])
        values = [record_dict[col] for col in columns]
        
        query = f"INSERT INTO {source_table} ({', '.join(columns)}) VALUES ({placeholders})"
        db.session.execute(query, values)
        
        return True
        
    except Exception as e:
        print(f"خطأ في استعادة السجل الرئيسي من {archive_table}: {str(e)}")
        return False

def restore_related_records(source_table: str, parent_id: int, metadata_id: int) -> int:
    """استعادة السجلات المرتبطة من الأرشيف"""
    
    # جلب العلاقات المؤرشفة
    relationships = ArchiveRelationship.query.filter_by(
        parent_table=source_table,
        parent_id=parent_id,
        archive_batch_id=metadata_id
    ).all()
    
    restored_count = 0
    
    for rel in relationships:
        try:
            # استعادة السجل المرتبط
            if restore_main_record(rel.child_table, rel.child_id, metadata_id):
                restored_count += 1
        except Exception as e:
            print(f"خطأ في استعادة السجل المرتبط {rel.child_table}:{rel.child_id}: {str(e)}")
    
    return restored_count

def delete_archived_records(source_table: str, record_id: int, metadata_id: int):
    """حذف السجلات من الأرشيف بعد الاستعادة"""
    
    try:
        # حذف العلاقات المؤرشفة
        ArchiveRelationship.query.filter_by(archive_batch_id=metadata_id).delete()
        
        # حذف البيانات الوصفية
        ArchiveMetadata.query.filter_by(id=metadata_id).delete()
        
        # حذف السجلات من جداول الأرشيف
        archive_tables = {
            'orders': 'archive_orders',
            'stages': 'archive_stages',
            'order_material': 'archive_order_material',
            'received_order': 'archive_received_order',
            'technician_dues': 'archive_technician_due',
            'technician_payment': 'archive_technician_payment',
            'audit_logs': 'archive_audit_log',
        }
        
        archive_table = archive_tables.get(source_table)
        if archive_table:
            db.session.execute(
                f"DELETE FROM {archive_table} WHERE archive_metadata_id = ?",
                [metadata_id]
            )
        
        db.session.commit()
        
    except Exception as e:
        db.session.rollback()
        print(f"خطأ في حذف السجلات المؤرشفة: {str(e)}")

def search_archived_records(search_params: Dict[str, Any]) -> List[Dict]:
    """البحث في السجلات المؤرشفة"""
    
    table_name = search_params.get('table_name')
    start_date = search_params.get('start_date')
    end_date = search_params.get('end_date')
    archive_reason = search_params.get('archive_reason')
    archived_by = search_params.get('archived_by')
    limit = search_params.get('limit', get_archive_setting('archive_search_results_limit', 100, 'int'))
    
    # تسجيل عملية البحث
    operation = log_archive_operation('search', table_name)
    
    try:
        # بناء استعلام البحث
        query = "SELECT * FROM archive_metadata WHERE 1=1"
        params = []
        
        if table_name:
            query += " AND source_table = ?"
            params.append(table_name)
        
        if start_date:
            query += " AND archived_at >= ?"
            params.append(start_date)
        
        if end_date:
            query += " AND archived_at <= ?"
            params.append(end_date)
        
        if archive_reason:
            query += " AND archive_reason LIKE ?"
            params.append(f"%{archive_reason}%")
        
        if archived_by:
            query += " AND archived_by = ?"
            params.append(archived_by)
        
        query += f" ORDER BY archived_at DESC LIMIT {limit}"
        
        # تنفيذ البحث
        from sqlalchemy import text
        results = db.session.execute(text(query), params).fetchall()
        
        # تحويل النتائج إلى قائمة من القواميس
        search_results = []
        for row in results:
            result = dict(row._mapping) if hasattr(row, '_mapping') else dict(row)
            # إضافة البيانات الأصلية إذا كانت متاحة
            if result['original_record_json']:
                try:
                    result['original_data'] = json.loads(result['original_record_json'])
                except:
                    result['original_data'] = None
            search_results.append(result)
        
        # إكمال عملية البحث
        complete_archive_operation(
            operation,
            'completed',
            performance_metrics={
                'results_count': len(search_results),
                'search_params': search_params
            }
        )
        
        return search_results
        
    except Exception as e:
        complete_archive_operation(operation, 'failed', str(e))
        raise e

def archive_batch_records(source_table: str, record_ids: List[int], 
                         archive_reason: str = 'دفعية', 
                         batch_size: int = None) -> Dict[str, Any]:
    """أرشفة مجموعة من السجلات في دفعات"""
    
    if not batch_size:
        batch_size = get_archive_setting('archive_batch_size', 50, 'int')
    
    total_records = len(record_ids)
    successful_count = 0
    failed_count = 0
    failed_records = []
    
    # تسجيل بداية العملية
    operation = log_archive_operation('archive', source_table, total_records)
    
    try:
        # معالجة السجلات في دفعات
        for i in range(0, total_records, batch_size):
            batch = record_ids[i:i + batch_size]
            
            for record_id in batch:
                if archive_single_record(source_table, record_id, archive_reason, 'manual'):
                    successful_count += 1
                else:
                    failed_count += 1
                    failed_records.append(record_id)
            
            # فاصل زمني بين الدفعات لتجنب الحمل الزائد
            import time
            time.sleep(0.1)
        
        # إكمال العملية
        status = 'completed' if failed_count == 0 else 'partial_failure'
        complete_archive_operation(
            operation,
            status,
            f"فشل في {failed_count} من أصل {total_records}" if failed_count > 0 else None,
            record_ids,
            {
                'successful_count': successful_count,
                'failed_count': failed_count,
                'failed_records': failed_records,
                'batch_size': batch_size
            }
        )
        
        return {
            'success': True,
            'total_records': total_records,
            'successful_count': successful_count,
            'failed_count': failed_count,
            'failed_records': failed_records
        }
        
    except Exception as e:
        complete_archive_operation(operation, 'failed', str(e))
        return {
            'success': False,
            'error': str(e),
            'successful_count': successful_count,
            'failed_count': failed_count
        }

def auto_archive_eligible_records() -> Dict[str, Any]:
    """أرشفة تلقائية للسجلات المؤهلة حسب الإعدادات"""
    
    if not get_archive_setting('archive_system_enabled', True, 'bool'):
        return {'message': 'نظام الأرشفة معطل'}
    
    if not get_archive_setting('archive_auto_mode_enabled', True, 'bool'):
        return {'message': 'الأرشفة التلقائية معطلة'}
    
    results = {}
    max_daily = get_archive_setting('archive_max_daily_records', 500, 'int')
    
    # أرشفة الطلبيات المؤهلة
    eligible_orders = get_eligible_records_for_archive('orders', min(100, max_daily))
    if eligible_orders:
        results['orders'] = archive_batch_records('orders', eligible_orders, 'تلقائية - انتهاء المدة المحددة')
    
    # أرشفة مستحقات الفنيين المؤهلة
    remaining_limit = max_daily - len(eligible_orders) if eligible_orders else max_daily
    if remaining_limit > 0:
        eligible_dues = get_eligible_records_for_archive('technician_dues', min(50, remaining_limit))
        if eligible_dues:
            results['technician_dues'] = archive_batch_records('technician_dues', eligible_dues, 'تلقائية - مستحق مدفوع')
    
    # أرشفة سجل التدقيق القديم
    remaining_limit = max_daily - len(eligible_orders or []) - len(eligible_dues or [])
    if remaining_limit > 0:
        eligible_logs = get_eligible_records_for_archive('audit_logs', min(200, remaining_limit))
        if eligible_logs:
            results['audit_logs'] = archive_batch_records('audit_logs', eligible_logs, 'تلقائية - سجل قديم')
    
    return results

def get_archive_dashboard_stats() -> Dict[str, Any]:
    """الحصول على إحصائيات لوحة الأرشيف"""
    
    stats = {}
    
    # إحصائيات الجداول المؤرشفة
    archive_stats = ArchiveStatistics.query.all()
    stats['tables'] = {stat.table_name: {
        'total_archived': stat.total_archived,
        'total_size_mb': float(stat.total_size_mb or 0),
        'last_archive_date': stat.last_archive_date,
        'success_rate': float(stat.archive_success_rate or 100)
    } for stat in archive_stats}
    
    # إحصائيات العمليات الأخيرة
    recent_operations = ArchiveOperationsLog.query.order_by(
        ArchiveOperationsLog.operation_start.desc()
    ).limit(10).all()
    
    stats['recent_operations'] = [
        {
            'id': op.id,
            'operation_type': op.operation_type,
            'table_name': op.table_name,
            'record_count': op.record_count,
            'status': op.status,
            'performed_by': op.performed_by,
            'operation_start': op.operation_start.isoformat() if op.operation_start else None,
            'duration_formatted': op.duration_formatted
        }
        for op in recent_operations
    ]
    
    # حساب الإجماليات
    stats['totals'] = {
        'total_archived_records': sum([stat.total_archived for stat in archive_stats]),
        'total_size_mb': sum([float(stat.total_size_mb or 0) for stat in archive_stats]),
        'active_schedules': ArchiveScheduler.query.filter_by(is_enabled=True).count()
    }
    
    # عدد السجلات المؤهلة للأرشفة
    stats['pending_counts'] = {}
    for table in ['orders', 'technician_dues', 'audit_logs']:
        eligible = get_eligible_records_for_archive(table, 1)  # للعد فقط
        stats['pending_counts'][table] = len(eligible)
    
    stats['totals']['pending_archive'] = sum(stats['pending_counts'].values())
    
    return stats

# ==================== Helper Functions لنظام الدفع المرن - مضاف 2025-10-19 ====================

def allocate_payment_fifo(payment, supplier_id, amount):
    """
    توزيع المدفوعات حسب FIFO (أول وارد، أول مخرج)
    
    Args:
        payment: كائن SupplierPayment
        supplier_id: معرف المورد
        amount: المبلغ المراد توزيعه
    
    Returns:
        list: قائمة بكائنات PaymentAllocation
    """
    # جلب الفواتير غير المدفوعة بالكامل مرتبة حسب التاريخ
    invoices = SupplierInvoice.query.filter_by(
        supplier_id=supplier_id,
        is_active=True
    ).filter(
        SupplierInvoice.debt_status.in_(['unpaid', 'partial'])
    ).order_by(SupplierInvoice.invoice_date.asc()).all()
    
    remaining_payment = amount
    allocations = []
    
    for invoice in invoices:
        if remaining_payment <= 0:
            break
        
        # حساب المبلغ المتبقي للفاتورة
        invoice_remaining = invoice.remaining_amount
        
        if invoice_remaining <= 0:
            continue
        
        # تخصيص المبلغ (أقل من المتبقي أو المدفوع)
        allocated = min(remaining_payment, invoice_remaining)
        
        # تحديث الفاتورة
        invoice.paid_amount += allocated
        invoice.debt_status = 'paid' if invoice.paid_amount >= invoice.debt_amount else 'partial'
        
        # إنشاء سجل التوزيع
        allocation = PaymentAllocation(
            payment_id=payment.id,
            invoice_id=invoice.id,
            allocated_amount=allocated,
            allocation_method='auto_fifo'
        )
        
        db.session.add(allocation)
        allocations.append(allocation)
        
        remaining_payment -= allocated
    
    return allocations, remaining_payment

# ==================== Helper Functions لسياسات التسعير ====================

def update_material_cost_price(material, new_purchase_price, quantity, invoice_id=None, user=None):
    """
    تحديث سعر تكلفة المادة وفق السياسة المختارة
    
    Args:
        material: كائن Material
        new_purchase_price: سعر الشراء الجديد
        quantity: الكمية المشتراة
        invoice_id: معرف الفاتورة (للتتبع)
        user: المستخدم الذي يقوم بالتحديث
    
    Returns:
        tuple: (نجح التحديث؟, رسالة)
    """
    try:
        old_cost_price = material.cost_price
        old_purchase_price = material.purchase_price
        old_qty = material.quantity_available
        
        # تحقق: هل السعر مقفل (معدّل يدوياً) ولا يسمح بالتعديل؟
        if material.price_locked and not material.allow_manual_price_edit:
            return (False, 'السعر مقفل ولا يمكن تحديثه تلقائياً')
        
        # الحصول على سياسة التسعير من الإعدادات إذا لم تكن محددة
        if not material.cost_price_mode:
            material.cost_price_mode = get_setting('default_cost_price_mode', 'purchase_price_default')
        
        # تطبيق السياسة
        if material.cost_price_mode == 'purchase_price_default':
            # السياسة 1: استخدام آخر سعر شراء مباشرة
            material.cost_price = new_purchase_price
            
        elif material.cost_price_mode == 'weighted_average':
            # السياسة 2: متوسط مرجّح
            # الصيغة: (السعر القديم × الكمية القديمة + السعر الجديد × الكمية الجديدة) / (الكمية القديمة + الكمية الجديدة)
            total_cost = (old_cost_price * old_qty) + (new_purchase_price * quantity)
            total_qty = old_qty + quantity
            
            if total_qty > 0:
                material.cost_price = total_cost / total_qty
            else:
                material.cost_price = new_purchase_price
                
        elif material.cost_price_mode == 'last_invoice':
            # السياسة 3: آخر فاتورة (نفس السياسة 1 لكن بالاسم)
            material.cost_price = new_purchase_price
        
        else:
            # سياسة غير معروفة - استخدام الافتراضي
            material.cost_price = new_purchase_price
        
        # تسجيل آخر سعر شراء دائماً
        material.purchase_price = new_purchase_price
        material.price_updated_at = datetime.now(timezone.utc)
        material.price_updated_by = user.username if user else 'system'
        
        # تسجيل التغيير في Audit Log
        if old_cost_price != material.cost_price:
            reason = f'تحديث من فاتورة {invoice_id}' if invoice_id else 'تحديث السعر'
            log_price_change(
                table='material',
                record_id=material.id,
                field='cost_price',
                old_value=old_cost_price,
                new_value=material.cost_price,
                reason=reason
            )
        
        if old_purchase_price != material.purchase_price:
            reason = f'شراء جديد من فاتورة {invoice_id}' if invoice_id else 'تحديث سعر الشراء'
            log_price_change(
                table='material',
                record_id=material.id,
                field='purchase_price',
                old_value=old_purchase_price,
                new_value=material.purchase_price,
                reason=reason
            )
        
        db.session.commit()
        
        return (True, f'تم تحديث السعر بنجاح: {old_cost_price:.2f} ← {material.cost_price:.2f}')
        
    except Exception as e:
        db.session.rollback()
        return (False, f'خطأ في تحديث السعر: {str(e)}')


def manual_override_material_price(material_id, new_cost_price, user, reason=None):
    """
    تجاوز يدوي لسعر التكلفة (للمدير فقط)
    
    Args:
        material_id: معرف المادة
        new_cost_price: سعر التكلفة الجديد
        user: المستخدم (يجب أن يكون مدير)
        reason: سبب التجاوز
    
    Returns:
        tuple: (نجح التحديث؟, رسالة)
    """
    try:
        if user.role != 'مدير':
            return (False, 'ليس لديك صلاحية لتجاوز سعر التكلفة')
        
        material = db.session.get(Material, material_id)
        if not material:
            return (False, 'المادة غير موجودة')
        
        old_cost_price = material.cost_price
        
        # تحديث السعر
        material.cost_price = new_cost_price
        material.price_locked = True  # قفل السعر
        material.price_updated_at = datetime.now(timezone.utc)
        material.price_updated_by = user.username
        
        # تسجيل التغيير في Audit Log
        log_change(
            table='material',
            record_id=material.id,
            action='update',
            field='cost_price',
            old_val=old_cost_price,
            new_val=new_cost_price,
            reason=reason or 'تجاوز يدوي من المدير',
            notes='السعر مقفل الآن'
        )
        
        db.session.commit()
        
        return (True, f'تم تجاوز السعر بنجاح: {old_cost_price:.2f} ← {new_cost_price:.2f}')
        
    except Exception as e:
        db.session.rollback()
        return (False, f'خطأ: {str(e)}')


def unlock_material_price(material_id, user):
    """
    فتح قفل سعر التكلفة (للمدير فقط)
    
    Args:
        material_id: معرف المادة
        user: المستخدم (يجب أن يكون مدير)
    
    Returns:
        tuple: (نجح التحديث؟, رسالة)
    """
    try:
        if user.role != 'مدير':
            return (False, 'ليس لديك صلاحية لفتح قفل السعر')
        
        material = db.session.get(Material, material_id)
        if not material:
            return (False, 'المادة غير موجودة')
        
        material.price_locked = False
        material.price_updated_at = datetime.now(timezone.utc)
        material.price_updated_by = user.username
        
        # تسجيل في Audit Log
        log_change(
            table='material',
            record_id=material.id,
            action='update',
            field='price_locked',
            old_val=True,
            new_val=False,
            reason='فتح قفل السعر',
            notes='السعر الآن يتبع سياسة التسعير التلقائية'
        )
        
        db.session.commit()
        
        return (True, 'تم فتح قفل السعر بنجاح')
        
    except Exception as e:
        db.session.rollback()
        return (False, f'خطأ: {str(e)}')


def require_showroom_access(f):
    """
    Decorator لحماية المسارات - يتأكد أن المستخدم له صلاحية الصالة
    
    محدث 2025-10-18:
    - المدير: صلاحية كل الصالات
    - مسؤول الإنتاج: صلاحية كل الصالات (لا ينتمي لصالة معينة)
    - باقي الموظفين: صلاحية الصالة المحددة فقط
    """
    from functools import wraps
    
    @wraps(f)
    def decorated_function(*args, **kwargs):
        showroom_id = kwargs.get('showroom_id')
        
        if not showroom_id:
            return f(*args, **kwargs)
        
        # المدير ومسؤول الإنتاج ومسؤول العمليات ومسؤول المخزن لهم صلاحية كل الصالات
        if current_user.role in ['مدير', 'مسؤول إنتاج', 'مسؤول العمليات', 'مسؤول مخزن']:
            return f(*args, **kwargs)
        
        # موظف بصالة محددة
        if current_user.showroom_id and current_user.showroom_id == int(showroom_id):
            return f(*args, **kwargs)
        
        flash('ليس لديك صلاحية للوصول إلى هذه الصالة', 'danger')
        return redirect(url_for('dashboard'))
    
    return decorated_function


def get_user_showroom_id():
    """
    ترجع showroom_id للمستخدم الحالي
    تستخدم عند إنشاء سجلات جديدة
    
    محدث 2025-10-18:
    - المدير ومسؤول الإنتاج: يستخدمون الفلتر أو أول صالة نشطة
    - باقي الموظفين: يستخدمون صالتهم المحددة
    """
    if not current_user.is_authenticated:
        return None
    
    # المدير ومسؤول الإنتاج ومسؤول العمليات ومسؤول المخزن: استخدم الفلتر المختار
    if current_user.role in ['مدير', 'مسؤول إنتاج', 'مسؤول العمليات', 'مسؤول مخزن']:
        showroom_filter = session.get('showroom_filter')
        if showroom_filter and showroom_filter != 'all':
            try:
                return int(showroom_filter)
            except (ValueError, TypeError):
                pass
        
        # إذا لم يكن هناك فلتر، استخدم صالة المستخدم (إن وجدت)
        if current_user.showroom_id:
            return current_user.showroom_id
        
        # إذا لم يكن للمستخدم صالة محددة، استخدم أول صالة نشطة
        first_showroom = Showroom.query.filter_by(is_active=True).first()
        if first_showroom:
            return first_showroom.id
        
        # في حالة عدم وجود أي صالة، نرجع None (سيسبب خطأ يجب التعامل معه)
        return None
    
    # موظف عادي: استخدم صالته
    return current_user.showroom_id


def get_all_showrooms():
    """
    ترجع جميع الصالات النشطة
    
    محدث 2025-10-18:
    - المدير ومسؤول الإنتاج: جميع الصالات
    - باقي الموظفين: صالتهم فقط
    """
    if current_user.is_authenticated and current_user.role in ['مدير', 'مسؤول إنتاج', 'مسؤول العمليات', 'مسؤول مخزن']:
        return Showroom.query.filter_by(is_active=True).all()
    elif current_user.is_authenticated and current_user.showroom_id:
        return [current_user.showroom]
    return []


def get_system_setting(key, default_value=None, value_type='string', showroom_id=None):
    """
    الحصول على قيمة إعداد من جدول SystemSettings
    
    Args:
        key: مفتاح الإعداد
        default_value: القيمة الافتراضية إذا لم يوجد الإعداد
        value_type: نوع القيمة (string, int, float, bool, json)
        showroom_id: معرف الصالة (None = إعداد على مستوى النظام)
    
    Returns:
        القيمة المحولة حسب النوع المطلوب
    """
    try:
        # البحث عن الإعداد
        setting = SystemSettings.query.filter_by(
            key=key,
            showroom_id=showroom_id,
            is_active=True
        ).first()
        
        if not setting:
            return default_value
        
        # تحويل القيمة حسب النوع
        if value_type == 'int':
            return int(setting.value) if setting.value else default_value
        elif value_type == 'float':
            return float(setting.value) if setting.value else default_value
        elif value_type == 'bool':
            return setting.value.lower() in ['true', '1', 'yes'] if setting.value else default_value
        elif value_type == 'json':
            import json
            return json.loads(setting.value) if setting.value else default_value
        else:  # string
            return setting.value if setting.value else default_value
            
    except Exception as e:
        # في حالة حدوث خطأ، نرجع القيمة الافتراضية
        return default_value


# المسارات الرئيسية
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()

        if user and check_password_hash(user.password, password):
            login_user(user)
            flash('تم تسجيل الدخول بنجاح', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('اسم المستخدم أو كلمة المرور غير صحيحة', 'danger')

    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('تم تسجيل الخروج بنجاح', 'info')
    return redirect(url_for('login'))

@app.route('/dashboard')
@login_required
def dashboard():
    """لوحة التحكم الرئيسية مع إحصائيات مفصلة"""
    
    # الحصول على الصالة حسب المستخدم
    showroom_id = get_user_showroom_id()
    
    # إحصائيات الطلبات
    order_query = get_scoped_query(Order, current_user)
    total_orders = order_query.count()
    open_orders = order_query.filter_by(status='مفتوح').count()
    in_progress_orders = order_query.filter_by(status='قيد التنفيذ').count()
    completed_orders = order_query.filter_by(status='مكتمل').count()
    delivered_orders = order_query.filter_by(status='مسلّم').count()
    cancelled_orders = order_query.filter_by(status='ملغي').count()
    
    # الإحصائيات المالية
    payment_query = get_scoped_query(Payment, current_user)
    total_revenue = db.session.query(db.func.sum(Payment.amount)).filter(
        Payment.showroom_id == showroom_id if showroom_id else True
    ).scalar() or 0
    
    # حساب إجمالي قيمة الطلبات
    total_orders_value = db.session.query(db.func.sum(Order.total_value)).filter(
        Order.showroom_id == showroom_id if showroom_id else True,
        Order.status.in_(['مكتمل', 'مسلّم'])
    ).scalar() or 0
    
    # حساب المتبقي (الديون)
    all_orders = order_query.filter(Order.status != 'ملغي').all()
    total_remaining = 0
    for order in all_orders:
        paid_amount = sum(p.amount for p in order.payments)
        remaining = order.total_value - paid_amount
        if remaining > 0:
            total_remaining += remaining
    
    # متوسط قيمة الطلب
    avg_order_value = total_orders_value / completed_orders if completed_orders > 0 else 0
    
    # الطلبيات القريبة من موعد التسليم (خلال 3 أيام)
    from datetime import timedelta
    today = datetime.now(timezone.utc).date()
    upcoming_deadline = today + timedelta(days=3)
    upcoming_orders = order_query.filter(
        Order.delivery_date.between(today, upcoming_deadline),
        Order.status.in_(['مفتوح', 'قيد التنفيذ'])
    ).count()
    
    # الطلبيات المتأخرة
    overdue_orders = order_query.filter(
        Order.delivery_date < today,
        Order.status.in_(['مفتوح', 'قيد التنفيذ'])
    ).count()
    
    # آخر الطلبات
    recent_orders = order_query.order_by(Order.order_date.desc()).limit(5).all()
    
    # الطلبات حسب الحالة (للرسم البياني)
    orders_by_status = {
        'مفتوح': open_orders,
        'قيد التنفيذ': in_progress_orders,
        'مكتمل': completed_orders,
        'مسلّم': delivered_orders,
        'ملغي': cancelled_orders
    }
    
    # إحصائيات آخر 30 يوم
    thirty_days_ago = today - timedelta(days=30)
    recent_orders_count = order_query.filter(Order.order_date >= thirty_days_ago).count()
    recent_revenue = db.session.query(db.func.sum(Payment.amount)).filter(
        Payment.showroom_id == showroom_id if showroom_id else True,
        Payment.payment_date >= thirty_days_ago
    ).scalar() or 0
    
    # معدل النمو (مقارنة بالشهر السابق)
    sixty_days_ago = today - timedelta(days=60)
    previous_month_orders = order_query.filter(
        Order.order_date.between(sixty_days_ago, thirty_days_ago)
    ).count()
    
    growth_rate = 0
    if previous_month_orders > 0:
        growth_rate = ((recent_orders_count - previous_month_orders) / previous_month_orders) * 100

    return render_template('dashboard.html', 
                         total_orders=total_orders,
                         open_orders=open_orders,
                         in_progress_orders=in_progress_orders,
                         completed_orders=completed_orders,
                         delivered_orders=delivered_orders,
                         cancelled_orders=cancelled_orders,
                         total_revenue=total_revenue,
                         total_orders_value=total_orders_value,
                         total_remaining=total_remaining,
                         avg_order_value=avg_order_value,
                         upcoming_orders=upcoming_orders,
                         overdue_orders=overdue_orders,
                         recent_orders=recent_orders,
                         orders_by_status=orders_by_status,
                         recent_orders_count=recent_orders_count,
                         recent_revenue=recent_revenue,
                         growth_rate=growth_rate)

# مسارات عرض الطلبيات المفلترة من لوحة التحكم
@app.route('/orders/recent-30-days')
@login_required
def orders_recent_30_days():
    """عرض الطلبيات في آخر 30 يوم"""
    from datetime import timedelta
    today = datetime.now(timezone.utc).date()
    thirty_days_ago = today - timedelta(days=30)
    
    order_query = get_scoped_query(Order, current_user)
    orders = order_query.filter(
        Order.order_date >= thirty_days_ago,
        Order.is_archived == False
    ).order_by(Order.order_date.desc()).all()
    
    return render_template('orders_filtered.html',
                         orders=orders,
                         title='الطلبيات في آخر 30 يوم',
                         filter_type='recent',
                         filter_description=f'الطلبيات المضافة من {thirty_days_ago} إلى {today}')

@app.route('/orders/upcoming-delivery')
@login_required
def orders_upcoming_delivery():
    """عرض الطلبيات القريبة من موعد التسليم (خلال 3 أيام)"""
    from datetime import timedelta
    today = datetime.now(timezone.utc).date()
    upcoming_deadline = today + timedelta(days=3)
    
    order_query = get_scoped_query(Order, current_user)
    orders = order_query.filter(
        Order.delivery_date.between(today, upcoming_deadline),
        Order.status.in_(['مفتوح', 'قيد التنفيذ']),
        Order.is_archived == False
    ).order_by(Order.delivery_date.asc()).all()
    
    return render_template('orders_filtered.html',
                         orders=orders,
                         title='الطلبيات القريبة من التسليم',
                         filter_type='upcoming',
                         filter_description=f'الطلبيات المقرر تسليمها خلال 3 أيام ({today} - {upcoming_deadline})')

@app.route('/orders/overdue')
@login_required
def orders_overdue():
    """عرض الطلبيات المتأخرة عن موعد التسليم"""
    today = datetime.now(timezone.utc).date()
    
    order_query = get_scoped_query(Order, current_user)
    orders = order_query.filter(
        Order.delivery_date < today,
        Order.status.in_(['مفتوح', 'قيد التنفيذ']),
        Order.is_archived == False
    ).order_by(Order.delivery_date.asc()).all()
    
    return render_template('orders_filtered.html',
                         orders=orders,
                         title='الطلبيات المتأخرة',
                         filter_type='overdue',
                         filter_description=f'الطلبيات المتأخرة عن موعد التسليم (قبل {today})')

# مسارات إدارة الطلبات
@app.route('/orders')
@login_required
def orders():
    # تطبيق العزل حسب الصالة
    order_query = get_scoped_query(Order, current_user)
    orders = order_query.order_by(Order.order_date.desc()).all()
    return render_template('orders.html', orders=orders)

@app.route('/order/new', methods=['GET', 'POST'])
@login_required
def new_order():
    if current_user.role not in ['مدير', 'موظف استقبال']:
        flash('ليس لديك صلاحية لإضافة طلب جديد', 'danger')
        return redirect(url_for('orders'))

    if request.method == 'POST':
        customer_name = request.form.get('customer_name')
        customer_phone = request.form.get('customer_phone')
        customer_address = request.form.get('customer_address')
        delivery_date = request.form.get('delivery_date')
        deadline = request.form.get('deadline')
        # meters: القيمة الافتراضية = 1 (سيتم تحديثها في مرحلة حصر المتطلبات)
        meters = 1
        total_value = float(request.form.get('total_value', 0))

        # إنشاء عميل جديد أو تحديد عميل موجود
        customer = Customer.query.filter_by(name=customer_name, phone=customer_phone).first()
        if not customer:
            customer = Customer(name=customer_name, phone=customer_phone, address=customer_address)
            db.session.add(customer)
            db.session.flush()  # للحصول على معرف العميل

        # الحصول على معرف الصالة
        # إذا كان مدير، يمكنه اختيار الصالة من النموذج
        if current_user.role == 'مدير':
            showroom_id = request.form.get('showroom_id')
            if not showroom_id:
                flash('يجب اختيار الصالة عند إنشاء طلب جديد', 'danger')
                showrooms = get_all_showrooms()
                return render_template('new_order.html', showrooms=showrooms)
            showroom_id = int(showroom_id)
        else:
            # موظف استقبال: استخدم صالته
            showroom_id = current_user.showroom_id

        # إنشاء طلب جديد
        order = Order(
            customer_id=customer.id,
            delivery_date=datetime.strptime(delivery_date, '%Y-%m-%d').date() if delivery_date else None,
            deadline=datetime.strptime(deadline, '%Y-%m-%d').date() if deadline else None,
            meters=meters,
            total_value=total_value,
            received_by=current_user.username,
            showroom_id=showroom_id  # إضافة معرف الصالة
        )
        db.session.add(order)
        db.session.flush()  # للحصول على معرف الطلب
        
        # إنشاء مراحل الطلب الأساسية
        stages = [
            {"name": "تصميم", "progress": 100, "start_date": order.order_date, "assigned_to": current_user.username},
            {"name": "استلام العربون", "progress": 0},
            {"name": "حصر المتطلبات", "progress": 0},
            {"name": "التصنيع", "progress": 0},
            {"name": "التركيب", "progress": 0},
            {"name": "تسليم", "progress": 0}
        ]
        
        for stage_data in stages:
            stage = Stage(
                order_id=order.id,
                stage_name=stage_data["name"],
                stage_type="طلب",
                progress=stage_data["progress"],
                start_date=stage_data.get("start_date"),
                assigned_to=stage_data.get("assigned_to"),  # تعيين الموظف المسؤول تلقائياً
                showroom_id=showroom_id  # إضافة معرف الصالة
            )
            db.session.add(stage)
        
        # إنشاء سجل استلام للطلب
        received_order = ReceivedOrder(
            order_id=order.id,
            received_date=order.order_date,
            notes=f"تم الاستلام بواسطة: {current_user.username}",
            showroom_id=showroom_id  # إضافة معرف الصالة
        )
        db.session.add(received_order)
        
        db.session.commit()

        # رفع الملفات
        if 'files' in request.files:
            files = request.files.getlist('files')
            for file in files:
                if file and file.filename != '':
                    original_filename = secure_filename(file.filename)
                    # تنظيف اسم الزبون للاستخدام في اسم الملف
                    safe_customer_name = clean_customer_name(customer_name)
                    # إضافة معرف الطلب واسم الزبون إلى اسم الملف
                    filename = f"order_{order.id}_{safe_customer_name}_{original_filename}"
                    file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                    file.save(file_path)

                    # حفظ مسار الملف في قاعدة البيانات
                    document = Document(
                        order_id=order.id, 
                        file_path=filename,
                        showroom_id=order.showroom_id
                    )
                    db.session.add(document)

            db.session.commit()

        flash('تم إضافة الطلب بنجاح', 'success')
        return redirect(url_for('order_detail', order_id=order.id))

    # في حالة GET، نرسل الصالات للمدير
    showrooms = get_all_showrooms() if current_user.role == 'مدير' else []
    return render_template('new_order.html', showrooms=showrooms)

@app.route('/order/<int:order_id>')
@login_required
@require_showroom_access
def order_detail(order_id):
    order = db.get_or_404(Order, order_id)
    
    # تطبيق العزل حسب الصالة للمواد والمراحل
    material_query = get_scoped_query(Material, current_user)
    materials = material_query.all()
    
    stage_query = get_scoped_query(Stage, current_user)
    # ترتيب المراحل حسب التسلسل المنطقي
    stage_order = {
        'تصميم': 1,
        'استلام العربون': 2,
        'حصر المتطلبات': 3,
        'التصنيع': 4,
        'التركيب': 5,
        'تسليم': 6,
        'التسليم النهائي': 6
    }
    order_stages_raw = stage_query.filter_by(order_id=order_id, stage_type='طلب').all()
    order_stages = sorted(order_stages_raw, key=lambda x: stage_order.get(x.stage_name, 999))
    
    consumption_query = get_scoped_query(MaterialConsumption, current_user)
    material_consumptions = consumption_query.filter_by(order_id=order_id).all()
    
    return render_template('order_detail.html', order=order, materials=materials, order_stages=order_stages, material_consumptions=material_consumptions)

@app.route('/order/<int:order_id>/add-material', methods=['POST', 'GET'])
@login_required
def add_order_material(order_id):
    """
    ⚠️ النظام القديم - تم استبداله بنظام OrderMaterial الجديد
    يتم إعادة التوجيه للنظام الجديد تلقائياً
    """
    flash('تم الانتقال للنظام الجديد لإدارة المواد! 🎉', 'info')
    return redirect(url_for('order_materials', order_id=order_id))

@app.route('/order/<int:order_id>/stages')
@login_required
def order_stages(order_id):
    if current_user.role not in ['مدير', 'مسؤول إنتاج', 'مسؤول العمليات']:
        flash('ليس لديك صلاحية لتعديل مراحل الطلب', 'danger')
        return redirect(url_for('order_detail', order_id=order_id))
    
    order = db.get_or_404(Order, order_id)
    return render_template('order_stages.html', order=order)

@app.route('/order/<int:order_id>/update-stage/<int:stage_id>', methods=['POST'])
@login_required
def update_order_stage(order_id, stage_id):
    if current_user.role not in ['مدير', 'مسؤول إنتاج', 'مسؤول العمليات']:
        flash('ليس لديك صلاحية لتعديل مراحل الطلب', 'danger')
        return redirect(url_for('order_detail', order_id=order_id))
    
    try:
        stage = db.get_or_404(Stage, stage_id)
        order = stage.order
        action = request.form.get('action')  # 'start' أو 'complete'
        assigned_to = request.form.get('assigned_to')
        notes = request.form.get('notes')
        
        # تحديث بيانات المرحلة
        stage.assigned_to = assigned_to
        if notes:
            stage.notes = notes
        
        if action == 'start':
            # بدء المرحلة
            stage.start_date = datetime.now().date()
            stage.progress = 50  # نسبة متوسطة للمراحل المبدوءة
            
            # معالجة خاصة لمرحلة حصر المتطلبات: تحديث الأمتار - مضاف 2025-10-19
            if stage.stage_name == 'حصر المتطلبات':
                # فقط الأدوار التالية يمكنها تحديث الأمتار
                if current_user.role in ['مدير', 'مسؤول إنتاج', 'مسؤول العمليات']:
                    meters = request.form.get('meters')
                    if meters:
                        old_meters = order.meters
                        order.meters = float(meters)
                        flash(f'تم تحديث عدد الأمتار من {old_meters} إلى {meters}', 'info')
                
                flash(f'تم بدء مرحلة {stage.stage_name}', 'success')
            
            # معالجة خاصة لمراحل التصنيع والتركيب - مضاف 2025-10-18
            elif stage.stage_name in ['التصنيع', 'التركيب']:
                # الحصول على بيانات الفني والسعر
                technician_id = request.form.get('technician_id')
                rate = request.form.get('rate')  # السعر قابل للتعديل
                
                if technician_id and rate:
                    # حفظ بيانات الفني والسعر في المرحلة
                    if stage.stage_name == 'التصنيع':
                        stage.manufacturing_technician_id = int(technician_id)
                        stage.manufacturing_rate = float(rate)
                        stage.manufacturing_start_date = datetime.now()
                        stage.order_meters = order.meters
                        cost_type = 'تصنيع'
                        total_cost = float(rate) * order.meters
                    else:  # التركيب
                        stage.installation_technician_id = int(technician_id)
                        stage.installation_rate = float(rate)
                        stage.installation_start_date = datetime.now()
                        stage.order_meters = order.meters
                        cost_type = 'تركيب'
                        total_cost = float(rate) * order.meters
                    
                    # الحصول على اسم الفني
                    technician = db.session.get(Technician, int(technician_id))
                    
                    # إضافة التكلفة إلى OrderCost
                    order_cost = OrderCost(
                        order_id=order.id,
                        cost_type=cost_type,
                        description=f'{cost_type}: {technician.name} ({rate} د.ل/م² × {order.meters} م²)',
                        amount=total_cost,
                        date=datetime.now().date(),
                        showroom_id=order.showroom_id
                    )
                    db.session.add(order_cost)
                    
                    # إضافة مستحق للفني
                    technician_due = TechnicianDue(
                        technician_id=int(technician_id),
                        order_id=order.id,
                        stage_id=stage.id,
                        amount=total_cost,
                        due_date=datetime.now().date(),
                        status='مستحق',
                        notes=f'{cost_type} - طلب رقم {order.id}'
                    )
                    db.session.add(technician_due)
                    
                    flash(f'تم بدء مرحلة {stage.stage_name} وإضافة التكلفة ({total_cost:.2f} د.ل)', 'success')
                else:
                    flash(f'تم بدء مرحلة {stage.stage_name}', 'success')
            else:
                flash(f'تم بدء مرحلة {stage.stage_name}', 'success')
            
        elif action == 'complete':
            # إكمال المرحلة
            if not stage.start_date:
                stage.start_date = datetime.now().date()
            stage.end_date = datetime.now().date()
            stage.progress = 100
            flash(f'تم إكمال مرحلة {stage.stage_name}', 'success')
            
            # بدء المرحلة التالية تلقائياً
            next_stage = Stage.query.filter_by(
                order_id=order_id
            ).filter(Stage.id > stage.id).order_by(Stage.id).first()
            
            if next_stage and not next_stage.start_date:
                next_stage.start_date = datetime.now().date()
                next_stage.progress = 50
        
        # إذا كانت هذه هي مرحلة التصميم، تحديث حالة الطلب
        if stage.stage_name == 'تصميم' and stage.progress == 100:
            order = db.session.get(Order, order_id)
            order.status = 'قيد التنفيذ'
            
        # إذا كانت هذه هي مرحلة التسليم، تحديث حالة الطلب
        if stage.stage_name == 'تسليم' and stage.progress == 100:
            order = db.session.get(Order, order_id)
            order.status = 'مكتمل'
            order.end_date = datetime.now().date()
        
        db.session.commit()
        flash(f'تم تحديث مرحلة {stage.stage_name} بنجاح', 'success')
        return redirect(url_for('order_stages', order_id=order_id))
    except Exception as e:
        db.session.rollback()
        flash(f'حدث خطأ: {str(e)}', 'danger')
        return redirect(url_for('order_stages', order_id=order_id))

# دوال مساعدة لدعم اللغة العربية في PDF
def register_arabic_fonts():
    """تسجيل الخطوط العربية مع دعم Linux و Windows و macOS"""
    font_paths = [
        # Linux paths - خطوط النظام
        '/usr/share/fonts/truetype/noto/NotoSansArabic-Regular.ttf',
        '/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf',
        '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
        '/usr/share/fonts/truetype/arphic/ukai.ttf',
        '/usr/share/fonts/truetype/arphic/uming.ttf',
        
        # Linux paths - خطوط المستخدم
        '~/.fonts/NotoSansArabic-Regular.ttf',
        '~/.fonts/Amiri-Regular.ttf',
        '~/.fonts/Arial.ttf',
        
        # Windows paths
        'C:\\Windows\\Fonts\\arial.ttf',
        'C:\\Windows\\Fonts\\tahoma.ttf',
        'C:\\Windows\\Fonts\\calibri.ttf',
        'C:\\Windows\\Fonts\\segoeui.ttf',
        
        # macOS paths
        '/System/Library/Fonts/Arial.ttf',
        '/Library/Fonts/Arial.ttf',
        '/System/Library/Fonts/Helvetica.ttc',
    ]
    
    for font_path in font_paths:
        try:
            # توسيع مسار المستخدم
            expanded_path = os.path.expanduser(font_path)
            
            if os.path.exists(expanded_path):
                # تسجيل الخط
                font_name = f"Arabic-{os.path.basename(font_path).split('.')[0]}"
                pdfmetrics.registerFont(TTFont(font_name, expanded_path))
                print(f"✅ تم تسجيل الخط: {font_name} من {expanded_path}")
                return font_name
        except Exception as e:
            print(f"❌ فشل تسجيل الخط {font_path}: {str(e)}")
            continue
    
    print("⚠️ لم يتم العثور على خطوط عربية مناسبة")
    return None

def test_arabic_fonts():
    """اختبار الخطوط العربية المتاحة"""
    test_text = "إيصال دفع - Kitchen Factory"
    
    print("🔍 اختبار الخطوط العربية:")
    print(f"النص التجريبي: {test_text}")
    
    # اختبار معالجة النص
    try:
        reshaped = reshape(test_text)
        bidi_text = get_display(reshaped)
        print(f"✅ معالجة النص: {bidi_text}")
    except Exception as e:
        print(f"❌ فشل معالجة النص: {str(e)}")
    
    # اختبار تسجيل الخطوط
    font_name = register_arabic_fonts()
    if font_name:
        print(f"✅ الخط المسجل: {font_name}")
    else:
        print("❌ لم يتم تسجيل أي خط")
    
    return font_name

def format_arabic_text(text):
    """تنسيق النص العربي مع معالجة أفضل للأخطاء"""
    if not text or not isinstance(text, str):
        return ""
    
    try:
        # تنظيف النص
        cleaned_text = text.strip()
        if not cleaned_text:
            return ""
        
        # معالجة النص العربي
        reshaped_text = reshape(cleaned_text)
        bidi_text = get_display(reshaped_text)
        
        # التحقق من النتيجة
        if bidi_text and len(bidi_text) > 0:
            return bidi_text
        else:
            print(f"⚠️ فشل في معالجة النص: {text}")
            return cleaned_text
            
    except Exception as e:
        print(f"❌ خطأ في تنسيق النص العربي '{text}': {str(e)}")
        return text

# دالة لإنشاء إيصال قبض PDF
# تم تعليق الدالة القديمة واستبدالها بـ generate_receipt_pdf_v2 - 2025-10-19
# def generate_receipt_pdf(order, payment_amount=None, payment_type_ar='عربون', receipt_number=None):
#     """إنشاء إيصال قبض PDF مع دعم كامل للغة العربية - الإصدار القديم"""
#     buffer = io.BytesIO()
#     
#     # إنشاء مستند PDF
#     p = canvas.Canvas(buffer, pagesize=A4)
#     width, height = A4
#     
#     # تسجيل الخط العربي مع fallback محسن
#     arabic_font = register_arabic_fonts()
#     
#     # تحسين اختيار الخط
#     if arabic_font:
#         font_name = arabic_font
#         print(f"✅ استخدام الخط العربي: {font_name}")
#     else:
#         # fallback للخطوط المتاحة
#         available_fonts = ['Helvetica-Bold', 'Helvetica', 'Times-Bold', 'Times-Roman']
#         font_name = available_fonts[0]  # استخدام أول خط متاح
#         print(f"⚠️ استخدام الخط الافتراضي: {font_name}")
#     
#     # رأس الإيصال
#     p.setFont(font_name, 16)
#     
#     # العنوان (بالإنجليزية)
#     title_text = "Kitchen Factory"
#     title_width = p.stringWidth(title_text, font_name, 16)
#     p.drawString((width - title_width) / 2, height - 2*cm, title_text)
#     
#     # العنوان الفرعي (عربي + إنجليزي)
#     subtitle_ar = format_arabic_text("ايصال قبض")
#     subtitle_text = f"Receipt / {subtitle_ar}"
#     subtitle_width = p.stringWidth(subtitle_text, font_name, 14)
#     p.setFont(font_name, 14)
#     p.drawString((width - subtitle_width) / 2, height - 2.8*cm, subtitle_text)
#     
#     # اسم الصالة
#     if order.showroom:
#         showroom_label = format_arabic_text("الصالة")
#         showroom_text = f"Showroom / {showroom_label}: {order.showroom.name}"
#         showroom_width = p.stringWidth(showroom_text, font_name, 11)
#         p.setFont(font_name, 11)
#         p.drawString((width - showroom_width) / 2, height - 3.5*cm, showroom_text)
#     
#     # رقم الإيصال
#     if receipt_number:
#         receipt_label = format_arabic_text("رقم الإيصال")
#         p.setFont(font_name, 10)
#         p.drawString(2*cm, height - 4*cm, f"Receipt No / {receipt_label}: {receipt_number}")
#     
#     # معلومات الإيصال
#     y_position = height - 5.3*cm
#     p.setFont(font_name, 12)
#     
#     # رقم الطلب
#     order_label = format_arabic_text("رقم الطلب")
#     p.drawString(2*cm, y_position, f"Order ID / {order_label}: {order.id}")
#     y_position -= 0.8*cm
#     
#     # اسم العميل
#     customer_label = format_arabic_text("العميل")
#     p.drawString(2*cm, y_position, f"Customer / {customer_label}: {order.customer.name}")
#     y_position -= 0.8*cm
#     
#     # تاريخ الإيصال
#     date_label = format_arabic_text("التاريخ")
#     p.drawString(2*cm, y_position, f"Date / {date_label}: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
#     y_position -= 0.8*cm
#     
#     # نوع الدفع (مع دعم أنواع متعددة)
#     payment_type_label = format_arabic_text("نوع الدفع")
#     payment_type_formatted = format_arabic_text(payment_type_ar)
#     
#     # الترجمة الإنجليزية
#     payment_type_en = {
#         'عربون': 'Deposit',
#         'دفعة': 'Payment',
#         'باقي المبلغ': 'Final Payment'
#     }.get(payment_type_ar, 'Payment')
#     
#     p.drawString(2*cm, y_position, f"Payment Type / {payment_type_label}: {payment_type_en} / {payment_type_formatted}")
#     y_position -= 1*cm
#     
#     # التفاصيل المالية
#     financial_label = format_arabic_text("التفاصيل المالية")
#     p.setFont(font_name, 13)
#     p.drawString(2*cm, y_position, f"Financial Details / {financial_label}:")
#     y_position -= 0.8*cm
#     
#     p.setFont(font_name, 11)
#     currency_label = format_arabic_text("دينار ليبي")
#     
#     # قيمة الطلبية
#     order_value_label = format_arabic_text("قيمة الطلبية")
#     p.drawString(2.5*cm, y_position, f"Order Value / {order_value_label}: {order.total_value:.2f} LYD / {currency_label}")
#     y_position -= 0.6*cm
#     
#     # إجمالي المدفوعات
#     total_paid_label = format_arabic_text("إجمالي المدفوعات")
#     p.drawString(2.5*cm, y_position, f"Total Paid / {total_paid_label}: {order.total_paid:.2f} LYD / {currency_label}")
#     y_position -= 0.6*cm
#     
#     # المتبقي
#     remaining_label = format_arabic_text("المتبقي")
#     p.drawString(2.5*cm, y_position, f"Remaining / {remaining_label}: {order.remaining_amount:.2f} LYD / {currency_label}")
#     y_position -= 0.8*cm
#     
#     # هذه الدفعة
#     if payment_amount:
#         p.setFont(font_name, 13)
#         this_payment_label = format_arabic_text("هذه الدفعة")
#         p.drawString(2*cm, y_position, f"This Payment / {this_payment_label}: {payment_amount:.2f} LYD / {currency_label}")
#         y_position -= 1*cm
#     
#     # حالة الدفع
#     p.setFont(font_name, 12)
#     payment_status_label = format_arabic_text("حالة الدفع")
#     status_ar = format_arabic_text(order.payment_status)
#     p.drawString(2*cm, y_position, f"Payment Status / {payment_status_label}: {status_ar}")
#     y_position -= 0.8*cm
#     
#     # المستلم
#     received_by_label = format_arabic_text("المستلم")
#     p.drawString(2*cm, y_position, f"Received by / {received_by_label}: {current_user.username}")
#     y_position -= 1.5*cm
#     
#     # خط فاصل
#     p.line(2*cm, y_position, width - 2*cm, y_position)
#     y_position -= 1*cm
#     
#     # ملاحظة
#     note_label = format_arabic_text("هذا إيصال مُنشأ بواسطة الكمبيوتر")
#     p.setFont(font_name, 9)
#     p.drawString(2*cm, y_position, "This is a computer generated receipt.")
#     p.drawString(2*cm, y_position - 0.5*cm, note_label)
#     
#     # إنهاء المستند
#     p.showPage()
#     p.save()
#     
#     buffer.seek(0)
#     return buffer

def number_to_arabic_words(number):
    """تحويل الأرقام إلى كلمات عربية - مضاف 2025-10-19"""
    ones = ['', 'واحد', 'اثنان', 'ثلاثة', 'أربعة', 'خمسة', 'ستة', 'سبعة', 'ثمانية', 'تسعة']
    tens = ['', '', 'عشرون', 'ثلاثون', 'أربعون', 'خمسون', 'ستون', 'سبعون', 'ثمانون', 'تسعون']
    hundreds = ['', 'مائة', 'مائتان', 'ثلاثمائة', 'أربعمائة', 'خمسمائة', 'ستمائة', 'سبعمائة', 'ثمانمائة', 'تسعمائة']
    thousands = ['', 'ألف', 'ألفان', 'ثلاثة آلاف', 'أربعة آلاف', 'خمسة آلاف', 'ستة آلاف', 'سبعة آلاف', 'ثمانية آلاف', 'تسعة آلاف']
    ten_thousands = ['', 'عشرة آلاف', 'عشرون ألف', 'ثلاثون ألف', 'أربعون ألف', 'خمسون ألف', 'ستون ألف', 'سبعون ألف', 'ثمانون ألف', 'تسعون ألف']
    
    if number == 0:
        return 'صفر'
    
    if number < 10:
        return ones[int(number)]
    
    if number < 100:
        ten = int(number / 10)
        one = int(number % 10)
        if one == 0:
            return tens[ten]
        return tens[ten] + ' و' + ones[one]
    
    if number < 1000:
        hundred = int(number / 100)
        remainder = number % 100
        if remainder == 0:
            return hundreds[hundred]
        return hundreds[hundred] + ' و' + number_to_arabic_words(remainder)
    
    if number < 10000:
        thousand = int(number / 1000)
        remainder = number % 1000
        if remainder == 0:
            return thousands[thousand]
        return thousands[thousand] + ' و' + number_to_arabic_words(remainder)
    
    if number < 100000:
        ten_thousand = int(number / 10000)
        remainder = number % 10000
        if remainder == 0:
            return ten_thousands[ten_thousand]
        return ten_thousands[ten_thousand] + ' و' + number_to_arabic_words(remainder)
    
    # للأرقام الأكبر، استخدم التنسيق العددي
    return str(int(number))

def generate_receipt_pdf_v2(order, payment, customer_name=None):
    """إنشاء إيصال قبض PDF بالتصميم الجديد - مضاف 2025-10-19"""
    buffer = io.BytesIO()
    
    # إنشاء مستند PDF
    p = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    
    # تسجيل الخط العربي
    arabic_font = register_arabic_fonts()
    if arabic_font:
        font_name = arabic_font
    else:
        font_name = 'Helvetica'
    
    # ========== 1. معلومات الصالة ==========
    y_position = height - 2*cm
    
    # صندوق معلومات الصالة
    p.setFillColorRGB(0.95, 0.95, 0.95)
    p.rect(width/2 - 4*cm, y_position - 2.5*cm, 8*cm, 2.5*cm, fill=1, stroke=1)
    p.setFillColorRGB(0, 0, 0)
    
    # اسم الصالة
    p.setFont(font_name, 16)
    showroom_name = order.showroom.name if order.showroom else "الصالة الرئيسية"
    showroom_text = format_arabic_text(showroom_name)
    p.drawCentredString(width/2, y_position - 0.8*cm, showroom_text)
    
    # رقم الهاتف والعنوان
    p.setFont(font_name, 10)
    if order.showroom and order.showroom.phone:
        phone_text = format_arabic_text(f"هاتف: {order.showroom.phone}")
        p.drawCentredString(width/2, y_position - 1.4*cm, phone_text)
    
    if order.showroom and order.showroom.address:
        address_text = format_arabic_text(f"العنوان: {order.showroom.address}")
        p.drawCentredString(width/2, y_position - 1.8*cm, address_text)
    
    y_position -= 3*cm
    
    # ========== 2. عنوان الإيصال ==========
    p.setFont(font_name, 22)
    title = format_arabic_text("إيصال قبض")
    p.drawCentredString(width/2, y_position, title)
    
    y_position -= 1.5*cm
    
    # ========== 3. الشريط الأزرق ==========
    # رسم المستطيل الأزرق
    p.setFillColorRGB(0, 0.47, 1)  # أزرق
    p.rect(2*cm, y_position - 2*cm, width - 4*cm, 2*cm, fill=1, stroke=0)
    
    # النصوص داخل الشريط الأزرق
    p.setFillColorRGB(1, 1, 1)  # أبيض
    p.setFont(font_name, 11)
    
    # رقم الطلب - تم تحسين المحاذاة 2025-10-19
    order_label = format_arabic_text("رقم الطلب")
    order_label_width = p.stringWidth(order_label, font_name, 11)
    p.drawString(width - 3*cm - order_label_width/2, y_position - 0.7*cm, order_label)
    p.setFont(font_name, 14)
    order_number_width = p.stringWidth(str(order.id), font_name, 14)
    p.drawString(width - 3*cm - order_number_width/2, y_position - 1.3*cm, str(order.id))
    
    # التاريخ
    p.setFont(font_name, 11)
    date_label = format_arabic_text("التاريخ")
    p.drawCentredString(width/2, y_position - 0.7*cm, date_label)
    p.setFont(font_name, 14)
    date_str = payment.payment_date.strftime('%Y-%m-%d') if hasattr(payment.payment_date, 'strftime') else str(payment.payment_date)
    p.drawCentredString(width/2, y_position - 1.3*cm, date_str)
    
    # تم الاستلام من
    p.setFont(font_name, 11)
    customer_label = format_arabic_text("تم الاستلام من")
    p.drawString(3*cm, y_position - 0.7*cm, customer_label)
    p.setFont(font_name, 14)
    customer_display = customer_name or (order.customer.name if order.customer else "")
    customer_formatted = format_arabic_text(customer_display)
    p.drawString(3*cm, y_position - 1.3*cm, customer_formatted)
    
    p.setFillColorRGB(0, 0, 0)  # العودة للون الأسود
    y_position -= 3*cm
    
    # ========== 4. تفاصيل الدفع ==========
    # صندوق تفاصيل الدفع
    p.setFillColorRGB(0.97, 0.97, 0.97)
    p.rect(2*cm, y_position - 5*cm, width - 4*cm, 5*cm, fill=1, stroke=1)
    p.setFillColorRGB(0, 0, 0)
    
    p.setFont(font_name, 12)
    detail_y = y_position - 1*cm
    
    # مبلغ وقدره
    amount_label = format_arabic_text("مبلغ وقدره:")
    p.drawString(width - 5*cm, detail_y, amount_label)
    
    p.setFont(font_name, 16)
    p.setFillColorRGB(0, 0.47, 1)
    amount_text = f"{payment.amount:.2f} " + format_arabic_text("دينار ليبي")
    p.drawString(3*cm, detail_y, amount_text)
    p.setFillColorRGB(0, 0, 0)
    
    detail_y -= 1*cm
    
    # المبلغ بالحروف
    p.setFont(font_name, 12)
    words_label = format_arabic_text("المبلغ بالحروف:")
    p.drawString(width - 5*cm, detail_y, words_label)
    
    p.setFont(font_name, 11)
    amount_words = number_to_arabic_words(int(payment.amount))
    amount_words_formatted = format_arabic_text(amount_words + " دينار ليبي")
    p.drawString(3*cm, detail_y, amount_words_formatted)
    
    detail_y -= 1*cm
    
    # الغرض
    p.setFont(font_name, 12)
    purpose_label = format_arabic_text("الغرض:")
    p.drawString(width - 5*cm, detail_y, purpose_label)
    
    p.setFont(font_name, 11)
    purpose_text = format_arabic_text(f"{payment.payment_type} طلب مطبخ رقم {order.id}")
    p.drawString(3*cm, detail_y, purpose_text)
    
    detail_y -= 1*cm
    
    # طريقة الدفع
    p.setFont(font_name, 12)
    method_label = format_arabic_text("طريقة الدفع:")
    p.drawString(width - 5*cm, detail_y, method_label)
    
    # عرض طريقة الدفع مع تمييز المحدد
    p.setFont(font_name, 11)
    methods = ['نقداً', 'شيك', 'تحويل مالي']
    method_x = 3*cm
    for method in methods:
        if payment.payment_method and method in payment.payment_method:
            # طريقة الدفع المحددة
            p.setFillColorRGB(0, 0.47, 1)
            p.setFont(font_name, 12)
            method_formatted = format_arabic_text(f"✓ {method}")
            p.drawString(method_x, detail_y, method_formatted)
            p.setFillColorRGB(0, 0, 0)
            p.setFont(font_name, 11)
        else:
            # طريقة دفع غير محددة
            p.setFillColorRGB(0.6, 0.6, 0.6)
            method_formatted = format_arabic_text(method)
            p.drawString(method_x, detail_y, method_formatted)
            p.setFillColorRGB(0, 0, 0)
        method_x += 4*cm
    
    y_position -= 6*cm
    
    # ========== 5. باقي القيمة ==========
    # حساب باقي القيمة
    total_paid = sum(p.amount for p in order.payments)
    remaining = order.total_value - total_paid
    
    # صندوق باقي القيمة
    p.setStrokeColorRGB(0.2, 0.2, 0.2)
    p.setLineWidth(2)
    p.rect(width/2 - 4*cm, y_position - 2.5*cm, 8*cm, 2.5*cm, fill=0, stroke=1)
    
    # عنوان
    p.setFont(font_name, 14)
    remaining_label = format_arabic_text("باقي القيمة")
    p.drawCentredString(width/2, y_position - 1*cm, remaining_label)
    
    # المبلغ - تم تحسين التخطيط لحل التداخل 2025-10-19
    p.setFont(font_name, 18)  # تصغير الخط قليلاً
    p.setFillColorRGB(0, 0.47, 1)
    
    # حساب المسافات لتجنب التداخل
    currency_text = "LYD"
    amount_text = f"{remaining:.2f}"
    symbol_text = format_arabic_text("د.")
    
    currency_width = p.stringWidth(currency_text, font_name, 18)
    amount_width = p.stringWidth(amount_text, font_name, 18)
    symbol_width = p.stringWidth(symbol_text, font_name, 18)
    
    # توزيع العناصر مع مسافات مناسبة
    start_x = width/2 - 2*cm
    p.drawString(start_x, y_position - 1.9*cm, currency_text)
    p.drawString(start_x + currency_width + 0.3*cm, y_position - 1.9*cm, amount_text)
    p.drawString(start_x + currency_width + amount_width + 0.6*cm, y_position - 1.9*cm, symbol_text)
    
    p.setFillColorRGB(0, 0, 0)
    
    y_position -= 4*cm
    
    # ========== 6. التوقيعات ==========
    # صندوق التوقيعات
    p.setFillColorRGB(0.97, 0.97, 0.97)
    p.rect(2*cm, y_position - 3*cm, width - 4*cm, 3*cm, fill=1, stroke=1)
    p.setFillColorRGB(0, 0, 0)
    
    # اسم المستلم - تم تحسين المحاذاة 2025-10-19
    p.setFont(font_name, 12)
    recipient_label = format_arabic_text("اسم المستلم")
    recipient_label_width = p.stringWidth(recipient_label, font_name, 12)
    p.drawString(width - 5*cm - recipient_label_width/2, y_position - 1*cm, recipient_label)
    
    p.setFont(font_name, 11)
    recipient_name = format_arabic_text(payment.received_by if payment.received_by else current_user.username)
    recipient_name_width = p.stringWidth(recipient_name, font_name, 11)
    p.drawString(width - 5*cm - recipient_name_width/2, y_position - 1.8*cm, recipient_name)
    
    # خط التوقيع - محاذاة مع النص أعلاه
    line_start = width - 5*cm - recipient_name_width/2
    line_end = line_start + max(recipient_name_width, 3*cm)
    p.line(line_start, y_position - 2*cm, line_end, y_position - 2*cm)
    
    # توقيع المستلم
    p.setFont(font_name, 12)
    signature_label = format_arabic_text("توقيع المستلم")
    p.drawString(4*cm, y_position - 1*cm, signature_label)
    
    # خط التوقيع
    p.line(4*cm, y_position - 2*cm, 4*cm + 4*cm, y_position - 2*cm)
    
    # ========== 7. رقم الإيصال والملاحظات ==========
    y_position -= 4*cm
    
    # رقم الإيصال
    if payment.receipt_number:
        p.setFont(font_name, 9)
        receipt_label = format_arabic_text("رقم الإيصال:")
        p.drawString(2*cm, y_position, f"{receipt_label} {payment.receipt_number}")
    
    # ملاحظة
    p.setFont(font_name, 8)
    note = format_arabic_text("هذا إيصال مُنشأ بواسطة الكمبيوتر ولا يحتاج لتوقيع")
    p.drawCentredString(width/2, y_position - 0.5*cm, note)
    
    # إنهاء المستند
    p.showPage()
    p.save()
    
    buffer.seek(0)
    return buffer

# مسار جديد لموظف الاستقبال لاستلام العربون وإصدار إيصال
@app.route('/order/<int:order_id>/receive-deposit', methods=['POST'])
@login_required
def receive_deposit(order_id):
    if current_user.role not in ['مدير', 'موظف استقبال']:
        flash('ليس لديك صلاحية لاستلام العربون', 'danger')
        return redirect(url_for('order_detail', order_id=order_id))
    
    try:
        order = db.get_or_404(Order, order_id)
        
        # البحث عن مرحلة التصميم واستلام العربون
        design_stage = Stage.query.filter_by(order_id=order_id, stage_name='تصميم').first()
        deposit_stage = Stage.query.filter_by(order_id=order_id, stage_name='استلام العربون').first()
        
        # التحقق من أن مرحلة التصميم مكتملة
        if not design_stage or design_stage.progress < 100:
            flash('يجب إكمال مرحلة التصميم أولاً قبل استلام العربون', 'warning')
            return redirect(url_for('order_detail', order_id=order_id))
        
        # التحقق من وجود مرحلة استلام العربون
        if not deposit_stage:
            flash('مرحلة استلام العربون غير موجودة في هذا الطلب', 'danger')
            return redirect(url_for('order_detail', order_id=order_id))
        
        # التحقق من أن العربون لم يتم استلامه بعد
        if deposit_stage.progress == 100:
            flash('تم استلام العربون مسبقاً لهذا الطلب', 'warning')
            return redirect(url_for('order_detail', order_id=order_id))
        
        # الحصول على مبلغ العربون من النموذج
        deposit_amount = float(request.form.get('deposit_amount', 0))
        payment_method = request.form.get('payment_method', 'نقد')
        payment_notes = request.form.get('payment_notes', '')
        
        # التحقق من صحة مبلغ العربون
        if deposit_amount <= 0:
            flash('يجب إدخال مبلغ العربون', 'danger')
            return redirect(url_for('order_detail', order_id=order_id))
        
        if deposit_amount > order.total_value:
            flash('مبلغ العربون لا يمكن أن يكون أكبر من قيمة الطلبية', 'warning')
            return redirect(url_for('order_detail', order_id=order_id))

        # إكتمال مرحلة استلام العربون
        deposit_stage.start_date = datetime.now().date()
        deposit_stage.progress = 100
        deposit_stage.end_date = datetime.now().date()
        deposit_stage.assigned_to = current_user.username
        deposit_stage.notes = f"تم استلام العربون بقيمة {deposit_amount} دينار ليبي بواسطة: {current_user.username}"
        
        # تسجيل دفعة العربون
        payment = Payment(
            order_id=order_id,
            amount=deposit_amount,
            payment_type='عربون',
            payment_method=payment_method,
            payment_date=datetime.now().date(),
            notes=payment_notes,
            received_by=current_user.username,
            receipt_number=f"REC_{order_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            showroom_id=order.showroom_id  # إضافة showroom_id من الطلب
        )
        db.session.add(payment)
        
        # بدء مرحلة القطع تلقائياً
        cutting_stage = Stage.query.filter_by(order_id=order_id, stage_name='قطع').first()
        if cutting_stage and not cutting_stage.start_date:
            cutting_stage.start_date = datetime.now().date()
            cutting_stage.notes = f"تم بدء مرحلة القطع تلقائياً بعد استلام العربون"
        
        # تحديث حالة الطلب
        if order.status == 'مفتوح':
            order.status = 'قيد التنفيذ'
            order.start_date = datetime.now().date()
        
        db.session.commit()
        
        # إنشاء إيصال PDF بالتصميم الجديد - تم التحديث 2025-10-19
        receipt_pdf = generate_receipt_pdf_v2(
            order=order,
            payment=payment,
            customer_name=order.customer.name if order.customer else None
        )
        
        # حفظ PDF في مجلد uploads مؤقتاً
        import os
        pdf_filename = f'receipt_order_{order.id}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.pdf'
        pdf_path = os.path.join(app.config['UPLOAD_FOLDER'], pdf_filename)
        
        # حفظ الملف
        with open(pdf_path, 'wb') as f:
            f.write(receipt_pdf.getvalue())
        
        flash(f'تم استلام العربون بقيمة {deposit_amount} دينار ليبي وإصدار الإيصال', 'success')
        
        # إعادة التوجيه لصفحة الطلب مع رابط PDF لفتحه تلقائياً
        return redirect(url_for('order_detail', order_id=order_id, print_receipt=pdf_filename))
        
    except Exception as e:
        db.session.rollback()
        flash(f'حدث خطأ: {str(e)}', 'danger')
        return redirect(url_for('order_detail', order_id=order_id))

@app.route('/test-fonts')
@login_required
def test_fonts():
    """اختبار الخطوط العربية"""
    if current_user.role not in ['مدير']:
        flash('ليس لديك صلاحية لاختبار الخطوط', 'danger')
        return redirect(url_for('dashboard'))
    
    try:
        # اختبار الخطوط
        font_name = test_arabic_fonts()
        
        if font_name:
            flash(f'تم العثور على خط عربي: {font_name}', 'success')
        else:
            flash('لم يتم العثور على خطوط عربية مناسبة', 'warning')
        
        return redirect(url_for('dashboard'))
    except Exception as e:
        flash(f'خطأ في اختبار الخطوط: {str(e)}', 'danger')
        return redirect(url_for('dashboard'))

@app.route('/download-receipt/<filename>')
@login_required
def download_receipt(filename):
    """تحميل إيصال من مجلد uploads"""
    try:
        import os
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        
        if os.path.exists(file_path):
            return send_file(
                file_path,
                as_attachment=True,
                download_name=filename,
                mimetype='application/pdf'
            )
        else:
            flash('الإيصال غير موجود', 'danger')
            return redirect(url_for('dashboard'))
    except Exception as e:
        flash(f'خطأ في تحميل الإيصال: {str(e)}', 'danger')
        return redirect(url_for('dashboard'))

# مسار جديد لموظف الاستقبال لإكتمال مرحلة التصميم
@app.route('/order/<int:order_id>/complete-design', methods=['POST'])
@login_required
def complete_design_stage(order_id):
    if current_user.role not in ['مدير', 'موظف استقبال']:
        flash('ليس لديك صلاحية لإكتمال مرحلة التصميم', 'danger')
        return redirect(url_for('order_detail', order_id=order_id))
    
    try:
        order = db.get_or_404(Order, order_id)
        
        # البحث عن مرحلة التصميم
        design_stage = Stage.query.filter_by(order_id=order_id, stage_name='تصميم').first()
        
        # التحقق من وجود مرحلة التصميم
        if not design_stage:
            flash('مرحلة التصميم غير موجودة في هذا الطلب', 'danger')
            return redirect(url_for('order_detail', order_id=order_id))
        
        # التحقق من أن مرحلة التصميم بدأت بالفعل
        if not design_stage.start_date:
            flash('يجب بدء مرحلة التصميم أولاً قبل إكتمالها', 'warning')
            return redirect(url_for('order_detail', order_id=order_id))
        
        # إكتمال مرحلة التصميم
        design_stage.progress = 100
        design_stage.end_date = datetime.now().date()
        design_stage.assigned_to = current_user.username  # تعيين الموظف المسؤول تلقائياً
        design_stage.notes = f"تم إكتمال التصميم بواسطة: {current_user.username}"
        
        # بدء مرحلة استلام العربون تلقائياً
        deposit_stage = Stage.query.filter_by(order_id=order_id, stage_name='استلام العربون').first()
        if deposit_stage and not deposit_stage.start_date:
            deposit_stage.start_date = datetime.now().date()
            deposit_stage.assigned_to = current_user.username  # تعيين الموظف المسؤول تلقائياً
            deposit_stage.notes = f"تم بدء مرحلة استلام العربون تلقائياً بعد إكتمال التصميم"
        
        db.session.commit()
        flash('تم إكتمال مرحلة التصميم بنجاح وبدء مرحلة استلام العربون', 'success')
        return redirect(url_for('order_detail', order_id=order_id))
        
    except Exception as e:
        db.session.rollback()
        flash(f'حدث خطأ: {str(e)}', 'danger')
        return redirect(url_for('order_detail', order_id=order_id))

# دالة تحميل الملفات المرفوعة
@app.route('/download/<filename>')
@login_required
def download_file(filename):
    """تحميل الملفات المرفوعة مع الطلبات"""
    try:
        # التحقق من وجود الملف
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        if not os.path.exists(file_path):
            flash('الملف المطلوب غير موجود', 'danger')
            return redirect(url_for('orders'))
        
        # التحقق من أن الملف مرتبط بطلب في قاعدة البيانات
        document = Document.query.filter_by(file_path=filename).first()
        if not document:
            flash('ليس لديك صلاحية للوصول إلى هذا الملف', 'danger')
            return redirect(url_for('orders'))
        
        # إرسال الملف للتحميل
        return send_file(
            file_path,
            as_attachment=True,
            download_name=filename
        )
        
    except Exception as e:
        flash(f'حدث خطأ في تحميل الملف: {str(e)}', 'danger')
        return redirect(url_for('orders'))

# دالة إضافة مرفق جديد للطلب
@app.route('/order/<int:order_id>/add-document', methods=['POST'])
@login_required
def add_document(order_id):
    """إضافة مرفق جديد للطلب"""
    if current_user.role not in ['مدير', 'موظف استقبال']:
        flash('ليس لديك صلاحية لإضافة مرفقات', 'danger')
        return redirect(url_for('order_detail', order_id=order_id))
    
    try:
        order = db.get_or_404(Order, order_id)
        
        # التحقق من حالة الطلب والمرحلة
        deposit_stage = Stage.query.filter_by(order_id=order_id, stage_name='استلام العربون').first()
        
        # إذا تم استلام العربون، لا يمكن للموظف استقبال إضافة مرفقات
        if (current_user.role == 'موظف استقبال' and 
            deposit_stage and deposit_stage.progress == 100):
            flash('لا يمكن إضافة مرفقات بعد استلام العربون', 'warning')
            return redirect(url_for('order_detail', order_id=order_id))
        
        # رفع الملف الجديد
        if 'file' not in request.files:
            flash('لم يتم اختيار ملف', 'danger')
            return redirect(url_for('order_detail', order_id=order_id))
        
        file = request.files['file']
        if file.filename == '':
            flash('لم يتم اختيار ملف', 'danger')
            return redirect(url_for('order_detail', order_id=order_id))
        
        if file:
            original_filename = secure_filename(file.filename)
            # تنظيف اسم الزبون للاستخدام في اسم الملف
            safe_customer_name = clean_customer_name(order.customer.name)
            # إضافة معرف الطلب واسم الزبون إلى اسم الملف
            filename = f"order_{order.id}_{safe_customer_name}_{original_filename}"
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(file_path)

            # حفظ مسار الملف في قاعدة البيانات
            document = Document(
                order_id=order.id, 
                file_path=filename,
                showroom_id=order.showroom_id
            )
            db.session.add(document)
            db.session.commit()
            
            flash('تم إضافة المرفق بنجاح', 'success')
        
        return redirect(url_for('order_detail', order_id=order_id))
        
    except Exception as e:
        db.session.rollback()
        flash(f'حدث خطأ في إضافة المرفق: {str(e)}', 'danger')
        return redirect(url_for('order_detail', order_id=order_id))

# دالة حذف مرفق من الطلب
@app.route('/order/<int:order_id>/delete-document/<int:document_id>', methods=['POST'])
@login_required
def delete_document(order_id, document_id):
    """حذف مرفق من الطلب"""
    if current_user.role not in ['مدير', 'موظف استقبال']:
        flash('ليس لديك صلاحية لحذف مرفقات', 'danger')
        return redirect(url_for('order_detail', order_id=order_id))
    
    try:
        order = db.get_or_404(Order, order_id)
        document = db.get_or_404(Document, document_id)
        
        # التحقق من أن المرفق ينتمي للطلب
        if document.order_id != order_id:
            flash('المرفق غير مرتبط بهذا الطلب', 'danger')
            return redirect(url_for('order_detail', order_id=order_id))
        
        # التحقق من حالة الطلب والمرحلة
        deposit_stage = Stage.query.filter_by(order_id=order_id, stage_name='استلام العربون').first()
        
        # إذا تم استلام العربون، لا يمكن للموظف استقبال حذف مرفقات
        if (current_user.role == 'موظف استقبال' and 
            deposit_stage and deposit_stage.progress == 100):
            flash('لا يمكن حذف مرفقات بعد استلام العربون', 'warning')
            return redirect(url_for('order_detail', order_id=order_id))
        
        # حذف الملف من نظام الملفات
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], document.file_path)
        if os.path.exists(file_path):
            os.remove(file_path)
        
        # حذف السجل من قاعدة البيانات
        db.session.delete(document)
        db.session.commit()
        
        flash('تم حذف المرفق بنجاح', 'success')
        return redirect(url_for('order_detail', order_id=order_id))
        
    except Exception as e:
        db.session.rollback()
        flash(f'حدث خطأ في حذف المرفق: {str(e)}', 'danger')
        return redirect(url_for('order_detail', order_id=order_id))

# دالة إضافة دفعة جديدة
@app.route('/order/<int:order_id>/add-payment', methods=['POST'])
@login_required
def add_payment(order_id):
    """إضافة دفعة جديدة للطلب"""
    if current_user.role not in ['مدير', 'موظف استقبال']:
        flash('ليس لديك صلاحية لإضافة دفعات', 'danger')
        return redirect(url_for('order_detail', order_id=order_id))
    
    try:
        order = db.get_or_404(Order, order_id)
        
        # الحصول على بيانات الدفعة
        amount = float(request.form.get('amount', 0))
        payment_type = request.form.get('payment_type', 'دفعة')
        payment_method = request.form.get('payment_method', 'نقد')
        payment_notes = request.form.get('payment_notes', '')
        
        # التحقق من صحة المبلغ
        if amount <= 0:
            flash('يجب إدخال مبلغ صحيح', 'danger')
            return redirect(url_for('order_detail', order_id=order_id))
        
        # التحقق من عدم تجاوز قيمة الطلبية
        if order.total_paid + amount > order.total_value:
            flash(f'المبلغ يتجاوز قيمة الطلبية. المتبقي: {order.remaining_amount} دينار ليبي', 'warning')
            return redirect(url_for('order_detail', order_id=order_id))
        
        # الحصول على معرف الصالة من الطلب نفسه
        showroom_id = order.showroom_id
        
        # تسجيل الدفعة
        payment = Payment(
            order_id=order_id,
            amount=amount,
            payment_type=payment_type,
            payment_method=payment_method,
            payment_date=datetime.now().date(),
            notes=payment_notes,
            received_by=current_user.username,
            receipt_number=f"REC_{order_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            showroom_id=showroom_id
        )
        db.session.add(payment)
        
        # إذا كانت الدفعة عربون، تحديث مرحلة "استلام العربون" إلى 100%
        if payment_type == 'عربون':
            deposit_stage = Stage.query.filter_by(
                order_id=order_id,
                stage_name='استلام العربون'
            ).first()
            
            if deposit_stage:
                deposit_stage.progress = 100
                deposit_stage.start_date = datetime.now().date()
                deposit_stage.end_date = datetime.now().date()
        
        db.session.commit()
        
        # إنشاء إيصال PDF بالتصميم الجديد - تم التحديث 2025-10-19
        receipt_pdf = generate_receipt_pdf_v2(
            order=order,
            payment=payment,
            customer_name=order.customer.name if order.customer else None
        )
        
        flash(f'تم تسجيل دفعة بقيمة {amount} دينار ليبي وإصدار الإيصال', 'success')
        
        # إرسال ملف PDF للتحميل
        return send_file(
            receipt_pdf,
            as_attachment=True,
            download_name=f'receipt_order_{order.id}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.pdf',
            mimetype='application/pdf'
        )
        
    except Exception as e:
        db.session.rollback()
        flash(f'حدث خطأ في إضافة الدفعة: {str(e)}', 'danger')
        return redirect(url_for('order_detail', order_id=order_id))

@app.route('/order/<int:order_id>/payment/<int:payment_id>/receipt')
@login_required
def payment_receipt_v2(order_id, payment_id):
    """طباعة إيصال دفعة محددة بالتصميم الجديد - مضاف 2025-10-19"""
    try:
        # جلب الطلب والدفعة
        order = db.get_or_404(Order, order_id)
        payment = db.get_or_404(Payment, payment_id)
        
        # التحقق من أن الدفعة تخص الطلب
        if payment.order_id != order.id:
            flash('الدفعة لا تخص هذا الطلب', 'danger')
            return redirect(url_for('order_detail', order_id=order_id))
        
        # التحقق من الصلاحيات
        if current_user.role not in ['مدير', 'موظف استقبال', 'مسؤول إنتاج', 'مسؤول مخزن', 'مسؤول العمليات']:
            flash('ليس لديك صلاحية لعرض الإيصالات', 'danger')
            return redirect(url_for('order_detail', order_id=order_id))
        
        # إنشاء PDF بالتصميم الجديد
        receipt_pdf = generate_receipt_pdf_v2(
            order=order,
            payment=payment,
            customer_name=order.customer.name if order.customer else None
        )
        
        # إرسال الملف
        return send_file(
            receipt_pdf,
            as_attachment=True,
            download_name=f'receipt_{order.id}_{payment.id}_{datetime.now().strftime("%Y%m%d")}.pdf',
            mimetype='application/pdf'
        )
        
    except Exception as e:
        flash(f'حدث خطأ في إنشاء الإيصال: {str(e)}', 'danger')
        return redirect(url_for('order_detail', order_id=order_id))

@app.route('/order/<int:order_id>/costs')
@login_required
def order_costs(order_id):
    if current_user.role not in ['مدير', 'مسؤول إنتاج', 'مسؤول مخزن', 'مسؤول العمليات']:
        flash('ليس لديك صلاحية لإدارة تكاليف الطلب', 'danger')
        return redirect(url_for('order_detail', order_id=order_id))
    
    order = db.get_or_404(Order, order_id)
    return render_template('order_costs.html', order=order)

@app.route('/order/<int:order_id>/add-cost', methods=['POST'])
@login_required
def add_order_cost(order_id):
    if current_user.role not in ['مدير', 'مسؤول إنتاج', 'مسؤول مخزن', 'مسؤول العمليات']:
        flash('ليس لديك صلاحية لإضافة تكاليف للطلب', 'danger')
        return redirect(url_for('order_detail', order_id=order_id))
    
    try:
        cost_type = request.form.get('cost_type')
        description = request.form.get('description')
        amount = float(request.form.get('amount'))
        date = datetime.strptime(request.form.get('date'), '%Y-%m-%d')
        
        # التحقق من وجود البيانات المطلوبة
        if not cost_type or not amount or not date:
            flash('نوع التكلفة والمبلغ والتاريخ مطلوبة', 'danger')
            return redirect(url_for('order_costs', order_id=order_id))
        
        # الحصول على الطلب للوصول إلى showroom_id
        order = db.get_or_404(Order, order_id)
        
        # الحصول على معرف الصالة من الطلب نفسه
        showroom_id = order.showroom_id
        
        # إنشاء سجل التكلفة
        order_cost = OrderCost(
            order_id=order_id,
            cost_type=cost_type,
            description=description,
            amount=amount,
            date=date,
            showroom_id=showroom_id
        )
        
        db.session.add(order_cost)
        db.session.commit()
        
        flash(f'تم إضافة تكلفة {cost_type} بنجاح', 'success')
        return redirect(url_for('order_costs', order_id=order_id))
    except Exception as e:
        db.session.rollback()
        flash(f'حدث خطأ: {str(e)}', 'danger')
        return redirect(url_for('order_costs', order_id=order_id))

@app.route('/order/<int:order_id>/edit', methods=['GET', 'POST'])
@login_required
@require_showroom_access
def edit_order(order_id):
    order = db.get_or_404(Order, order_id)

    if current_user.role not in ['مدير', 'موظف استقبال']:
        flash('ليس لديك صلاحية لتعديل الطلب', 'danger')
        return redirect(url_for('order_detail', order_id=order.id))
    
    # موظف استقبال: يمكنه التعديل فقط قبل مرحلة "حصر متطلبات الطلب"
    if current_user.role == 'موظف استقبال':
        # التحقق من وجود مرحلة "حصر متطلبات الطلب"
        inventory_stage = Stage.query.filter_by(
            order_id=order_id,
            stage_name='حصر متطلبات الطلب'
        ).first()
        
        # إذا بدأت المرحلة أو اكتملت، لا يمكن التعديل
        if inventory_stage and (inventory_stage.start_date or inventory_stage.progress > 0):
            flash('لا يمكن تعديل الطلب بعد بدء مرحلة حصر المتطلبات', 'warning')
            return redirect(url_for('order_detail', order_id=order.id))

    if request.method == 'POST':
        order.delivery_date = datetime.strptime(request.form.get('delivery_date'), '%Y-%m-%d').date() if request.form.get('delivery_date') else None
        order.deadline = datetime.strptime(request.form.get('deadline'), '%Y-%m-%d').date() if request.form.get('deadline') else None
        order.meters = int(request.form.get('meters'))
        order.status = request.form.get('status')

        # تحديث بيانات العميل
        order.customer.name = request.form.get('customer_name')
        order.customer.phone = request.form.get('customer_phone')
        order.customer.address = request.form.get('customer_address')

        db.session.commit()
        flash('تم تحديث الطلب بنجاح', 'success')
        return redirect(url_for('order_detail', order_id=order.id))

    return render_template('edit_order.html', order=order)

@app.route('/order/<int:order_id>/delete', methods=['POST'])
@login_required
@require_showroom_access
def delete_order(order_id):
    order = db.get_or_404(Order, order_id)

    if current_user.role != 'مدير':
        flash('ليس لديك صلاحية لحذف الطلب', 'danger')
        return redirect(url_for('order_detail', order_id=order.id))

    # حذف الملفات المرتبطة بالطلب
    for document in order.documents:
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], document.file_path)
        if os.path.exists(file_path):
            os.remove(file_path)
        # حذف سجل Document من قاعدة البيانات
        db.session.delete(document)

    db.session.delete(order)
    db.session.commit()
    flash('تم حذف الطلب بنجاح', 'success')
    return redirect(url_for('orders'))

# مسارات الأرشفة
@app.route('/order/<int:order_id>/archive', methods=['POST'])
@login_required
@require_showroom_access
def archive_order(order_id):
    """أرشفة طلبية مكتملة - للمديرين فقط"""
    if current_user.role != 'مدير':
        flash('ليس لديك صلاحية لأرشفة الطلبات', 'danger')
        return redirect(url_for('order_detail', order_id=order_id))
    
    order = db.get_or_404(Order, order_id)
    
    # التحقق من أن الطلبية مكتملة
    if order.status not in ['مكتمل', 'مسلّم']:
        flash('يمكن أرشفة الطلبيات المكتملة أو المسلمة فقط', 'warning')
        return redirect(url_for('order_detail', order_id=order_id))
    
    # التحقق من أنها ليست مؤرشفة بالفعل
    if order.is_archived:
        flash('هذه الطلبية مؤرشفة بالفعل', 'info')
        return redirect(url_for('order_detail', order_id=order_id))
    
    # أرشفة الطلبية
    order.is_archived = True
    order.archived_at = datetime.now(timezone.utc)
    order.archived_by = current_user.username
    order.archive_notes = request.form.get('notes', '')
    
    db.session.commit()
    flash(f'تم أرشفة الطلبية رقم {order.id} بنجاح', 'success')
    return redirect(url_for('orders'))

@app.route('/order/<int:order_id>/unarchive', methods=['POST'])
@login_required
@require_showroom_access
def unarchive_order(order_id):
    """إلغاء أرشفة طلبية - للمديرين فقط"""
    if current_user.role != 'مدير':
        flash('ليس لديك صلاحية لإلغاء أرشفة الطلبات', 'danger')
        return redirect(url_for('order_detail', order_id=order_id))
    
    order = db.get_or_404(Order, order_id)
    
    # التحقق من أنها مؤرشفة
    if not order.is_archived:
        flash('هذه الطلبية ليست مؤرشفة', 'info')
        return redirect(url_for('order_detail', order_id=order_id))
    
    # إلغاء الأرشفة
    order.is_archived = False
    order.archived_at = None
    order.archived_by = None
    order.archive_notes = None
    
    db.session.commit()
    flash(f'تم إلغاء أرشفة الطلبية رقم {order.id} بنجاح', 'success')
    return redirect(url_for('order_detail', order_id=order_id))

@app.route('/orders/archived')
@login_required
def archived_orders():
    """عرض الطلبيات المؤرشفة - للمديرين فقط"""
    if current_user.role != 'مدير':
        flash('ليس لديك صلاحية لعرض الطلبيات المؤرشفة', 'danger')
        return redirect(url_for('dashboard'))
    
    # جلب الطلبيات المؤرشفة مع العزل حسب الصالة
    order_query = get_scoped_query(Order, current_user)
    archived_orders = order_query.filter_by(is_archived=True).order_by(Order.archived_at.desc()).all()
    
    return render_template('archived_orders.html', orders=archived_orders)

# مسارات إدارة المواد
@app.route('/materials')
@login_required
def materials():
    """عرض قائمة المواد - المخزن موحد لجميع الصالات"""
    if current_user.role not in ['مدير', 'مسؤول مخزن', 'مسؤول العمليات']:
        flash('ليس لديك صلاحية للوصول إلى صفحة المواد', 'danger')
        return redirect(url_for('dashboard'))

    # المواد موحدة لجميع الصالات (لا عزل)
    materials = Material.query.filter_by(is_active=True).all()
    
    # الحصول على المخازن للعرض
    warehouses = Warehouse.query.filter_by(is_active=True).all()
    
    return render_template('materials.html', materials=materials, warehouses=warehouses)

@app.route('/material/new', methods=['GET', 'POST'])
@login_required
def new_material():
    """إضافة مادة جديدة - مسؤول المخزن ومسؤول الإنتاج"""
    if current_user.role not in ['مدير', 'مسؤول مخزن', 'مسؤول العمليات']:
        flash('ليس لديك صلاحية لإضافة مادة جديدة', 'danger')
        return redirect(url_for('materials'))

    if request.method == 'POST':
        name = request.form.get('name')
        unit = request.form.get('unit')
        quantity = float(request.form.get('quantity'))
        unit_price = float(request.form.get('unit_price', 0))
        warehouse_id = request.form.get('warehouse_id')
        storage_location = request.form.get('storage_location')
        min_quantity = float(request.form.get('min_quantity', 0))
        max_quantity = request.form.get('max_quantity')

        # التحقق من أن سعر الوحدة موجب
        if unit_price < 0:
            flash('سعر الوحدة يجب أن يكون رقمًا موجبًا', 'danger')
            warehouses = Warehouse.query.filter_by(is_active=True).all()
            return render_template('new_material.html', warehouses=warehouses)

        # إذا لم يتم اختيار مخزن، استخدم المخزن الافتراضي
        if not warehouse_id:
            default_warehouse = Warehouse.query.filter_by(is_default=True).first()
            if default_warehouse:
                warehouse_id = default_warehouse.id
            else:
                flash('يجب تحديد المخزن', 'danger')
                warehouses = Warehouse.query.filter_by(is_active=True).all()
                return render_template('new_material.html', warehouses=warehouses)
        
        material = Material(
            name=name, 
            unit=unit, 
            quantity_available=quantity, 
            unit_price=unit_price,
            cost_price=unit_price,  # تعيين التكلفة الافتراضية
            purchase_price=unit_price,  # تعيين سعر الشراء
            warehouse_id=int(warehouse_id),
            storage_location=storage_location,
            min_quantity=min_quantity,
            max_quantity=float(max_quantity) if max_quantity else None
        )
        db.session.add(material)
        db.session.commit()

        flash('تم إضافة المادة بنجاح', 'success')
        return redirect(url_for('materials'))

    warehouses = Warehouse.query.filter_by(is_active=True).all()
    return render_template('new_material.html', warehouses=warehouses)

@app.route('/material/<int:material_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_material(material_id):
    """تعديل مادة - مسؤول المخزن فقط"""
    if current_user.role not in ['مدير', 'مسؤول مخزن', 'مسؤول العمليات']:
        flash('ليس لديك صلاحية لتعديل المادة', 'danger')
        return redirect(url_for('materials'))
    
    material = db.get_or_404(Material, material_id)

    if request.method == 'POST':
        material.name = request.form.get('name')
        material.unit = request.form.get('unit')
        material.quantity_available = float(request.form.get('quantity'))
        unit_price = float(request.form.get('unit_price', 0))
        
        # تحديث المخزن والموقع
        warehouse_id = request.form.get('warehouse_id')
        if warehouse_id:
            material.warehouse_id = int(warehouse_id)
        material.storage_location = request.form.get('storage_location')
        
        # تحديث الحدود الدنيا والقصوى
        material.min_quantity = float(request.form.get('min_quantity', 0))
        max_quantity = request.form.get('max_quantity')
        material.max_quantity = float(max_quantity) if max_quantity else None

        # التحقق من أن سعر الوحدة موجب
        if unit_price < 0:
            flash('سعر الوحدة يجب أن يكون رقمًا موجبًا', 'danger')
            warehouses = Warehouse.query.filter_by(is_active=True).all()
            return render_template('edit_material.html', material=material, warehouses=warehouses)

        # تحديث سعر الوحدة وتاريخ التحديث
        material.unit_price = unit_price
        material.price_updated_at = datetime.now(timezone.utc)

        db.session.commit()
        flash('تم تحديث المادة بنجاح', 'success')
        return redirect(url_for('materials'))

    warehouses = Warehouse.query.filter_by(is_active=True).all()
    return render_template('edit_material.html', material=material, warehouses=warehouses)

@app.route('/material/<int:material_id>/delete', methods=['POST'])
@login_required
def delete_material(material_id):
    """حذف مادة - المدير فقط"""
    if current_user.role != 'مدير':
        flash('ليس لديك صلاحية لحذف المادة', 'danger')
        return redirect(url_for('materials'))
    
    material = db.get_or_404(Material, material_id)

    db.session.delete(material)
    db.session.commit()
    flash('تم حذف المادة بنجاح', 'success')
    return redirect(url_for('materials'))

@app.route('/materials/add-stock', methods=['POST'])
@login_required
def add_stock():
    """إضافة كمية لمادة - مسؤول المخزن فقط"""
    try:
        if current_user.role not in ['مدير', 'مسؤول مخزن', 'مسؤول العمليات']:
            return jsonify({'success': False, 'message': 'ليس لديك صلاحية لإضافة مخزون'})
        
        material_id = request.form.get('material_id')
        quantity_str = request.form.get('quantity')
        batch_date = request.form.get('batch_date')
        
        # التحقق من وجود البيانات المطلوبة
        if not material_id or not quantity_str or not batch_date:
            return jsonify({'success': False, 'message': 'جميع الحقول مطلوبة'})
        
        try:
            quantity = float(quantity_str)
            if quantity <= 0:
                return jsonify({'success': False, 'message': 'الكمية يجب أن تكون رقمًا موجبًا'})
        except ValueError:
            return jsonify({'success': False, 'message': 'الكمية يجب أن تكون رقمًا صحيحًا'})
        
        material = db.session.get(Material, material_id)
        if not material:
            return jsonify({'success': False, 'message': 'المادة المحددة غير موجودة'})
        
        # إضافة الكمية للمخزون
        material.quantity_available += quantity
        
        # إضافة سجل للكمية المضافة
        # هنا يمكن إضافة نموذج جديد لتتبع حركات المخزون إذا لزم الأمر
        
        db.session.commit()
        
        return jsonify({
            'success': True, 
            'message': 'تم إضافة الكمية بنجاح', 
            'new_quantity': material.quantity_available
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'حدث خطأ: {str(e)}'})

@app.route('/material/<int:material_id>/add_stock', methods=['GET', 'POST'])
@login_required
def add_material_stock(material_id):
    """إضافة كمية لمادة محددة - مسؤول المخزن فقط"""
    if current_user.role not in ['مدير', 'مسؤول مخزن', 'مسؤول العمليات']:
        flash('ليس لديك صلاحية لإضافة مخزون', 'danger')
        return redirect(url_for('materials'))

    if request.method == 'POST':
        quantity = float(request.form.get('quantity'))
        material.quantity_available += quantity

        db.session.commit()
        flash(f'تم إضافة {quantity} {material.unit} من {material.name} بنجاح', 'success')
        return redirect(url_for('materials'))

    return render_template('add_material_stock.html', material=material)

# مسارات إدارة المستخدمين
@app.route('/users')
@login_required
def users():
    if current_user.role != 'مدير':
        flash('ليس لديك صلاحية للوصول إلى صفحة المستخدمين', 'danger')
        return redirect(url_for('dashboard'))

    # المديرون يرون جميع المستخدمين، لكن يمكن فلترتهم حسب الصالة
    users = User.query.filter_by(is_active=True).all()
    showrooms = get_all_showrooms()
    return render_template('users.html', users=users, showrooms=showrooms)

@app.route('/user/new', methods=['GET', 'POST'])
@login_required
def new_user():
    if current_user.role != 'مدير':
        flash('ليس لديك صلاحية لإضافة مستخدم جديد', 'danger')
        return redirect(url_for('users'))

    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        role = request.form.get('role')
        showroom_id = request.form.get('showroom_id')

        # التحقق من عدم وجود مستخدم بنفس الاسم
        if User.query.filter_by(username=username).first():
            flash('اسم المستخدم موجود بالفعل', 'danger')
            showrooms = get_all_showrooms()
            return render_template('new_user.html', showrooms=showrooms)

        # الأدوار التي لا ترتبط بصالة محددة
        manager_roles = ['مدير', 'مسؤول مخزن', 'مسؤول إنتاج', 'مسؤول العمليات']
        
        if role in manager_roles:
            # الأدوار الإدارية: showroom_id اختياري (يمكن أن يكون None)
            if showroom_id and showroom_id.strip():
                showroom_id = int(showroom_id)
            else:
                showroom_id = None
        else:
            # موظف استقبال: showroom_id إلزامي
            if not showroom_id:
                flash('يجب اختيار صالة لموظف الاستقبال', 'warning')
                showrooms = get_all_showrooms()
                return render_template('new_user.html', showrooms=showrooms)
            showroom_id = int(showroom_id)

        user = User(
            username=username,
            password=generate_password_hash(password),
            role=role,
            showroom_id=showroom_id
        )
        db.session.add(user)
        db.session.commit()

        flash('تم إضافة المستخدم بنجاح', 'success')
        return redirect(url_for('users'))

    showrooms = get_all_showrooms()
    return render_template('new_user.html', showrooms=showrooms)

@app.route('/user/<int:user_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_user(user_id):
    user = db.get_or_404(User, user_id)

    if current_user.role != 'مدير':
        flash('ليس لديك صلاحية لتعديل المستخدم', 'danger')
        return redirect(url_for('users'))

    if request.method == 'POST':
        username = request.form.get('username')
        role = request.form.get('role')
        password = request.form.get('password')
        showroom_id = request.form.get('showroom_id')

        # التحقق من عدم وجود مستخدم آخر بنفس الاسم
        existing_user = User.query.filter_by(username=username).first()
        if existing_user and existing_user.id != user.id:
            flash('اسم المستخدم موجود بالفعل', 'danger')
            showrooms = get_all_showrooms()
            return render_template('edit_user.html', user=user, showrooms=showrooms)

        # الأدوار التي لا ترتبط بصالة محددة
        manager_roles = ['مدير', 'مسؤول مخزن', 'مسؤول إنتاج', 'مسؤول العمليات']
        
        if role in manager_roles:
            # الأدوار الإدارية: showroom_id اختياري (يمكن أن يكون None)
            if showroom_id and showroom_id.strip():
                showroom_id = int(showroom_id)
            else:
                showroom_id = None
        else:
            # موظف استقبال: showroom_id إلزامي
            if not showroom_id:
                flash('يجب اختيار صالة لموظف الاستقبال', 'warning')
                showrooms = get_all_showrooms()
                return render_template('edit_user.html', user=user, showrooms=showrooms)
            showroom_id = int(showroom_id)

        user.username = username
        user.role = role
        user.showroom_id = showroom_id

        # تحديث كلمة المرور فقط إذا تم إدخال كلمة مرور جديدة
        if password:
            user.password = generate_password_hash(password)

        db.session.commit()
        flash('تم تحديث المستخدم بنجاح', 'success')
        return redirect(url_for('users'))

    showrooms = get_all_showrooms()
    return render_template('edit_user.html', user=user, showrooms=showrooms)

@app.route('/user/<int:user_id>/delete', methods=['POST'])
@login_required
def delete_user(user_id):
    user = db.get_or_404(User, user_id)

    if current_user.role != 'مدير':
        flash('ليس لديك صلاحية لحذف المستخدم', 'danger')
        return redirect(url_for('users'))

    # منع حذف المستخدم الحالي
    if user.id == current_user.id:
        flash('لا يمكنك حذف حسابك الحالي', 'danger')
        return redirect(url_for('users'))

    # Soft Delete: نوقف المستخدم بدلاً من حذفه
    user.is_active = False
    db.session.commit()
    flash('تم تعطيل المستخدم بنجاح', 'success')
    return redirect(url_for('users'))

# ==================== مسارات إدارة الفنيين ====================

@app.route('/technicians')
@login_required
def technicians():
    """صفحة قائمة الفنيين - للمدير ومسؤول الإنتاج ومسؤول العمليات فقط"""
    if current_user.role not in ['مدير', 'مسؤول إنتاج', 'مسؤول العمليات']:
        flash('ليس لديك صلاحية للوصول إلى صفحة الفنيين', 'danger')
        return redirect(url_for('dashboard'))
    
    technicians = Technician.query.all()
    return render_template('technicians.html', technicians=technicians)


@app.route('/technician/new', methods=['GET', 'POST'])
@login_required
def new_technician():
    """إضافة فني جديد - للمدير ومسؤول الإنتاج ومسؤول العمليات"""
    if current_user.role not in ['مدير', 'مسؤول إنتاج', 'مسؤول العمليات']:
        flash('ليس لديك صلاحية لإضافة فني جديد', 'danger')
        return redirect(url_for('technicians'))
    
    # جلب الإعدادات الافتراضية
    default_manufacturing_rate = get_system_setting('default_manufacturing_rate', '50.0', 'float')
    default_installation_rate = get_system_setting('default_installation_rate', '30.0', 'float')
    
    if request.method == 'POST':
        # جمع البيانات من النموذج
        name = request.form.get('name')
        phone = request.form.get('phone')
        email = request.form.get('email')
        national_id = request.form.get('national_id')
        specialization = request.form.get('specialization')
        hire_date = request.form.get('hire_date')
        bank_name = request.form.get('bank_name')
        bank_account = request.form.get('bank_account')
        manufacturing_rate = float(request.form.get('manufacturing_rate', default_manufacturing_rate))
        installation_rate = float(request.form.get('installation_rate', default_installation_rate))
        notes = request.form.get('notes')
        
        # إنشاء كائن الفني
        technician = Technician(
            name=name,
            phone=phone,
            email=email,
            national_id=national_id,
            specialization=specialization,
            status='نشط',  # الحالة الافتراضية
            hire_date=datetime.strptime(hire_date, '%Y-%m-%d').date() if hire_date else None,
            bank_name=bank_name,
            bank_account=bank_account,
            manufacturing_rate_per_meter=manufacturing_rate,
            installation_rate_per_meter=installation_rate,
            notes=notes
        )
        
        db.session.add(technician)
        db.session.commit()
        
        flash(f'تم إضافة الفني {name} بنجاح', 'success')
        return redirect(url_for('technicians'))
    
    return render_template('new_technician.html', 
                          default_manufacturing_rate=default_manufacturing_rate,
                          default_installation_rate=default_installation_rate)


@app.route('/api/technician/<int:technician_id>/rates')
@login_required
def get_technician_rates(technician_id):
    """API: الحصول على أسعار الفني - مضاف 2025-10-18"""
    technician = db.get_or_404(Technician, technician_id)
    
    return jsonify({
        'id': technician.id,
        'name': technician.name,
        'specialty': technician.specialty,
        'manufacturing_rate': float(technician.manufacturing_rate) if technician.manufacturing_rate else 0.0,
        'installation_rate': float(technician.installation_rate) if technician.installation_rate else 0.0
    })


@app.route('/technician/<int:technician_id>')
@login_required
def technician_detail(technician_id):
    """تفاصيل الفني - عرض جميع المعلومات والمستحقات"""
    if current_user.role not in ['مدير', 'مسؤول إنتاج', 'مسؤول العمليات']:
        flash('ليس لديك صلاحية للوصول إلى صفحة تفاصيل الفنيين', 'danger')
        return redirect(url_for('dashboard'))
    
    technician = db.get_or_404(Technician, technician_id)
    
    # جلب المستحقات غير المدفوعة
    pending_dues = TechnicianDue.query.filter_by(technician_id=technician_id, is_paid=False).all()
    
    # جلب سجل الدفعات
    payments = TechnicianPayment.query.filter_by(technician_id=technician_id).order_by(TechnicianPayment.payment_date.desc()).all()
    
    # إحصائيات الأداء
    total_manufacturing_orders = db.session.query(Stage).filter_by(manufacturing_technician_id=technician_id).count()
    total_installation_orders = db.session.query(Stage).filter_by(installation_technician_id=technician_id).count()
    
    return render_template('technician_detail.html', 
                          technician=technician, 
                          pending_dues=pending_dues,
                          payments=payments,
                          total_manufacturing_orders=total_manufacturing_orders,
                          total_installation_orders=total_installation_orders)


@app.route('/technician/<int:technician_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_technician(technician_id):
    """تعديل بيانات الفني"""
    if current_user.role not in ['مدير', 'مسؤول إنتاج', 'مسؤول العمليات']:
        flash('ليس لديك صلاحية لتعديل بيانات الفنيين', 'danger')
        return redirect(url_for('technician_detail', technician_id=technician_id))
    
    technician = db.get_or_404(Technician, technician_id)
    
    if request.method == 'POST':
        technician.name = request.form.get('name')
        technician.phone = request.form.get('phone')
        technician.email = request.form.get('email')
        technician.national_id = request.form.get('national_id')
        technician.specialization = request.form.get('specialization')
        technician.status = request.form.get('status')
        technician.hire_date = datetime.strptime(request.form.get('hire_date'), '%Y-%m-%d').date() if request.form.get('hire_date') else None
        technician.bank_name = request.form.get('bank_name')
        technician.bank_account = request.form.get('bank_account')
        technician.manufacturing_rate_per_meter = float(request.form.get('manufacturing_rate', 0))
        technician.installation_rate_per_meter = float(request.form.get('installation_rate', 0))
        technician.notes = request.form.get('notes')
        
        db.session.commit()
        
        flash(f'تم تحديث بيانات الفني {technician.name} بنجاح', 'success')
        return redirect(url_for('technician_detail', technician_id=technician_id))
    
    return render_template('edit_technician.html', technician=technician)


@app.route('/technician/<int:technician_id>/dues')
@login_required
def technician_dues(technician_id):
    """المستحقات المالية للفني"""
    if current_user.role not in ['مدير', 'مسؤول إنتاج', 'مسؤول العمليات']:
        flash('ليس لديك صلاحية للوصول إلى صفحة مستحقات الفنيين', 'danger')
        return redirect(url_for('dashboard'))
    
    technician = db.get_or_404(Technician, technician_id)
    
    # جلب المستحقات غير المدفوعة مرتبة حسب التاريخ
    dues = TechnicianDue.query.filter_by(technician_id=technician_id, is_paid=False).all()
    
    return render_template('technician_dues.html', technician=technician, dues=dues)


@app.route('/technician/<int:technician_id>/pay', methods=['GET', 'POST'])
@login_required
def pay_technician_dues(technician_id):
    """دفع مستحقات الفني - للمدير فقط"""
    if current_user.role not in ['مدير', 'مسؤول إنتاج', 'مسؤول العمليات']:
        flash('ليس لديك صلاحية لدفع مستحقات الفنيين', 'danger')
        return redirect(url_for('technician_dues', technician_id=technician_id))
    
    technician = db.get_or_404(Technician, technician_id)
    
    if request.method == 'POST':
        # المستحقات المراد دفعها
        due_ids = request.form.getlist('due_ids')
        
        if not due_ids:
            flash('لم يتم اختيار أي مستحقات للدفع', 'warning')
            return redirect(url_for('technician_dues', technician_id=technician_id))
        
        # جلب المستحقات من قاعدة البيانات
        dues_to_pay = TechnicianDue.query.filter(TechnicianDue.id.in_(due_ids)).all()
        
        # حساب المبلغ الإجمالي
        total_amount = sum([due.amount for due in dues_to_pay])
        
        # إنشاء سجل الدفع
        payment = TechnicianPayment(
            technician_id=technician_id,
            amount=total_amount,
            payment_date=datetime.strptime(request.form.get('payment_date'), '%Y-%m-%d').date(),
            payment_method=request.form.get('payment_method', 'نقداً'),
            reference_number=request.form.get('reference_number'),
            notes=request.form.get('notes'),
            paid_by=current_user.username,
            is_active=True
        )
        
        db.session.add(payment)
        db.session.flush()  # للحصول على معرف الدفعة
        
        # تحديث المستحقات
        for due in dues_to_pay:
            due.is_paid = True
            due.paid_at = datetime.now(timezone.utc)
            due.payment_id = payment.id
        
        db.session.commit()
        
        # تسجيل في سجل التدقيق
        add_audit_log(
            action_type='دفع مستحقات',
            entity_type='فني',
            entity_id=technician_id,
            details=f'دفع مستحقات للفني {technician.name} بقيمة {total_amount} د.ل - عدد البنود: {len(dues_to_pay)}',
            user_id=current_user.id
        )
        
        flash(f'تم دفع مستحقات الفني {technician.name} بقيمة {total_amount} د.ل بنجاح', 'success')
        return redirect(url_for('technician_detail', technician_id=technician_id))
    
    # GET: عرض صفحة اختيار المستحقات للدفع
    dues = TechnicianDue.query.filter_by(technician_id=technician_id, is_paid=False).all()
    return render_template('pay_technician_dues.html', technician=technician, dues=dues)


# مسارات التقارير
@app.route('/reports')
@login_required
def reports():
    if current_user.role != 'مدير':
        flash('ليس لديك صلاحية للوصول إلى صفحة التقارير', 'danger')
        return redirect(url_for('dashboard'))

    return render_template('reports.html')

# مسارات التقارير الفرعية
@app.route('/reports/orders_by_status')
@login_required
def orders_by_status_report():
    if current_user.role != 'مدير':
        flash('ليس لديك صلاحية للوصول إلى هذا التقرير', 'danger')
        return redirect(url_for('dashboard'))
    
    # استعلام لجلب الطلبات مقسمة حسب الحالة (مع تطبيق العزل حسب الصالة)
    # استثناء الطلبيات المؤرشفة
    order_query = get_scoped_query(Order, current_user).filter_by(is_archived=False)
    orders_by_status = order_query.with_entities(Order.status, db.func.count(Order.id)).group_by(Order.status).all()
    
    # ترتيب الحالات بشكل منطقي
    status_order = {
        'مفتوح': 1,
        'قيد التنفيذ': 2,
        'مكتمل': 3,
        'مسلّم': 4,
        'ملغي': 5
    }
    orders_by_status = sorted(orders_by_status, key=lambda x: status_order.get(x[0], 999))
    
    # ألوان مخصصة لكل حالة
    status_colors = {
        'مفتوح': 'rgba(255, 206, 86, 0.7)',       # أصفر
        'قيد التنفيذ': 'rgba(54, 162, 235, 0.7)', # أزرق
        'مكتمل': 'rgba(75, 192, 192, 0.7)',       # أخضر فاتح
        'مسلّم': 'rgba(76, 175, 80, 0.7)',        # أخضر غامق
        'ملغي': 'rgba(255, 99, 132, 0.7)'        # أحمر
    }
    
    return render_template('reports/orders_by_status.html', 
                         orders_by_status=orders_by_status,
                         status_colors=status_colors)

@app.route('/reports/overdue_orders')
@login_required
def overdue_orders_report():
    if current_user.role != 'مدير':
        flash('ليس لديك صلاحية للوصول إلى هذا التقرير', 'danger')
        return redirect(url_for('dashboard'))
    
    # استعلام لجلب الطلبات المتأخرة (مع تطبيق العزل حسب الصالة)
    today = datetime.now(timezone.utc).date()
    order_query = get_scoped_query(Order, current_user)
    overdue_orders = order_query.filter(Order.deadline < today, Order.status != 'مكتمل', Order.status != 'مسلّم').all()
    
    return render_template('reports/overdue_orders.html', overdue_orders=overdue_orders)

@app.route('/reports/materials_consumption')
@login_required
def materials_consumption_report():
    if current_user.role != 'مدير':
        flash('ليس لديك صلاحية للوصول إلى هذا التقرير', 'danger')
        return redirect(url_for('dashboard'))
    
    # استعلام لجلب استهلاك المواد مع الوحدة وتطبيق العزل حسب الصالة
    base_query = db.session.query(
        Material.name,
        Material.unit,
        db.func.sum(OrderMaterial.quantity_used).label('total_used')
    ).join(OrderMaterial)
    
    # تطبيق فلتر الصالة إذا كان محدداً
    if session.get('showroom_filter') and session.get('showroom_filter') != 'all':
        showroom_id = int(session.get('showroom_filter'))
        base_query = base_query.filter(Material.showroom_id == showroom_id)
    
    materials_consumption = base_query.group_by(Material.id).all()
    
    return render_template('reports/materials_consumption.html', materials_consumption=materials_consumption)

@app.route('/reports/low_materials')
@login_required
def low_materials_report():
    if current_user.role != 'مدير':
        flash('ليس لديك صلاحية للوصول إلى هذا التقرير', 'danger')
        return redirect(url_for('dashboard'))
    
    # استعلام لجلب المواد المنخفضة (أقل من 10 وحدات) مع تطبيق العزل حسب الصالة
    material_query = get_scoped_query(Material, current_user)
    low_materials = material_query.filter(Material.quantity_available < 10).all()
    
    return render_template('reports/low_materials.html', low_materials=low_materials)

@app.route('/reports/orders_costs')
@login_required
def orders_costs_report():
    if current_user.role != 'مدير':
        flash('ليس لديك صلاحية للوصول إلى هذا التقرير', 'danger')
        return redirect(url_for('dashboard'))
    
    # استعلام لجلب تكاليف الطلبات (مع تطبيق العزل حسب الصالة)
    order_query = get_scoped_query(Order, current_user)
    orders = order_query.all()
    
    return render_template('reports/orders_costs.html', orders=orders)

@app.route('/reports/costs_by_type')
@login_required
def costs_by_type_report():
    if current_user.role != 'مدير':
        flash('ليس لديك صلاحية للوصول إلى هذا التقرير', 'danger')
        return redirect(url_for('dashboard'))
    
    # استعلام لجلب التكاليف حسب النوع مع تطبيق العزل حسب الصالة
    base_query = db.session.query(
        OrderCost.cost_type,
        db.func.sum(OrderCost.amount).label('total_amount')
    )
    
    # تطبيق فلتر الصالة إذا كان محدداً
    if session.get('showroom_filter') and session.get('showroom_filter') != 'all':
        showroom_id = int(session.get('showroom_filter'))
        base_query = base_query.filter(OrderCost.showroom_id == showroom_id)
    
    costs_by_type = base_query.group_by(OrderCost.cost_type).all()
    
    return render_template('reports/costs_by_type.html', costs_by_type=costs_by_type)

@app.route('/reports/overdue_tasks')
@login_required
def overdue_tasks_report():
    if current_user.role != 'مدير':
        flash('ليس لديك صلاحية للوصول إلى هذا التقرير', 'danger')
        return redirect(url_for('dashboard'))
    
    # استعلام لجلب المهام المتأخرة (مع تطبيق العزل حسب الصالة)
    today = datetime.now(timezone.utc).date()
    stage_query = get_scoped_query(Stage, current_user)
    overdue_tasks = stage_query.filter(Stage.end_date < today, Stage.progress < 100).all()
    
    return render_template('reports/overdue_tasks.html', overdue_tasks=overdue_tasks)

# ==================== تقارير الموردين - النظام الجديد ====================

@app.route('/reports/suppliers_debts')
@login_required
def suppliers_debts_report():
    """تقرير ديون الموردين - النظام الجديد - مضاف 2025-10-19"""
    if current_user.role not in ['مدير', 'مسؤول مخزن', 'مسؤول العمليات']:
        flash('ليس لديك صلاحية للوصول إلى هذا التقرير', 'danger')
        return redirect(url_for('dashboard'))
    
    # جلب جميع الموردين النشطين
    suppliers = Supplier.query.filter_by(is_active=True).all()
    
    # حساب الديون لكل مورد
    suppliers_data = []
    total_debts = 0
    
    for supplier in suppliers:
        # جلب الفواتير النشطة غير المدفوعة بالكامل
        active_invoices = [inv for inv in supplier.invoices 
                          if inv.is_active and inv.debt_status != 'paid']
        
        total_invoices = len([inv for inv in supplier.invoices if inv.is_active])
        unpaid_invoices = len(active_invoices)
        supplier_debt = supplier.total_debt
        total_debts += supplier_debt
        
        # حساب إجمالي المشتريات
        total_purchases = sum(inv.final_amount for inv in supplier.invoices if inv.is_active)
        
        suppliers_data.append({
            'supplier': supplier,
            'total_invoices': total_invoices,
            'unpaid_invoices': unpaid_invoices,
            'total_debt': supplier_debt,
            'total_purchases': total_purchases,
            'total_paid': supplier.total_paid
        })
    
    # ترتيب حسب المديونية (الأعلى أولاً)
    suppliers_data.sort(key=lambda x: x['total_debt'], reverse=True)
    
    return render_template('reports/suppliers_debts.html', 
                         suppliers_data=suppliers_data, 
                         total_debts=total_debts)

@app.route('/reports/overdue_invoices')
@login_required
def overdue_invoices_report():
    """تقرير الفواتير المتأخرة - النظام الجديد - مضاف 2025-10-19"""
    if current_user.role not in ['مدير', 'مسؤول مخزن', 'مسؤول العمليات']:
        flash('ليس لديك صلاحية للوصول إلى هذا التقرير', 'danger')
        return redirect(url_for('dashboard'))
    
    # جلب الفواتير المتأخرة
    today = datetime.now(timezone.utc).date()
    
    overdue_invoices = SupplierInvoice.query.filter(
        SupplierInvoice.due_date.isnot(None),
        SupplierInvoice.due_date < today,
        SupplierInvoice.debt_status != 'paid',
        SupplierInvoice.is_active == True
    ).order_by(SupplierInvoice.due_date.asc()).all()
    
    # حساب الإحصائيات
    total_overdue_amount = sum(inv.remaining_amount for inv in overdue_invoices)
    
    # تصنيف حسب مدة التأخير
    invoices_by_delay = {
        'أقل من أسبوع': [],
        'أسبوع إلى شهر': [],
        'أكثر من شهر': []
    }
    
    for invoice in overdue_invoices:
        days_overdue = (today - invoice.due_date).days
        if days_overdue < 7:
            invoices_by_delay['أقل من أسبوع'].append(invoice)
        elif days_overdue < 30:
            invoices_by_delay['أسبوع إلى شهر'].append(invoice)
        else:
            invoices_by_delay['أكثر من شهر'].append(invoice)
    
    return render_template('reports/overdue_invoices.html',
                         overdue_invoices=overdue_invoices,
                         invoices_by_delay=invoices_by_delay,
                         total_overdue_amount=total_overdue_amount,
                         today=today)

@app.route('/reports/suppliers_performance')
@login_required
def suppliers_performance_report():
    """تقرير أداء الموردين - النظام الجديد - مضاف 2025-10-19"""
    if current_user.role not in ['مدير', 'مسؤول مخزن', 'مسؤول العمليات']:
        flash('ليس لديك صلاحية للوصول إلى هذا التقرير', 'danger')
        return redirect(url_for('dashboard'))
    
    # جلب جميع الموردين النشطين
    suppliers = Supplier.query.filter_by(is_active=True).all()
    
    suppliers_performance = []
    
    for supplier in suppliers:
        # حساب الإحصائيات
        active_invoices = [inv for inv in supplier.invoices if inv.is_active]
        active_payments = [pay for pay in supplier.payments if pay.is_active]
        
        total_invoices = len(active_invoices)
        total_purchases = sum(inv.final_amount for inv in active_invoices)
        total_paid = sum(pay.amount for pay in active_payments)
        total_remaining = supplier.total_debt
        
        # حساب متوسط مبلغ الفاتورة
        avg_invoice = total_purchases / total_invoices if total_invoices > 0 else 0
        
        # حساب نسبة الدفع
        payment_rate = (total_paid / total_purchases * 100) if total_purchases > 0 else 0
        
        # آخر تاريخ شراء
        last_purchase = max((inv.invoice_date for inv in active_invoices), default=None)
        
        # آخر تاريخ دفع
        last_payment = max((pay.payment_date for pay in active_payments), default=None)
        
        suppliers_performance.append({
            'supplier': supplier,
            'total_invoices': total_invoices,
            'total_purchases': total_purchases,
            'total_paid': total_paid,
            'total_remaining': total_remaining,
            'avg_invoice': avg_invoice,
            'payment_rate': payment_rate,
            'last_purchase': last_purchase,
            'last_payment': last_payment
        })
    
    # ترتيب حسب إجمالي المشتريات (الأعلى أولاً)
    suppliers_performance.sort(key=lambda x: x['total_purchases'], reverse=True)
    
    return render_template('reports/suppliers_performance.html',
                         suppliers_performance=suppliers_performance)

@app.route('/reports/payment_allocations')
@login_required
def payment_allocations_report():
    """تقرير توزيع المدفوعات - النظام الجديد - مضاف 2025-10-19"""
    if current_user.role not in ['مدير', 'مسؤول مخزن', 'مسؤول العمليات']:
        flash('ليس لديك صلاحية للوصول إلى هذا التقرير', 'danger')
        return redirect(url_for('dashboard'))
    
    # جلب جميع التوزيعات
    allocations = PaymentAllocation.query.order_by(PaymentAllocation.allocation_date.desc()).all()
    
    # إحصائيات
    total_allocations = len(allocations)
    total_allocated = sum(a.allocated_amount for a in allocations)
    
    # تصنيف حسب طريقة التوزيع
    allocations_by_method = {
        'auto_fifo': [],
        'auto_priority': [],
        'manual': []
    }
    
    for allocation in allocations:
        method = allocation.allocation_method or 'manual'
        if method in allocations_by_method:
            allocations_by_method[method].append(allocation)
    
    stats = {
        'total_allocations': total_allocations,
        'total_allocated': total_allocated,
        'auto_fifo_count': len(allocations_by_method['auto_fifo']),
        'auto_priority_count': len(allocations_by_method['auto_priority']),
        'manual_count': len(allocations_by_method['manual'])
    }
    
    return render_template('reports/payment_allocations.html',
                         allocations=allocations,
                         allocations_by_method=allocations_by_method,
                         stats=stats)

# ==================== تقارير متقدمة ====================

@app.route('/reports/showroom_profitability')
@login_required
def showroom_profitability_report():
    """تقرير ربحية الصالات - يعرض الإيرادات والتكاليف والربح الصافي لكل صالة"""
    
    # التحقق من الصلاحيات
    if current_user.role not in ['مدير']:
        flash('ليس لديك صلاحية للوصول إلى هذا التقرير', 'danger')
        return redirect(url_for('dashboard'))
    
    # الحصول على فترة التقرير من الطلب (اختياري)
    from datetime import timedelta
    period = request.args.get('period', '30')  # افتراضي: آخر 30 يوم
    
    try:
        days = int(period)
    except:
        days = 30
    
    today = datetime.now(timezone.utc).date()
    start_date = today - timedelta(days=days)
    
    # الحصول على جميع الصالات النشطة
    showrooms = Showroom.query.filter_by(is_active=True).all()
    
    profitability_data = []
    total_revenue = 0
    total_costs = 0
    total_profit = 0
    
    for showroom in showrooms:
        # 1. حساب الإيرادات (المدفوعات المستلمة)
        revenue = db.session.query(db.func.sum(Payment.amount)).filter(
            Payment.showroom_id == showroom.id,
            Payment.payment_date >= start_date
        ).scalar() or 0
        
        # ==================== طريقة حساب التكاليف المحدثة (2025-10-16) ====================
        # 2. حساب إجمالي التكاليف من OrderCost (يشمل المواد + الإضافات)
        # الطريقة القديمة (معلقة - كانت تستخدم MaterialConsumption):
        # material_costs = db.session.query(
        #     db.func.sum(MaterialConsumption.quantity_used * Material.cost_price)
        # ).join(...).filter(...).scalar() or 0
        # additional_costs = db.session.query(db.func.sum(OrderCost.amount))...
        # total_showroom_costs = material_costs + additional_costs
        
        # الطريقة الجديدة (باستخدام الخصائص المحسوبة):
        orders = Order.query.filter(
            Order.showroom_id == showroom.id,
            Order.order_date >= start_date
        ).all()
        
        # حساب التكاليف من الخصائص المحسوبة
        material_costs = sum(order.total_materials_cost for order in orders)
        additional_costs = sum(order.total_additional_costs for order in orders)
        total_showroom_costs = sum(order.total_cost for order in orders)
        
        # 5. الربح الصافي
        net_profit = revenue - total_showroom_costs
        
        # 6. هامش الربح (%)
        profit_margin = (net_profit / revenue * 100) if revenue > 0 else 0
        
        # 7. عدد الطلبات
        orders_count = len(orders)  # من الاستعلام السابق
        
        # 8. متوسط الربح لكل طلب
        avg_profit_per_order = net_profit / orders_count if orders_count > 0 else 0
        
        profitability_data.append({
            'showroom': showroom,
            'revenue': revenue,
            'material_costs': material_costs,
            'additional_costs': additional_costs,
            'total_costs': total_showroom_costs,
            'net_profit': net_profit,
            'profit_margin': profit_margin,
            'orders_count': orders_count,
            'avg_profit_per_order': avg_profit_per_order
        })
        
        # إضافة للإجماليات
        total_revenue += revenue
        total_costs += total_showroom_costs
        total_profit += net_profit
    
    # ترتيب حسب الربح الصافي (الأعلى أولاً)
    profitability_data.sort(key=lambda x: x['net_profit'], reverse=True)
    
    # حساب الإجماليات
    summary = {
        'total_revenue': total_revenue,
        'total_costs': total_costs,
        'total_profit': total_profit,
        'overall_margin': (total_profit / total_revenue * 100) if total_revenue > 0 else 0
    }
    
    return render_template('reports/showroom_profitability.html',
                         profitability_data=profitability_data,
                         summary=summary,
                         period=days,
                         start_date=start_date,
                         end_date=today)

@app.route('/reports/inventory_turnover')
@login_required
def inventory_turnover_report():
    """تقرير دوران المخزون - معدل دوران المواد والمواد السريعة/البطيئة الحركة"""
    
    # التحقق من الصلاحيات
    if current_user.role not in ['مدير', 'مسؤول مخزن', 'مسؤول العمليات']:
        flash('ليس لديك صلاحية للوصول إلى هذا التقرير', 'danger')
        return redirect(url_for('dashboard'))
    
    # الحصول على فترة التقرير
    from datetime import timedelta
    period = request.args.get('period', '90')  # افتراضي: آخر 90 يوم
    
    try:
        days = int(period)
    except:
        days = 90
    
    today = datetime.now(timezone.utc).date()
    start_date = today - timedelta(days=days)
    
    # الحصول على جميع المواد النشطة
    materials = Material.query.filter_by(is_active=True).all()
    
    turnover_data = []
    total_inventory_value = 0
    
    for material in materials:
        # 1. الكمية المستهلكة في الفترة
        consumed_qty = db.session.query(
            db.func.sum(MaterialConsumption.quantity_used)
        ).join(
            Order, MaterialConsumption.order_id == Order.id
        ).filter(
            MaterialConsumption.material_id == material.id,
            Order.order_date >= start_date
        ).scalar() or 0
        
        # 2. متوسط الكمية المتاحة (نفترض الحالية كمتوسط)
        avg_inventory = material.quantity_available
        
        # 3. معدل الدوران (Turnover Ratio)
        # معدل الدوران = الكمية المستهلكة / متوسط المخزون
        turnover_ratio = (consumed_qty / avg_inventory) if avg_inventory > 0 else 0
        
        # 4. عدد أيام المخزون (Days in Inventory)
        # عدد الأيام = (متوسط المخزون / الكمية المستهلكة) × عدد أيام الفترة
        days_in_inventory = (avg_inventory / consumed_qty * days) if consumed_qty > 0 else float('inf')
        
        # 5. قيمة المخزون الحالي
        inventory_value = material.quantity_available * material.cost_price
        total_inventory_value += inventory_value
        
        # 6. تصنيف الحركة
        if days_in_inventory == float('inf'):
            movement_category = 'راكد'
        elif days_in_inventory <= 30:
            movement_category = 'سريع الحركة'
        elif days_in_inventory <= 90:
            movement_category = 'متوسط الحركة'
        else:
            movement_category = 'بطيء الحركة'
        
        # 7. عدد مرات الشراء
        purchase_count = db.session.query(db.func.count(PurchaseInvoiceItem.id)).filter(
            PurchaseInvoiceItem.material_id == material.id
        ).join(
            PurchaseInvoice, PurchaseInvoiceItem.invoice_id == PurchaseInvoice.id
        ).filter(
            PurchaseInvoice.invoice_date >= start_date,
            PurchaseInvoice.is_active == True
        ).scalar() or 0
        
        turnover_data.append({
            'material': material,
            'consumed_qty': consumed_qty,
            'current_qty': material.quantity_available,
            'turnover_ratio': turnover_ratio,
            'days_in_inventory': days_in_inventory if days_in_inventory != float('inf') else 0,
            'inventory_value': inventory_value,
            'movement_category': movement_category,
            'purchase_count': purchase_count
        })
    
    # ترتيب حسب معدل الدوران (الأعلى أولاً)
    turnover_data.sort(key=lambda x: x['turnover_ratio'], reverse=True)
    
    # تصنيف المواد
    fast_moving = [m for m in turnover_data if m['movement_category'] == 'سريع الحركة']
    medium_moving = [m for m in turnover_data if m['movement_category'] == 'متوسط الحركة']
    slow_moving = [m for m in turnover_data if m['movement_category'] == 'بطيء الحركة']
    stagnant = [m for m in turnover_data if m['movement_category'] == 'راكد']
    
    summary = {
        'total_inventory_value': total_inventory_value,
        'fast_moving_count': len(fast_moving),
        'medium_moving_count': len(medium_moving),
        'slow_moving_count': len(slow_moving),
        'stagnant_count': len(stagnant)
    }
    
    return render_template('reports/inventory_turnover.html',
                         turnover_data=turnover_data,
                         fast_moving=fast_moving[:10],  # أعلى 10
                         slow_moving=slow_moving[:10],  # أبطأ 10
                         stagnant=stagnant,
                         summary=summary,
                         period=days,
                         start_date=start_date,
                         end_date=today)

@app.route('/reports/product_performance')
@login_required
def product_performance_report():
    """تقرير أداء المنتجات - أكثر المنتجات طلباً وربحيتها"""
    
    # التحقق من الصلاحيات
    if current_user.role not in ['مدير', 'مسؤول إنتاج']:
        flash('ليس لديك صلاحية للوصول إلى هذا التقرير', 'danger')
        return redirect(url_for('dashboard'))
    
    # الحصول على فترة التقرير
    from datetime import timedelta
    period = request.args.get('period', '90')  # افتراضي: آخر 90 يوم
    
    try:
        days = int(period)
    except:
        days = 90
    
    today = datetime.now(timezone.utc).date()
    start_date = today - timedelta(days=days)
    
    # استعلام للحصول على أداء المنتجات (حسب نوع المطبخ أو التصنيف)
    # نفترض أن الطلبات لها نوع/فئة
    
    # 1. أكثر المواد طلباً
    top_materials = db.session.query(
        Material.id,
        Material.name,
        Material.unit,
        db.func.sum(MaterialConsumption.quantity_used).label('total_consumed'),
        db.func.count(db.distinct(MaterialConsumption.order_id)).label('orders_count')
    ).join(
        MaterialConsumption, Material.id == MaterialConsumption.material_id
    ).join(
        Order, MaterialConsumption.order_id == Order.id
    ).filter(
        Order.order_date >= start_date
    ).group_by(
        Material.id, Material.name, Material.unit
    ).order_by(
        db.func.sum(MaterialConsumption.quantity_used).desc()
    ).limit(20).all()
    
    # 2. ربحية المواد (الفرق بين سعر البيع وسعر التكلفة)
    material_profitability = []
    
    for mat_id, mat_name, mat_unit, total_consumed, orders_count in top_materials:
        material = db.session.get(Material, mat_id)
        
        # حساب الربح المقدر (إذا كان هناك سعر بيع)
        if material and material.selling_price and material.selling_price > 0:
            unit_profit = material.selling_price - material.cost_price
            total_profit = unit_profit * total_consumed
            profit_margin = (unit_profit / material.selling_price * 100) if material.selling_price > 0 else 0
        else:
            unit_profit = 0
            total_profit = 0
            profit_margin = 0
        
        # متوسط الاستهلاك الشهري
        avg_monthly_consumption = (total_consumed / days) * 30 if days > 0 else 0
        
        material_profitability.append({
            'material_id': mat_id,
            'material_name': mat_name,
            'unit': mat_unit,
            'total_consumed': total_consumed,
            'orders_count': orders_count,
            'cost_price': material.cost_price if material else 0,
            'selling_price': material.selling_price if material else 0,
            'unit_profit': unit_profit,
            'total_profit': total_profit,
            'profit_margin': profit_margin,
            'avg_monthly_consumption': avg_monthly_consumption
        })
    
    # 3. الطلبات الأكثر ربحية
    profitable_orders = db.session.query(
        Order.id,
        Order.order_date,
        Customer.name.label('customer_name'),
        Order.total_value,
        db.func.sum(Payment.amount).label('paid_amount')
    ).join(
        Customer, Order.customer_id == Customer.id
    ).outerjoin(
        Payment, Order.id == Payment.order_id
    ).filter(
        Order.order_date >= start_date,
        Order.status.in_(['مكتمل', 'مسلّم'])
    ).group_by(
        Order.id, Order.order_date, Customer.name, Order.total_value
    ).order_by(
        Order.total_value.desc()
    ).limit(10).all()
    
    # حساب ملخص
    total_consumed_value = sum([m['total_consumed'] * m['cost_price'] for m in material_profitability])
    total_profit_value = sum([m['total_profit'] for m in material_profitability if m['total_profit'] > 0])
    
    summary = {
        'top_materials_count': len(top_materials),
        'total_consumed_value': total_consumed_value,
        'total_profit_value': total_profit_value,
        'avg_profit_margin': (total_profit_value / total_consumed_value * 100) if total_consumed_value > 0 else 0
    }
    
    return render_template('reports/product_performance.html',
                         material_profitability=material_profitability,
                         profitable_orders=profitable_orders,
                         summary=summary,
                         period=days,
                         start_date=start_date,
                         end_date=today)

# مسارات إدارة المواد في الطلبات
@app.route('/order/<int:order_id>/materials', methods=['GET', 'POST'])
@login_required
def order_materials(order_id):
    """صفحة إدارة المواد للطلبية - النظام المحدّث مع تتبع النقص"""
    order = db.get_or_404(Order, order_id)

    if current_user.role not in ['مدير', 'مسؤول مخزن', 'مسؤول العمليات']:
        flash('ليس لديك صلاحية للوصول إلى صفحة مواد الطلب', 'danger')
        return redirect(url_for('order_detail', order_id=order.id))

    if request.method == 'POST':
        material_id = int(request.form.get('material_id'))
        quantity_needed = float(request.form.get('quantity_needed', 0))
        
        if quantity_needed <= 0:
            flash('الكمية يجب أن تكون أكبر من صفر', 'danger')
            return redirect(url_for('order_materials', order_id=order.id))

        material = db.get_or_404(Material, material_id)
        
        # التحقق من عدم التكرار
        existing = OrderMaterial.query.filter_by(
            order_id=order_id,
            material_id=material_id
        ).first()
        
        if existing:
            flash(f'المادة {material.name} مضافة مسبقاً', 'warning')
            return redirect(url_for('order_materials', order_id=order.id))

        # حساب ما يمكن خصمه
        available = material.quantity_available
        to_consume = min(available, quantity_needed)
        shortage = quantity_needed - to_consume
        
        # تحديد الحالة
        if shortage == 0:
            status = 'complete'
        elif to_consume > 0:
            status = 'partial'
        else:
            status = 'pending'
        
        # خصم من المخزون
        material.quantity_available -= to_consume
        
        # ==================== MaterialConsumption (معلق 2025-10-16) ====================
        # تم تعليق هذا الكود لأنه يسبب ازدواجية مع OrderMaterial
        # MaterialConsumption يجب استخدامه فقط للتتبع التفصيلي بالمراحل (اختياري)
        # السطور المعلقة: 4776-4790 (15 سطر)
        
        # if to_consume > 0:
        #     # الحصول على أول مرحلة أو إنشاء مرحلة افتراضية
        #     first_stage = Stage.query.filter_by(order_id=order_id).first()
        #     if first_stage:
        #         consumption = MaterialConsumption(
        #             order_id=order_id,
        #             stage_id=first_stage.id,
        #             material_id=material_id,
        #             quantity_used=to_consume,
        #             unit_price=material.cost_price,
        #             showroom_id=order.showroom_id
        #         )
        #         db.session.add(consumption)
        
        # تسجيل في OrderMaterial
        order_material = OrderMaterial(
            order_id=order_id,
            material_id=material_id,
            quantity_needed=quantity_needed,
            quantity_consumed=to_consume,
            quantity_shortage=shortage,
            quantity_used=to_consume,  # للتوافق
            unit_price=material.cost_price,
            unit_cost=material.cost_price,
            total_cost=quantity_needed * material.cost_price,
            status=status,
            consumed_at=datetime.now(timezone.utc) if to_consume > 0 else None,
            added_by=current_user.username,
            showroom_id=order.showroom_id,
            notes=f'المتاح: {available}, المطلوب: {quantity_needed}'
        )
        db.session.add(order_material)
        db.session.flush()  # للحصول على order_material.id
        
        # ==================== إنشاء OrderCost تلقائياً للمادة (مضاف 2025-10-16) ====================
        # إنشاء سجل تكلفة مربوط بالمادة
        order_cost = OrderCost(
            order_id=order_id,
            cost_type='مواد',
            description=f'تكلفة مادة: {material.name} ({quantity_needed} {material.unit})',
            amount=order_material.total_cost,
            order_material_id=order_material.id,  # الربط المباشر
            date=datetime.now().date(),
            showroom_id=order.showroom_id
        )
        db.session.add(order_cost)
        
        db.session.commit()
        
        # رسائل التأكيد
        if status == 'complete':
            flash(f'✅ تم خصم {material.name} بالكامل ({to_consume} {material.unit})', 'success')
        elif status == 'partial':
            flash(f'⚠️ {material.name}: تم خصم {to_consume} {material.unit}، الناقص: {shortage} {material.unit}', 'warning')
        else:
            flash(f'❌ {material.name}: غير متوفر، مطلوب: {quantity_needed} {material.unit}', 'danger')

        return redirect(url_for('order_materials', order_id=order.id))

    # GET request
    all_materials = Material.query.filter_by(is_active=True).order_by(Material.name).all()
    order_materials_list = OrderMaterial.query.filter_by(order_id=order_id).all()
    summary = order.materials_summary
    
    return render_template('order_materials.html', 
                         order=order, 
                         materials=all_materials,
                         order_materials=order_materials_list,
                         summary=summary)

@app.route('/order_material/<int:material_id>/delete', methods=['POST'])
@login_required
def delete_order_material(material_id):
    """حذف مادة من الطلبية - النظام المحدّث"""
    order_material = db.get_or_404(OrderMaterial, material_id)
    order_id = order_material.order_id

    if current_user.role not in ['مدير', 'مسؤول مخزن', 'مسؤول العمليات']:
        flash('ليس لديك صلاحية لحذف مادة من الطلب', 'danger')
        return redirect(url_for('order_materials', order_id=order_id))

    # إعادة الكمية المخصومة إلى المخزون
    material = db.session.get(Material, order_material.material_id)
    if order_material.quantity_consumed > 0:
        material.quantity_available += order_material.quantity_consumed
    
    # ==================== حذف OrderCost المرتبط (مضاف 2025-10-16) ====================
    # حذف سجل التكلفة المرتبط بالمادة (إن وجد)
    related_cost = OrderCost.query.filter_by(
        order_material_id=order_material.id,
        cost_type='مواد'
    ).first()
    
    if related_cost:
        db.session.delete(related_cost)

    db.session.delete(order_material)
    db.session.commit()
    flash('تم حذف المادة من الطلب وإعادة الكمية إلى المخزون', 'success')
    return redirect(url_for('order_materials', order_id=order_id))

@app.route('/order_material/<int:material_id>/update', methods=['POST'])
@login_required
def update_order_material_quantity(material_id):
    """تعديل كمية مادة في الطلبية"""
    order_material = db.get_or_404(OrderMaterial, material_id)
    
    if current_user.role not in ['مدير', 'مسؤول مخزن', 'مسؤول العمليات']:
        flash('ليس لديك صلاحية لتعديل المادة', 'danger')
        return redirect(url_for('order_materials', order_id=order_material.order_id))
    
    try:
        new_quantity = float(request.form.get('new_quantity', 0))
        if new_quantity <= 0:
            flash('الكمية يجب أن تكون أكبر من صفر', 'danger')
            return redirect(url_for('order_materials', order_id=order_material.order_id))
        
        material = db.session.get(Material, order_material.material_id)
        
        # إرجاع الكمية المخصومة سابقاً
        material.quantity_available += order_material.quantity_consumed
        
        # حساب الكمية الجديدة
        available = material.quantity_available
        to_consume = min(available, new_quantity)
        shortage = new_quantity - to_consume
        
        # خصم الجديد
        material.quantity_available -= to_consume
        
        # تحديث السجل
        order_material.quantity_needed = new_quantity
        order_material.quantity_consumed = to_consume
        order_material.quantity_shortage = shortage
        order_material.quantity_used = to_consume
        order_material.total_cost = new_quantity * order_material.unit_cost
        
        # تحديث الحالة
        if shortage == 0:
            order_material.status = 'complete'
        elif to_consume > 0:
            order_material.status = 'partial'
        else:
            order_material.status = 'pending'
        
        order_material.modified_by = current_user.username
        
        db.session.commit()
        flash(f'تم تحديث الكمية بنجاح', 'success')
        
    except ValueError:
        flash('يرجى إدخال كمية صحيحة', 'danger')
    
    return redirect(url_for('order_materials', order_id=order_material.order_id))

@app.route('/order_material/<int:material_id>/complete_shortage', methods=['POST'])
@login_required
def complete_material_shortage(material_id):
    """إكمال نقص مادة عند توفرها"""
    order_material = db.get_or_404(OrderMaterial, material_id)
    
    if current_user.role not in ['مدير', 'مسؤول مخزن', 'مسؤول العمليات']:
        flash('ليس لديك صلاحية لإكمال النقص', 'danger')
        return redirect(url_for('order_materials', order_id=order_material.order_id))
    
    if order_material.quantity_shortage <= 0:
        flash('لا يوجد نقص لهذه المادة', 'info')
        return redirect(url_for('order_materials', order_id=order_material.order_id))
    
    material = db.session.get(Material, order_material.material_id)
    
    # حساب ما يمكن خصمه من النقص
    shortage_remaining = order_material.quantity_shortage
    available = material.quantity_available
    to_consume_now = min(available, shortage_remaining)
    
    if to_consume_now <= 0:
        flash(f'المادة {material.name} غير متوفرة حالياً في المخزن', 'warning')
        return redirect(url_for('order_materials', order_id=order_material.order_id))
    
    # خصم من المخزون
    material.quantity_available -= to_consume_now
    
    # تحديث السجل
    order_material.quantity_consumed += to_consume_now
    order_material.quantity_shortage -= to_consume_now
    order_material.quantity_used = order_material.quantity_consumed
    
    # تحديث الحالة
    if order_material.quantity_shortage == 0:
        order_material.status = 'complete'
        order_material.completed_at = datetime.now(timezone.utc)
        flash(f'✅ تم إكمال نقص {material.name} بالكامل ({to_consume_now} {material.unit})', 'success')
    else:
        order_material.status = 'partial'
        flash(f'⚠️ تم خصم {to_consume_now} {material.unit}، المتبقي: {order_material.quantity_shortage} {material.unit}', 'warning')
    
    # تسجيل في MaterialConsumption (للتوافق مع النظام القديم)
    first_stage = Stage.query.filter_by(order_id=order_material.order_id).first()
    if first_stage:
        consumption = MaterialConsumption(
            order_id=order_material.order_id,
            stage_id=first_stage.id,
            material_id=material.id,
            quantity_used=to_consume_now,
            unit_price=material.cost_price,
            showroom_id=order_material.showroom_id
        )
        db.session.add(consumption)
    
    order_material.modified_by = current_user.username
    
    db.session.commit()
    
    return redirect(url_for('order_materials', order_id=order_material.order_id))

@app.route('/shortage_materials')
@login_required
def shortage_materials_list():
    """قائمة بجميع المواد الناقصة في الطلبيات"""
    if current_user.role not in ['مدير', 'مسؤول مخزن', 'مسؤول العمليات']:
        flash('ليس لديك صلاحية للوصول', 'danger')
        return redirect(url_for('dashboard'))
    
    # المواد الناقصة
    shortage_items = OrderMaterial.query.filter(
        OrderMaterial.quantity_shortage > 0
    ).order_by(OrderMaterial.added_at.desc()).all()
    
    # تجميع حسب المادة
    material_summary = {}
    for item in shortage_items:
        mat_id = item.material_id
        if mat_id not in material_summary:
            material_summary[mat_id] = {
                'material': item.material,
                'total_shortage': 0,
                'orders_count': 0,
                'total_value': 0,
                'orders': []
            }
        
        material_summary[mat_id]['total_shortage'] += item.quantity_shortage
        material_summary[mat_id]['orders_count'] += 1
        material_summary[mat_id]['total_value'] += (item.quantity_shortage * (item.unit_cost or 0))
        material_summary[mat_id]['orders'].append({
            'order': item.order,
            'quantity': item.quantity_shortage
        })
    
    return render_template('shortage_materials.html', 
                         shortage_items=shortage_items,
                         material_summary=material_summary)

# إضافة دالة now لقوالب Jinja2
@app.context_processor
def inject_now():
    """إضافة دالة now() للاستخدام في قوالب Jinja2"""
    return {'now': datetime.now}

@app.context_processor
def inject_archive_helpers():
    """إضافة دوال مساعدة لنظام الأرشيف في قوالب Jinja2"""
    
    def get_table_display_name(table_name):
        """الحصول على الاسم المعروض للجدول"""
        names = {
            'orders': 'الطلبيات',
            'stages': 'مراحل الطلبيات',
            'order_material': 'مواد الطلبيات',
            'received_order': 'استلام الطلبيات',
            'technician_dues': 'مستحقات الفنيين',
            'technician_payment': 'دفعات الفنيين',
            'audit_logs': 'سجل التدقيق',
            'material_consumption': 'استهلاك المواد'
        }
        return names.get(table_name, table_name)
    
    def get_table_icon(table_name):
        """الحصول على أيقونة الجدول"""
        icons = {
            'orders': 'shopping-cart',
            'stages': 'tasks',
            'order_material': 'boxes',
            'received_order': 'clipboard-check',
            'technician_dues': 'hard-hat',
            'technician_payment': 'money-bill-wave',
            'audit_logs': 'shield-alt',
            'material_consumption': 'chart-line'
        }
        return icons.get(table_name, 'table')
    
    def get_operation_display_name(operation_type):
        """الحصول على الاسم المعروض للعملية"""
        names = {
            'archive': 'أرشفة',
            'restore': 'استعادة',
            'search': 'بحث',
            'delete': 'حذف',
            'verify': 'تحقق'
        }
        return names.get(operation_type, operation_type)
    
    def get_operation_icon(operation_type):
        """الحصول على أيقونة العملية"""
        icons = {
            'archive': 'archive',
            'restore': 'undo',
            'search': 'search',
            'delete': 'trash',
            'verify': 'check-circle'
        }
        return icons.get(operation_type, 'cog')
    
    def get_status_display_name(status):
        """الحصول على الاسم المعروض للحالة"""
        names = {
            'completed': 'مكتمل',
            'failed': 'فاشل',
            'running': 'قيد التشغيل',
            'cancelled': 'ملغي',
            'pending': 'في الانتظار'
        }
        return names.get(status, status)
    
    def get_pending_archive_count():
        """الحصول على عدد السجلات في انتظار الأرشفة"""
        try:
            stats = get_archive_dashboard_stats()
            return stats['totals'].get('pending_archive', 0)
        except:
            return 0
    
    return {
        'get_table_display_name': get_table_display_name,
        'get_table_icon': get_table_icon,
        'get_operation_display_name': get_operation_display_name,
        'get_operation_icon': get_operation_icon,
        'get_status_display_name': get_status_display_name,
        'get_pending_archive_count': get_pending_archive_count
    }

# تشغيل التطبيق
if __name__ == '__main__':
    with app.app_context():
        # إنشاء قاعدة البيانات مع التحقق من الجداول المفقودة
        print("🔧 بدء إنشاء قاعدة البيانات...")
        
        try:
            # إنشاء جميع الجداول
            db.create_all()
            print("✅ تم إنشاء الجداول الأساسية")
            
            # التحقق من جداول الموردين المطلوبة
            required_supplier_tables = ['suppliers', 'supplier_debts', 'supplier_invoices', 'supplier_payments', 'payment_allocations']
            
            # فحص الجداول الموجودة
            from sqlalchemy import inspect
            inspector = inspect(db.engine)
            existing_tables = inspector.get_table_names()
            
            missing_tables = [table for table in required_supplier_tables if table not in existing_tables]
            
            if missing_tables:
                print(f"⚠️  جداول مفقودة: {missing_tables}")
                print("🔧 محاولة إنشاء الجداول المفقودة...")
                
                # إنشاء الجداول المفقودة يدوياً
                import sqlite3
                conn = sqlite3.connect(app.config['SQLALCHEMY_DATABASE_URI'].replace('sqlite:///', ''))
                cursor = conn.cursor()
                
                for table_name in missing_tables:
                    try:
                        if table_name == 'payment_allocations':
                            cursor.execute("""
                                CREATE TABLE payment_allocations (
                                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                                    payment_id INTEGER NOT NULL,
                                    invoice_id INTEGER NOT NULL,
                                    allocated_amount DECIMAL(10,2) NOT NULL,
                                    allocation_date DATETIME DEFAULT CURRENT_TIMESTAMP,
                                    allocation_method VARCHAR(20) DEFAULT 'auto_fifo',
                                    notes TEXT,
                                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                                    FOREIGN KEY (payment_id) REFERENCES supplier_payments (id) ON DELETE CASCADE,
                                    FOREIGN KEY (invoice_id) REFERENCES supplier_invoices (id) ON DELETE CASCADE
                                )
                            """)
                            print(f"   ✅ تم إنشاء جدول {table_name}")
                        # يمكن إضافة جداول أخرى هنا إذا لزم الأمر
                    except Exception as e:
                        print(f"   ⚠️  فشل إنشاء جدول {table_name}: {e}")
                
                conn.commit()
                conn.close()
                print("✅ تم إنشاء الجداول المفقودة")
            else:
                print("✅ جميع جداول الموردين موجودة")
                
        except Exception as e:
            print(f"❌ خطأ في إنشاء قاعدة البيانات: {e}")
            # لا نوقف التطبيق، نكمل التشغيل

        # إنشاء مستخدم مدير افتراضي إذا لم يكن موجودًا
        if not User.query.filter_by(username='admin').first():
            admin = User(
                username='admin',
                password=generate_password_hash('admin123'),
                role='مدير'
            )
            db.session.add(admin)
            db.session.commit()
            print("✅ تم إنشاء المستخدم الافتراضي")

    # نقطة نهاية API لجلب سعر المادة
    @app.route('/api/material/<int:material_id>/price', methods=['GET'])
    @login_required
    def get_material_price(material_id):
        material = db.session.get(Material, material_id)
        if material:
            return jsonify({
                'success': True,
                'unit_price': material.unit_price
            })
        else:
            return jsonify({
                'success': False,
                'message': 'المادة غير موجودة'
            }), 404

    # نقطة نهاية للنسخ الاحتياطي لقاعدة البيانات
    @app.route('/admin/backup', methods=['GET'])
    @login_required
    def backup_database():
        if current_user.role != 'مدير':
            flash('ليس لديك صلاحية للوصول إلى هذه الصفحة', 'danger')
            return redirect(url_for('dashboard'))

        try:
            # إنشاء اسم ملف النسخ الاحتياطي مع التاريخ والوقت
            backup_filename = f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
            backup_path = os.path.join('backups', backup_filename)

            # التأكد من وجود مجلد النسخ الاحتياطية
            os.makedirs('backups', exist_ok=True)

            # نسخ قاعدة البيانات
            import shutil
            shutil.copy2('kitchen_factory.db', backup_path)

            flash(f'تم إنشاء النسخ الاحتياطي بنجاح: {backup_filename}', 'success')
            return redirect(url_for('admin_tools'))
        except Exception as e:
            flash(f'حدث خطأ أثناء إنشاء النسخ الاحتياطي: {str(e)}', 'danger')
            return redirect(url_for('admin_tools'))

    # نقطة نهاية لاستيراد نسخة احتياطية
    @app.route('/admin/restore', methods=['POST'])
    @login_required
    def restore_database():
        if current_user.role != 'مدير':
            flash('ليس لديك صلاحية للوصول إلى هذه الصفحة', 'danger')
            return redirect(url_for('dashboard'))

        try:
            if 'backup_file' not in request.files:
                flash('لم يتم اختيار ملف للنسخ الاحتياطي', 'danger')
                return redirect(url_for('admin_tools'))

            backup_file = request.files['backup_file']
            if backup_file.filename == '':
                flash('لم يتم اختيار ملف للنسخ الاحتياطي', 'danger')
                return redirect(url_for('admin_tools'))

            if backup_file and backup_file.filename.endswith('.db'):
                # حفظ الملف المرفوع
                backup_path = os.path.join('backups', backup_file.filename)
                backup_file.save(backup_path)

                # استعادة قاعدة البيانات
                import shutil
                shutil.copy2(backup_path, 'kitchen_factory.db')

                flash(f'تم استعادة النسخ الاحتياطي بنجاح: {backup_file.filename}', 'success')
                return redirect(url_for('admin_tools'))
            else:
                flash('نوع الملف غير مدعوم. يرجى اختيار ملف قاعدة بيانات (.db)', 'danger')
                return redirect(url_for('admin_tools'))
        except Exception as e:
            flash(f'حدث خطأ أثناء استعادة النسخ الاحتياطي: {str(e)}', 'danger')
            return redirect(url_for('admin_tools'))

    # صفحة أدوات المشرف
    @app.route('/admin/tools')
    @login_required
    def admin_tools():
        if current_user.role != 'مدير':
            flash('ليس لديك صلاحية للوصول إلى هذه الصفحة', 'danger')
            return redirect(url_for('dashboard'))

        # الحصول على قائمة النسخ الاحتياطية المتوفرة
        backup_files = []
        backup_info = []
        if os.path.exists('backups'):
            backup_files = [f for f in os.listdir('backups') if f.endswith('.db')]
            backup_files.sort(reverse=True)  # ترتيب تنازلي حسب التاريخ

            # الحصول على معلومات كل نسخة احتياطية
            for backup_file in backup_files:
                backup_path = os.path.join('backups', backup_file)
                file_size = os.path.getsize(backup_path) / 1024  # بالكيلوبايت
                backup_info.append({
                    'filename': backup_file,
                    'size': file_size,
                    'date': backup_file.replace('backup_', '').replace('.db', '')
                })

        return render_template('admin_tools.html', backup_info=backup_info)

    @app.route('/admin/reset-all-data', methods=['POST'])
    @login_required
    def reset_all_data():
        """حذف جميع البيانات التشغيلية مع الاحتفاظ بالمستخدمين والإعدادات والمراحل"""
        
        # 1. التحقق من الصلاحيات
        if current_user.role != 'مدير':
            flash('ليس لديك صلاحية لتنفيذ هذه العملية', 'danger')
            return redirect(url_for('admin_tools'))
        
        try:
            # 2. التحقق من كلمة التأكيد
            confirm_text = request.form.get('confirm_text')
            if confirm_text != 'حذف البيانات':
                flash('نص التأكيد غير صحيح', 'danger')
                return redirect(url_for('admin_tools'))
            
            # 3. التحقق من كلمة مرور المدير
            admin_password = request.form.get('admin_password')
            if not check_password_hash(current_user.password, admin_password):
                flash('كلمة المرور غير صحيحة', 'danger')
                log_audit('reset_data_failed', f'محاولة فاشلة: كلمة مرور خاطئة من {current_user.username}')
                return redirect(url_for('admin_tools'))
            
            # 4. السبب (اختياري)
            reset_reason = request.form.get('reset_reason', 'لم يتم تحديد سبب')
            
            # 5. إنشاء نسخة احتياطية
            import shutil
            from datetime import datetime
            
            backup_time = datetime.now().strftime('%Y%m%d_%H%M%S')
            db_path = os.path.join(app.instance_path, 'kitchen_factory.db')
            backup_path = os.path.join(
                app.instance_path, 
                f'kitchen_factory_before_reset_{backup_time}.db'
            )
            
            shutil.copy2(db_path, backup_path)
            flash(f'✅ تم إنشاء نسخة احتياطية: {os.path.basename(backup_path)}', 'success')
            
            # 6. بداية عملية الحذف
            deleted_counts = {}
            
            # حذف البيانات بالترتيب الصحيح (مع مراعاة العلاقات الخارجية)
            
            # المدفوعات
            deleted_counts['payments'] = db.session.query(Payment).delete()
            
            # مستحقات ودفعات الفنيين
            deleted_counts['technician_payments'] = db.session.query(TechnicianPayment).delete()
            deleted_counts['technician_dues'] = db.session.query(TechnicianDue).delete()
            
            # المواد والاستهلاك
            deleted_counts['material_consumption'] = db.session.query(MaterialConsumption).delete()
            deleted_counts['order_materials'] = db.session.query(OrderMaterial).delete()
            deleted_counts['materials'] = db.session.query(Material).delete()
            
            # الفواتير والموردين
            deleted_counts['purchase_invoice_items'] = db.session.query(PurchaseInvoiceItem).delete()
            deleted_counts['supplier_payments'] = db.session.query(SupplierPayment).delete()
            deleted_counts['purchase_invoices'] = db.session.query(PurchaseInvoice).delete()
            deleted_counts['suppliers'] = db.session.query(Supplier).delete()
            
            # التكاليف (يجب حذفها قبل الطلبيات)
            deleted_counts['order_costs'] = db.session.query(OrderCost).delete()
            
            # الطلبيات والعملاء
            deleted_counts['received_orders'] = db.session.query(ReceivedOrder).delete()
            deleted_counts['orders'] = db.session.query(Order).delete()
            deleted_counts['customers'] = db.session.query(Customer).delete()
            
            # 7. حفظ التغييرات
            db.session.commit()
            
            # 8. حساب الإحصائيات المحفوظة
            preserved_counts = {
                'users': User.query.count(),
                'showrooms': Showroom.query.count(),
                'technicians': Technician.query.count(),
                'warehouses': Warehouse.query.count(),
                'stages': Stage.query.count(),
            }
            
            # 9. تسجيل في Audit Log
            total_deleted = sum(deleted_counts.values())
            audit_log = AuditLog(
                table_name='system',
                record_id=0,
                action='reset_all_data',
                field_name='data_reset',
                old_value=f'إجمالي السجلات: {total_deleted}',
                new_value=f'تم الحذف. المحذوف: {deleted_counts} | المحفوظ: {preserved_counts}',
                user_id=current_user.id,
                user_name=current_user.username,
                showroom_id=current_user.showroom_id,
                reason=f'{reset_reason}. النسخة الاحتياطية: {backup_path}'
            )
            db.session.add(audit_log)
            
            # 10. عرض النتائج
            flash(f'✅ تم حذف {total_deleted} سجل بنجاح!', 'success')
            flash(f'✅ تم الاحتفاظ بـ {preserved_counts["users"]} مستخدم', 'info')
            flash(f'✅ تم الاحتفاظ بـ {preserved_counts["showrooms"]} صالة', 'info')
            flash(f'✅ تم الاحتفاظ بـ {preserved_counts["technicians"]} فني', 'info')
            flash(f'✅ تم الاحتفاظ بـ {preserved_counts["stages"]} مرحلة', 'success')
            
            return redirect(url_for('admin_tools'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'❌ حدث خطأ: {str(e)}', 'danger')
            
            # تسجيل الخطأ في Audit Log
            error_log = AuditLog(
                table_name='system',
                record_id=0,
                action='reset_data_error',
                field_name='error',
                old_value='محاولة حذف البيانات',
                new_value=f'فشل: {str(e)}',
                user_id=current_user.id,
                user_name=current_user.username,
                showroom_id=current_user.showroom_id,
                reason=str(e)
            )
            db.session.add(error_log)
            db.session.commit()
            
            return redirect(url_for('admin_tools'))

    # ==================== مسارات إدارة إعدادات النظام ====================
    
    @app.route('/admin/system_settings')
    @login_required
    def system_settings_list():
        """عرض وإدارة إعدادات النظام - للمديرين فقط"""
        if current_user.role != 'مدير':
            flash('ليس لديك صلاحية للوصول إلى هذه الصفحة', 'danger')
            return redirect(url_for('dashboard'))
        
        # جلب جميع الإعدادات مجموعة حسب الفئة
        settings = SystemSettings.query.filter_by(is_active=True).order_by(SystemSettings.category, SystemSettings.key).all()
        
        # تجميع الإعدادات حسب الفئة
        settings_by_category = {}
        for setting in settings:
            category = setting.category or 'general'
            if category not in settings_by_category:
                settings_by_category[category] = []
            settings_by_category[category].append(setting)
        
        # ترجمة أسماء الفئات
        category_names = {
            'pricing': 'سياسات التسعير',
            'inventory': 'إدارة المخزون',
            'permissions': 'الصلاحيات',
            'general': 'إعدادات عامة',
            'reports': 'التقارير'
        }
        
        return render_template('admin_system_settings.html', 
                             settings_by_category=settings_by_category,
                             category_names=category_names)
    
    @app.route('/admin/system_settings/edit/<int:setting_id>', methods=['GET', 'POST'])
    @login_required
    def edit_system_setting(setting_id):
        """تعديل إعداد معين"""
        if current_user.role != 'مدير':
            flash('ليس لديك صلاحية للوصول إلى هذه الصفحة', 'danger')
            return redirect(url_for('dashboard'))
        
        setting = db.get_or_404(SystemSettings, setting_id)
        
        if request.method == 'POST':
            old_value = setting.value
            new_value = request.form.get('value')
            
            # التحقق من صحة القيمة حسب النوع
            try:
                if setting.value_type == 'int':
                    int(new_value)
                elif setting.value_type == 'float':
                    float(new_value)
                elif setting.value_type == 'bool':
                    if new_value.lower() not in ('true', 'false', '1', '0', 'yes', 'no'):
                        raise ValueError("قيمة منطقية غير صحيحة")
                elif setting.value_type == 'json':
                    import json
                    json.loads(new_value)
            except ValueError as e:
                flash(f'قيمة غير صحيحة: {str(e)}', 'danger')
                return redirect(url_for('edit_system_setting', setting_id=setting_id))
            
            # تحديث القيمة
            setting.value = new_value
            setting.updated_at = datetime.now(timezone.utc)
            setting.updated_by = current_user.username
            
            # تسجيل في Audit Log
            log_change(
                table='system_settings',
                record_id=setting.id,
                action='update',
                field='value',
                old_val=old_value,
                new_val=new_value,
                reason=f'تعديل الإعداد {setting.key}'
            )
            
            db.session.commit()
            flash(f'تم تحديث الإعداد "{setting.key}" بنجاح', 'success')
            return redirect(url_for('system_settings_list'))
        
        return render_template('edit_system_setting.html', setting=setting)
    
    @app.route('/admin/system_settings/add', methods=['GET', 'POST'])
    @login_required
    def add_system_setting():
        """إضافة إعداد جديد"""
        if current_user.role != 'مدير':
            flash('ليس لديك صلاحية للوصول إلى هذه الصفحة', 'danger')
            return redirect(url_for('dashboard'))
        
        if request.method == 'POST':
            key = request.form.get('key')
            value = request.form.get('value')
            value_type = request.form.get('value_type', 'string')
            category = request.form.get('category', 'general')
            description = request.form.get('description', '')
            showroom_id = request.form.get('showroom_id')
            
            # التحقق من عدم وجود المفتاح
            existing = SystemSettings.query.filter_by(key=key).first()
            if existing:
                flash(f'الإعداد "{key}" موجود بالفعل', 'danger')
                return redirect(url_for('add_system_setting'))
            
            # إنشاء الإعداد الجديد
            new_setting = SystemSettings(
                key=key,
                value=value,
                value_type=value_type,
                category=category,
                description=description,
                showroom_id=int(showroom_id) if showroom_id else None,
                created_by=current_user.username
            )
            
            db.session.add(new_setting)
            
            # تسجيل في Audit Log
            log_change(
                table='system_settings',
                record_id=0,  # سيتم تحديثه بعد الحفظ
                action='create',
                field=None,
                old_val=None,
                new_val=f'{key}={value}',
                reason=f'إضافة إعداد جديد: {key}'
            )
            
            db.session.commit()
            flash(f'تم إضافة الإعداد "{key}" بنجاح', 'success')
            return redirect(url_for('system_settings_list'))
        
        # جلب قائمة الصالات للاختيار
        showrooms = Showroom.query.filter(Showroom.deleted_at.is_(None), Showroom.is_active == True).all()
        return render_template('add_system_setting.html', showrooms=showrooms)

    # ==================== مسارات عرض Audit Log ====================
    
    @app.route('/admin/audit_log')
    @login_required
    def audit_log_list():
        """عرض سجل التدقيق - للمديرين فقط"""
        if current_user.role != 'مدير':
            flash('ليس لديك صلاحية للوصول إلى هذه الصفحة', 'danger')
            return redirect(url_for('dashboard'))
        
        # الحصول على معاملات الفلترة
        page = request.args.get('page', 1, type=int)
        per_page = 50
        
        table_filter = request.args.get('table', '')
        action_filter = request.args.get('action', '')
        user_filter = request.args.get('user', '')
        date_from = request.args.get('date_from', '')
        date_to = request.args.get('date_to', '')
        
        # بناء الاستعلام
        query = AuditLog.query
        
        if table_filter:
            query = query.filter(AuditLog.table_name == table_filter)
        
        if action_filter:
            query = query.filter(AuditLog.action == action_filter)
        
        if user_filter:
            query = query.filter(AuditLog.user_name.contains(user_filter))
        
        if date_from:
            try:
                from_date = datetime.strptime(date_from, '%Y-%m-%d')
                query = query.filter(AuditLog.timestamp >= from_date)
            except ValueError:
                pass
        
        if date_to:
            try:
                to_date = datetime.strptime(date_to, '%Y-%m-%d')
                # إضافة يوم كامل
                to_date = to_date.replace(hour=23, minute=59, second=59)
                query = query.filter(AuditLog.timestamp <= to_date)
            except ValueError:
                pass
        
        # ترتيب تنازلي حسب التاريخ
        query = query.order_by(AuditLog.timestamp.desc())
        
        # Pagination
        pagination = query.paginate(page=page, per_page=per_page, error_out=False)
        logs = pagination.items
        
        # الحصول على قوائم فريدة للفلاتر
        all_tables = db.session.query(AuditLog.table_name).distinct().order_by(AuditLog.table_name).all()
        all_tables = [t[0] for t in all_tables]
        
        all_actions = ['create', 'update', 'delete', 'cancel']
        
        # إحصائيات سريعة
        total_logs = AuditLog.query.count()
        today_logs = AuditLog.query.filter(
            AuditLog.timestamp >= datetime.now(timezone.utc).replace(hour=0, minute=0, second=0)
        ).count()
        
        return render_template('audit_log.html', 
                             logs=logs,
                             pagination=pagination,
                             all_tables=all_tables,
                             all_actions=all_actions,
                             total_logs=total_logs,
                             today_logs=today_logs,
                             filters={
                                 'table': table_filter,
                                 'action': action_filter,
                                 'user': user_filter,
                                 'date_from': date_from,
                                 'date_to': date_to
                             })
    
    @app.route('/admin/audit_log/<int:log_id>')
    @login_required
    def audit_log_detail(log_id):
        """عرض تفاصيل سجل معين"""
        if current_user.role != 'مدير':
            flash('ليس لديك صلاحية للوصول إلى هذه الصفحة', 'danger')
            return redirect(url_for('dashboard'))
        
        log = db.get_or_404(AuditLog, log_id)
        
        # جلب السجلات المرتبطة (نفس الجدول والسجل)
        related_logs = AuditLog.query.filter(
            AuditLog.table_name == log.table_name,
            AuditLog.record_id == log.record_id,
            AuditLog.id != log.id
        ).order_by(AuditLog.timestamp.desc()).limit(10).all()
        
        return render_template('audit_log_detail.html', log=log, related_logs=related_logs)

    # ==================== مسارات إدارة سياسات الأصناف ====================
    
    @app.route('/admin/material_pricing')
    @login_required
    def material_pricing_list():
        """عرض وإدارة سياسات تسعير الأصناف - للمديرين فقط"""
        if current_user.role != 'مدير':
            flash('ليس لديك صلاحية للوصول إلى هذه الصفحة', 'danger')
            return redirect(url_for('dashboard'))
        
        # جلب جميع المواد النشطة
        materials = Material.query.filter_by(is_active=True).order_by(Material.name).all()
        
        # إحصائيات
        total_materials = len(materials)
        locked_prices = sum(1 for m in materials if m.price_locked)
        manual_override = sum(1 for m in materials if m.price_locked and m.allow_manual_price_edit)
        
        # تجميع حسب سياسة التسعير
        pricing_modes = {}
        for material in materials:
            mode = material.cost_price_mode or 'purchase_price_default'
            if mode not in pricing_modes:
                pricing_modes[mode] = 0
            pricing_modes[mode] += 1
        
        return render_template('material_pricing.html',
                             materials=materials,
                             total_materials=total_materials,
                             locked_prices=locked_prices,
                             manual_override=manual_override,
                             pricing_modes=pricing_modes)
    
    @app.route('/admin/material_pricing/edit/<int:material_id>', methods=['GET', 'POST'])
    @login_required
    def edit_material_pricing(material_id):
        """تعديل سياسة تسعير صنف معين"""
        if current_user.role != 'مدير':
            flash('ليس لديك صلاحية للوصول إلى هذه الصفحة', 'danger')
            return redirect(url_for('dashboard'))
        
        material = db.get_or_404(Material, material_id)
        
        if request.method == 'POST':
            old_mode = material.cost_price_mode
            old_locked = material.price_locked
            old_allow_edit = material.allow_manual_price_edit
            
            # تحديث السياسة
            new_mode = request.form.get('cost_price_mode')
            price_locked = request.form.get('price_locked') == 'on'
            allow_manual = request.form.get('allow_manual_price_edit') == 'on'
            
            material.cost_price_mode = new_mode
            material.price_locked = price_locked
            material.allow_manual_price_edit = allow_manual
            material.price_updated_at = datetime.now(timezone.utc)
            material.price_updated_by = current_user.username
            
            # تسجيل التغييرات في Audit Log
            if old_mode != new_mode:
                log_change(
                    table='material',
                    record_id=material.id,
                    action='update',
                    field='cost_price_mode',
                    old_val=old_mode,
                    new_val=new_mode,
                    reason=f'تغيير سياسة التسعير للصنف {material.name}'
                )
            
            if old_locked != price_locked:
                log_change(
                    table='material',
                    record_id=material.id,
                    action='update',
                    field='price_locked',
                    old_val=str(old_locked),
                    new_val=str(price_locked),
                    reason=f'{"قفل" if price_locked else "فتح"} سعر الصنف {material.name}'
                )
            
            db.session.commit()
            flash(f'تم تحديث سياسة التسعير للصنف "{material.name}" بنجاح', 'success')
            return redirect(url_for('material_pricing_list'))
        
        return render_template('edit_material_pricing.html', material=material)
    
    @app.route('/admin/material_pricing/bulk_update', methods=['POST'])
    @login_required
    def bulk_update_material_pricing():
        """تحديث جماعي لسياسات التسعير"""
        if current_user.role != 'مدير':
            flash('ليس لديك صلاحية للوصول إلى هذه الصفحة', 'danger')
            return redirect(url_for('dashboard'))
        
        action = request.form.get('action')
        material_ids = request.form.getlist('material_ids')
        
        if not material_ids:
            flash('لم يتم تحديد أي أصناف', 'warning')
            return redirect(url_for('material_pricing_list'))
        
        materials = Material.query.filter(Material.id.in_(material_ids)).all()
        
        if action == 'lock_all':
            for material in materials:
                material.price_locked = True
                material.price_updated_at = datetime.now(timezone.utc)
                material.price_updated_by = current_user.username
            flash(f'تم قفل أسعار {len(materials)} صنف', 'success')
        
        elif action == 'unlock_all':
            for material in materials:
                material.price_locked = False
                material.price_updated_at = datetime.now(timezone.utc)
                material.price_updated_by = current_user.username
            flash(f'تم فتح أسعار {len(materials)} صنف', 'success')
        
        elif action == 'change_mode':
            new_mode = request.form.get('new_mode')
            for material in materials:
                material.cost_price_mode = new_mode
                material.price_updated_at = datetime.now(timezone.utc)
                material.price_updated_by = current_user.username
            flash(f'تم تغيير سياسة التسعير لـ {len(materials)} صنف', 'success')
        
        db.session.commit()
        return redirect(url_for('material_pricing_list'))
    
    @app.route('/admin/material_pricing/policy_wizard')
    @login_required
    def material_pricing_wizard():
        """معالج تحديد سياسات التسعير بشكل مرن"""
        if current_user.role != 'مدير':
            flash('ليس لديك صلاحية للوصول إلى هذه الصفحة', 'danger')
            return redirect(url_for('dashboard'))
        
        # جلب جميع المواد مع تجميعها حسب السياسة الحالية
        materials = Material.query.filter_by(is_active=True).order_by(Material.name).all()
        
        # تجميع حسب الفئات (يمكن إضافة حقل category للمواد مستقبلاً)
        warehouses = Warehouse.query.filter_by(is_active=True).all()
        
        return render_template('material_pricing_wizard.html',
                             materials=materials,
                             warehouses=warehouses)
    
    @app.route('/admin/material_pricing/apply_policy', methods=['POST'])
    @login_required
    def apply_pricing_policy():
        """تطبيق سياسة تسعير على مجموعة من المواد"""
        if current_user.role != 'مدير':
            flash('ليس لديك صلاحية للوصول إلى هذه الصفحة', 'danger')
            return redirect(url_for('dashboard'))
        
        policy = request.form.get('policy')
        material_ids = request.form.getlist('material_ids[]')
        lock_prices = request.form.get('lock_prices') == 'true'
        allow_manual = request.form.get('allow_manual') == 'true'
        
        if not material_ids:
            return {'success': False, 'message': 'لم يتم تحديد أي مواد'}, 400
        
        if not policy:
            return {'success': False, 'message': 'لم يتم تحديد سياسة التسعير'}, 400
        
        try:
            # تطبيق السياسة على المواد المحددة
            materials = Material.query.filter(Material.id.in_(material_ids)).all()
            updated_count = 0
            
            for material in materials:
                old_policy = material.cost_price_mode
                material.cost_price_mode = policy
                material.price_locked = lock_prices
                material.allow_manual_price_edit = allow_manual
                material.price_updated_at = datetime.now(timezone.utc)
                material.price_updated_by = current_user.username
                
                # تسجيل في Audit Log
                log_change(
                    table='material',
                    record_id=material.id,
                    action='update',
                    field='cost_price_mode',
                    old_val=old_policy,
                    new_val=policy,
                    reason=f'تطبيق سياسة جماعية: {policy}'
                )
                
                updated_count += 1
            
            db.session.commit()
            
            # ترجمة اسم السياسة للعرض
            policy_name = {
                'purchase_price_default': 'آخر سعر شراء',
                'weighted_average': 'متوسط مرجّح',
                'last_invoice': 'آخر فاتورة'
            }.get(policy, policy)
            
            return {
                'success': True, 
                'message': f'تم تطبيق سياسة "{policy_name}" على {updated_count} صنف بنجاح'
            }
            
        except Exception as e:
            db.session.rollback()
            return {'success': False, 'message': f'حدث خطأ: {str(e)}'}, 500

    # ==================== مسارات إدارة الصالات ====================
    
    # 1. عرض قائمة الصالات
    @app.route('/showrooms')
    @login_required
    def showrooms_list():
        """عرض قائمة جميع الصالات - متاح للمديرين فقط"""
        if current_user.role != 'مدير':
            flash('ليس لديك صلاحية للوصول إلى هذه الصفحة', 'danger')
            return redirect(url_for('dashboard'))
        
        # جلب جميع الصالات (بما فيها غير النشطة)
        showrooms = Showroom.query.filter(Showroom.deleted_at.is_(None)).order_by(Showroom.created_at.desc()).all()
        
        # إحصائيات لكل صالة
        showroom_stats = []
        today = datetime.now(timezone.utc).date()
        upcoming_deadline = today + timedelta(days=3)  # خلال 72 ساعة
        
        for showroom in showrooms:
            # الطلبيات الأساسية
            showroom_orders = Order.query.filter_by(showroom_id=showroom.id).all()
            active_orders = [o for o in showroom_orders if o.status not in ['مكتمل', 'ملغي']]
            
            # حساب مجموع البواقي على الزبائن
            total_remaining = 0
            for order in active_orders:
                # حساب الباقي = إجمالي القيمة - المدفوع
                paid_amount = sum(p.amount for p in order.payments)
                remaining = order.total_value - paid_amount
                if remaining > 0:
                    total_remaining += remaining
            
            # طلبيات للتسليم قريباً (خلال 72 ساعة)
            upcoming_orders = []
            for order in active_orders:
                if order.delivery_date and today <= order.delivery_date <= upcoming_deadline:
                    paid_amount = sum(p.amount for p in order.payments)
                    remaining = order.total_value - paid_amount
                    upcoming_orders.append({
                        'order': order,
                        'customer_name': order.customer.name,
                        'remaining': remaining,
                        'days_until': (order.delivery_date - today).days
                    })
            # ترتيب حسب تاريخ التسليم (الأقرب أولاً)
            upcoming_orders.sort(key=lambda x: x['order'].delivery_date)
            
            # طلبيات متأخرة (فات موعدها ولم تسلم)
            overdue_orders = []
            for order in active_orders:
                if order.delivery_date and order.delivery_date < today:
                    days_overdue = (today - order.delivery_date).days
                    overdue_orders.append({
                        'order': order,
                        'customer_name': order.customer.name,
                        'days_overdue': days_overdue
                    })
            # ترتيب حسب أيام التأخير (الأكثر أولاً)
            overdue_orders.sort(key=lambda x: x['days_overdue'], reverse=True)
            
            stats = {
                'showroom': showroom,
                'total_orders': len(showroom_orders),
                'active_orders': len(active_orders),
                'total_users': User.query.filter_by(showroom_id=showroom.id, is_active=True).count(),
                'total_remaining': total_remaining,
                'upcoming_orders': upcoming_orders[:5],  # أول 5 فقط
                'upcoming_count': len(upcoming_orders),
                'overdue_orders': overdue_orders[:5],  # أول 5 فقط
                'overdue_count': len(overdue_orders)
            }
            showroom_stats.append(stats)
        
        return render_template('showrooms.html', showroom_stats=showroom_stats)
    
    # 2. إضافة صالة جديدة
    @app.route('/showroom/new', methods=['GET', 'POST'])
    @login_required
    def new_showroom():
        """إضافة صالة جديدة - متاح للمديرين فقط"""
        if current_user.role != 'مدير':
            flash('ليس لديك صلاحية لإضافة صالة جديدة', 'danger')
            return redirect(url_for('dashboard'))
        
        if request.method == 'POST':
            try:
                # استخراج البيانات من النموذج
                name = request.form.get('name', '').strip()
                code = request.form.get('code', '').strip()
                address = request.form.get('address', '').strip()
                phone = request.form.get('phone', '').strip()
                manager_name = request.form.get('manager_name', '').strip()
                notes = request.form.get('notes', '').strip()
                is_active = request.form.get('is_active') == 'on'
                
                # التحقق من البيانات المطلوبة
                if not name:
                    flash('اسم الصالة مطلوب', 'danger')
                    return render_template('new_showroom.html')
                
                # التحقق من عدم تكرار الاسم أو الكود
                if Showroom.query.filter_by(name=name).first():
                    flash('اسم الصالة موجود بالفعل', 'danger')
                    return render_template('new_showroom.html')
                
                if code and Showroom.query.filter_by(code=code).first():
                    flash('كود الصالة موجود بالفعل', 'danger')
                    return render_template('new_showroom.html')
                
                # إنشاء الصالة الجديدة
                new_showroom = Showroom(
                    name=name,
                    code=code if code else None,
                    address=address if address else None,
                    phone=phone if phone else None,
                    manager_name=manager_name if manager_name else None,
                    notes=notes if notes else None,
                    is_active=is_active,
                    created_at=datetime.now(timezone.utc)
                )
                
                db.session.add(new_showroom)
                db.session.commit()
                
                flash(f'تم إضافة الصالة "{name}" بنجاح', 'success')
                return redirect(url_for('showrooms_list'))
                
            except Exception as e:
                db.session.rollback()
                flash(f'حدث خطأ أثناء إضافة الصالة: {str(e)}', 'danger')
                return render_template('new_showroom.html')
        
        return render_template('new_showroom.html')
    
    # 3. تعديل صالة
    @app.route('/showroom/<int:showroom_id>/edit', methods=['GET', 'POST'])
    @login_required
    def edit_showroom(showroom_id):
        """تعديل بيانات صالة - متاح للمديرين فقط"""
        if current_user.role != 'مدير':
            flash('ليس لديك صلاحية لتعديل الصالات', 'danger')
            return redirect(url_for('dashboard'))
        
        showroom = db.get_or_404(Showroom, showroom_id)
        
        # التحقق من أن الصالة غير محذوفة
        if showroom.deleted_at:
            flash('هذه الصالة محذوفة ولا يمكن تعديلها', 'danger')
            return redirect(url_for('showrooms_list'))
        
        if request.method == 'POST':
            try:
                # استخراج البيانات من النموذج
                name = request.form.get('name', '').strip()
                code = request.form.get('code', '').strip()
                address = request.form.get('address', '').strip()
                phone = request.form.get('phone', '').strip()
                manager_name = request.form.get('manager_name', '').strip()
                notes = request.form.get('notes', '').strip()
                is_active = request.form.get('is_active') == 'on'
                
                # التحقق من البيانات المطلوبة
                if not name:
                    flash('اسم الصالة مطلوب', 'danger')
                    return render_template('edit_showroom.html', showroom=showroom)
                
                # التحقق من عدم تكرار الاسم أو الكود (ما عدا الصالة الحالية)
                existing_name = Showroom.query.filter(Showroom.name == name, Showroom.id != showroom_id).first()
                if existing_name:
                    flash('اسم الصالة موجود بالفعل', 'danger')
                    return render_template('edit_showroom.html', showroom=showroom)
                
                if code:
                    existing_code = Showroom.query.filter(Showroom.code == code, Showroom.id != showroom_id).first()
                    if existing_code:
                        flash('كود الصالة موجود بالفعل', 'danger')
                        return render_template('edit_showroom.html', showroom=showroom)
                
                # تحديث البيانات
                showroom.name = name
                showroom.code = code if code else None
                showroom.address = address if address else None
                showroom.phone = phone if phone else None
                showroom.manager_name = manager_name if manager_name else None
                showroom.notes = notes if notes else None
                showroom.is_active = is_active
                showroom.updated_at = datetime.now(timezone.utc)
                
                db.session.commit()
                
                flash(f'تم تحديث بيانات الصالة "{name}" بنجاح', 'success')
                return redirect(url_for('showroom_detail', showroom_id=showroom.id))
                
            except Exception as e:
                db.session.rollback()
                flash(f'حدث خطأ أثناء تحديث الصالة: {str(e)}', 'danger')
                return render_template('edit_showroom.html', showroom=showroom)
        
        return render_template('edit_showroom.html', showroom=showroom)
    
    # 4. تفاصيل صالة
    @app.route('/showroom/<int:showroom_id>')
    @login_required
    def showroom_detail(showroom_id):
        """عرض تفاصيل وإحصائيات صالة - متاح للمديرين فقط"""
        if current_user.role != 'مدير':
            flash('ليس لديك صلاحية للوصول إلى هذه الصفحة', 'danger')
            return redirect(url_for('dashboard'))
        
        showroom = db.get_or_404(Showroom, showroom_id)
        
        # إحصائيات مفصلة
        stats = {
            'total_orders': Order.query.filter_by(showroom_id=showroom.id).count(),
            'active_orders': Order.query.filter_by(showroom_id=showroom.id, status='مفتوح').count(),
            'completed_orders': Order.query.filter_by(showroom_id=showroom.id, status='مكتمل').count(),
            'total_users': User.query.filter_by(showroom_id=showroom.id).count(),
            'active_users': User.query.filter_by(showroom_id=showroom.id, is_active=True).count(),
            # المواد الآن مرتبطة بالمخزن الموحد وليس بالصالة
            'total_materials': Material.query.filter_by(is_active=True).count(),
            'active_materials': Material.query.filter_by(is_active=True).count(),
            'total_payments': Payment.query.filter_by(showroom_id=showroom.id).count(),
            'total_revenue': db.session.query(db.func.sum(Payment.amount)).filter_by(showroom_id=showroom.id).scalar() or 0
        }
        
        # آخر الطلبات
        recent_orders = Order.query.filter_by(showroom_id=showroom.id).order_by(Order.order_date.desc()).limit(5).all()
        
        # الموظفين
        users = User.query.filter_by(showroom_id=showroom.id).order_by(User.username).all()
        
        return render_template('showroom_detail.html', showroom=showroom, stats=stats, recent_orders=recent_orders, users=users)
    
    # 5. تعطيل/تفعيل صالة
    @app.route('/showroom/<int:showroom_id>/toggle_active', methods=['POST'])
    @login_required
    def toggle_showroom_active(showroom_id):
        """تعطيل أو تفعيل صالة - متاح للمديرين فقط"""
        if current_user.role != 'مدير':
            flash('ليس لديك صلاحية لتعطيل/تفعيل الصالات', 'danger')
            return redirect(url_for('dashboard'))
        
        showroom = db.get_or_404(Showroom, showroom_id)
        
        # التحقق من أن الصالة غير محذوفة
        if showroom.deleted_at:
            flash('هذه الصالة محذوفة ولا يمكن تعديلها', 'danger')
            return redirect(url_for('showrooms_list'))
        
        try:
            # عكس الحالة
            showroom.is_active = not showroom.is_active
            showroom.updated_at = datetime.now(timezone.utc)
            
            db.session.commit()
            
            status = 'تفعيل' if showroom.is_active else 'تعطيل'
            flash(f'تم {status} الصالة "{showroom.name}" بنجاح', 'success')
            
        except Exception as e:
            db.session.rollback()
            flash(f'حدث خطأ أثناء تحديث حالة الصالة: {str(e)}', 'danger')
        
        return redirect(url_for('showroom_detail', showroom_id=showroom.id))

    # ==================== مسارات إدارة الموردين - النظام الجديد ====================
    
    @app.route('/suppliers')
    @login_required
    def suppliers_list():
        """عرض قائمة الموردين - النظام الجديد - مضاف 2025-10-19"""
        if current_user.role not in ['مدير', 'مسؤول مخزن', 'مسؤول العمليات']:
            flash('ليس لديك صلاحية للوصول إلى صفحة الموردين', 'danger')
            return redirect(url_for('dashboard'))
        
        # جلب الموردين النشطين
        suppliers = Supplier.query.filter_by(is_active=True).order_by(Supplier.created_at.desc()).all()
        
        # إحصائيات لكل مورد
        for supplier in suppliers:
            supplier.invoices_count = len([inv for inv in supplier.invoices if inv.is_active])
            supplier.total_invoices_amount = sum(inv.final_amount for inv in supplier.invoices if inv.is_active)
        
        return render_template('suppliers.html', suppliers=suppliers)
    
    @app.route('/supplier/new', methods=['GET', 'POST'])
    @login_required
    def new_supplier():
        """إضافة مورد جديد - النظام الجديد - مضاف 2025-10-19"""
        if current_user.role not in ['مدير', 'مسؤول مخزن', 'مسؤول العمليات']:
            flash('ليس لديك صلاحية لإضافة مورد جديد', 'danger')
            return redirect(url_for('suppliers_list'))
        
        if request.method == 'POST':
            name = request.form.get('name')
            code = request.form.get('code')
            phone = request.form.get('phone')
            email = request.form.get('email')
            address = request.form.get('address')
            tax_id = request.form.get('tax_id')
            contact_person = request.form.get('contact_person')
            payment_terms = request.form.get('payment_terms')
            notes = request.form.get('notes')
            
            # التحقق من البيانات المطلوبة
            if not name:
                flash('اسم المورد مطلوب', 'danger')
                return render_template('new_supplier.html')
            
            # التحقق من عدم تكرار الكود
            if code:
                existing_supplier = Supplier.query.filter_by(code=code, is_active=True).first()
                if existing_supplier:
                    flash(f'كود المورد "{code}" مستخدم بالفعل', 'danger')
                    return render_template('new_supplier.html')
            
            try:
                # الحصول على معرف الصالة
                showroom_id = get_user_showroom_id()
                
                supplier = Supplier(
                    name=name,
                    code=code,
                    phone=phone,
                    email=email,
                    address=address,
                    tax_id=tax_id,
                    contact_person=contact_person,
                    payment_terms=payment_terms,
                    notes=notes,
                    showroom_id=showroom_id,
                    created_by=current_user.username
                )
                
                db.session.add(supplier)
                db.session.flush()
                
                # إنشاء سجل دين للمورد
                debt = SupplierDebt(
                    supplier_id=supplier.id,
                    total_debt=0,
                    paid_amount=0,
                    remaining_debt=0
                )
                
                db.session.add(debt)
                db.session.commit()
                
                flash(f'تم إضافة المورد "{name}" بنجاح', 'success')
                return redirect(url_for('suppliers_list'))
                
            except Exception as e:
                db.session.rollback()
                flash(f'حدث خطأ أثناء إضافة المورد: {str(e)}', 'danger')
        
        return render_template('new_supplier.html')
    
    @app.route('/supplier/<int:supplier_id>')
    @login_required
    def supplier_detail(supplier_id):
        """عرض تفاصيل مورد - النظام الجديد - مضاف 2025-10-19"""
        if current_user.role not in ['مدير', 'مسؤول مخزن', 'مسؤول العمليات']:
            flash('ليس لديك صلاحية للوصول إلى هذه الصفحة', 'danger')
            return redirect(url_for('dashboard'))
        
        supplier = db.get_or_404(Supplier, supplier_id)
        
        # الفواتير النشطة
        active_invoices = [inv for inv in supplier.invoices if inv.is_active]
        
        # المدفوعات النشطة
        active_payments = [pay for pay in supplier.payments if pay.is_active]
        
        # حساب الفواتير المتأخرة
        from datetime import date
        today = date.today()
        overdue_invoices = [
            inv for inv in active_invoices 
            if inv.due_date and inv.due_date < today and inv.debt_status != 'paid'
        ]
        
        # إحصائيات
        stats = {
            'total_invoices': len(active_invoices),
            'total_amount': sum(inv.final_amount for inv in active_invoices),
            'total_paid': supplier.total_paid,
            'total_remaining': supplier.total_debt,
            'payments_count': len(active_payments),
            'overdue_invoices': len(overdue_invoices)
        }
        
        return render_template('supplier_detail.html', 
                             supplier=supplier, 
                             stats=stats, 
                             active_invoices=active_invoices,
                             active_payments=active_payments)
    
    @app.route('/supplier/<int:supplier_id>/edit', methods=['GET', 'POST'])
    @login_required
    def edit_supplier(supplier_id):
        """تعديل بيانات مورد - النظام الجديد - مضاف 2025-10-19"""
        if current_user.role not in ['مدير', 'مسؤول مخزن', 'مسؤول العمليات']:
            flash('ليس لديك صلاحية لتعديل المورد', 'danger')
            return redirect(url_for('dashboard'))
        
        supplier = db.get_or_404(Supplier, supplier_id)
        
        # التحقق من أن المورد نشط
        if not supplier.is_active:
            flash('هذا المورد غير نشط ولا يمكن تعديله', 'danger')
            return redirect(url_for('suppliers_list'))
        
        if request.method == 'POST':
            name = request.form.get('name')
            code = request.form.get('code')
            
            # التحقق من عدم تكرار الكود
            if code and code != supplier.code:
                existing_supplier = Supplier.query.filter_by(code=code, is_active=True).filter(Supplier.id != supplier.id).first()
                if existing_supplier:
                    flash(f'كود المورد "{code}" مستخدم بالفعل', 'danger')
                    return render_template('edit_supplier.html', supplier=supplier)
            
            try:
                supplier.name = name
                supplier.code = code
                supplier.phone = request.form.get('phone')
                supplier.email = request.form.get('email')
                supplier.address = request.form.get('address')
                supplier.tax_id = request.form.get('tax_id')
                supplier.contact_person = request.form.get('contact_person')
                supplier.payment_terms = request.form.get('payment_terms')
                supplier.notes = request.form.get('notes')
                supplier.updated_at = datetime.now(timezone.utc)
                
                db.session.commit()
                
                flash(f'تم تحديث بيانات المورد "{name}" بنجاح', 'success')
                return redirect(url_for('supplier_detail', supplier_id=supplier.id))
                
            except Exception as e:
                db.session.rollback()
                flash(f'حدث خطأ أثناء تحديث المورد: {str(e)}', 'danger')
        
        return render_template('edit_supplier.html', supplier=supplier)
    
    @app.route('/supplier/<int:supplier_id>/delete', methods=['POST'])
    @login_required
    def delete_supplier(supplier_id):
        """حذف مورد (Soft Delete) - النظام الجديد - مضاف 2025-10-19"""
        if current_user.role != 'مدير':
            flash('ليس لديك صلاحية لحذف الموردين', 'danger')
            return redirect(url_for('dashboard'))
        
        supplier = db.get_or_404(Supplier, supplier_id)
        
        # التحقق من وجود فواتير نشطة
        active_invoices = [inv for inv in supplier.invoices if inv.is_active]
        if active_invoices:
            flash(f'لا يمكن حذف المورد لأنه لديه {len(active_invoices)} فاتورة نشطة', 'danger')
            return redirect(url_for('supplier_detail', supplier_id=supplier.id))
        
        # التحقق من وجود ديون
        if supplier.total_debt > 0:
            flash(f'لا يمكن حذف المورد لأنه لديه ديون متبقية بمبلغ {supplier.total_debt:.2f} دينار', 'danger')
            return redirect(url_for('supplier_detail', supplier_id=supplier.id))
        
        try:
            # Soft Delete
            supplier.is_active = False
            
            db.session.commit()
            
            flash(f'تم حذف المورد "{supplier.name}" بنجاح', 'success')
            return redirect(url_for('suppliers_list'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'حدث خطأ أثناء حذف المورد: {str(e)}', 'danger')
            return redirect(url_for('supplier_detail', supplier_id=supplier.id))

    # ==================== مسارات إدارة الفواتير - النظام الجديد ====================
    
    @app.route('/invoices')
    @login_required
    def invoices_list():
        """عرض قائمة فواتير الشراء - النظام الجديد - مضاف 2025-10-19"""
        if current_user.role not in ['مدير', 'مسؤول مخزن', 'مسؤول العمليات']:
            flash('ليس لديك صلاحية للوصول إلى صفحة الفواتير', 'danger')
            return redirect(url_for('dashboard'))
        
        # جلب الفواتير النشطة
        invoices = SupplierInvoice.query.filter_by(is_active=True).order_by(SupplierInvoice.invoice_date.desc()).all()
        
        # إحصائيات
        total_invoices = len(invoices)
        total_amount = sum(inv.final_amount for inv in invoices)
        total_paid = sum(inv.paid_amount for inv in invoices)
        total_remaining = sum(inv.remaining_amount for inv in invoices)
        
        # الفواتير المتأخرة
        today = datetime.now(timezone.utc).date()
        overdue_invoices = [inv for inv in invoices 
                           if inv.due_date and inv.due_date < today 
                           and inv.debt_status != 'paid']
        
        stats = {
            'total_invoices': total_invoices,
            'total_amount': total_amount,
            'total_paid': total_paid,
            'total_remaining': total_remaining,
            'overdue_count': len(overdue_invoices)
        }
        
        return render_template('invoices.html', invoices=invoices, stats=stats)
    
    @app.route('/invoice/new', methods=['GET', 'POST'])
    @login_required
    def new_invoice():
        """إضافة فاتورة شراء جديدة - النظام الجديد - مضاف 2025-10-19"""
        if current_user.role not in ['مدير', 'مسؤول مخزن', 'مسؤول العمليات']:
            flash('ليس لديك صلاحية لإضافة فاتورة', 'danger')
            return redirect(url_for('invoices_list'))
        
        if request.method == 'POST':
            try:
                # بيانات الفاتورة
                supplier_id = request.form.get('supplier_id')
                invoice_number = request.form.get('invoice_number')
                invoice_date = request.form.get('invoice_date')
                due_date = request.form.get('due_date')
                notes = request.form.get('notes')
                
                # التحقق من البيانات المطلوبة
                if not supplier_id or not invoice_number:
                    flash('المورد ورقم الفاتورة مطلوبان', 'danger')
                    suppliers = Supplier.query.filter_by(is_active=True).all()
                    materials = Material.query.filter_by(is_active=True).all()
                    return render_template('new_invoice.html', suppliers=suppliers, materials=materials)
                
                # التحقق من عدم تكرار رقم الفاتورة
                existing = SupplierInvoice.query.filter_by(invoice_number=invoice_number, is_active=True).first()
                if existing:
                    flash(f'رقم الفاتورة "{invoice_number}" مستخدم بالفعل', 'danger')
                    suppliers = Supplier.query.filter_by(is_active=True).all()
                    materials = Material.query.filter_by(is_active=True).all()
                    return render_template('new_invoice.html', suppliers=suppliers, materials=materials)
                
                # الحصول على الصالة
                showroom_id = get_user_showroom_id()
                
                # إنشاء الفاتورة
                invoice = SupplierInvoice(
                    supplier_id=int(supplier_id),
                    showroom_id=showroom_id,
                    invoice_number=invoice_number,
                    invoice_date=datetime.strptime(invoice_date, '%Y-%m-%d').date() if invoice_date else datetime.now(timezone.utc).date(),
                    due_date=datetime.strptime(due_date, '%Y-%m-%d').date() if due_date else None,
                    notes=notes,
                    created_by=current_user.username
                )
                
                db.session.add(invoice)
                db.session.flush()
                
                # إضافة المواد (نفس المنطق القديم)
                material_ids = request.form.getlist('material_id[]')
                quantities = request.form.getlist('quantity[]')
                prices = request.form.getlist('price[]')
                
                total_amount = 0
                
                for mat_id, qty, price in zip(material_ids, quantities, prices):
                    if mat_id and qty and price:
                        quantity = float(qty)
                        purchase_price = float(price)
                        line_total = quantity * purchase_price
                        total_amount += line_total
                        
                        # تحديث كمية المادة في المخزن
                        material = db.session.get(Material, int(mat_id))
                        if material:
                            old_qty = material.quantity_available
                            material.quantity_available += quantity
                            
                            # تحديث سعر التكلفة
                            success, message = update_material_cost_price(
                                material=material,
                                new_purchase_price=purchase_price,
                                quantity=quantity,
                                invoice_id=invoice.id,
                                user=current_user
                            )
                            
                            # تسجيل تغيير الكمية
                            log_quantity_change(
                                table='material',
                                record_id=material.id,
                                old_qty=old_qty,
                                new_qty=material.quantity_available,
                                reason=f'إضافة من فاتورة {invoice.invoice_number}'
                            )
                
                # حساب المبلغ النهائي
                invoice.total_amount = total_amount
                invoice.final_amount = total_amount
                invoice.debt_amount = total_amount
                invoice.paid_amount = 0
                
                # تحديث سجل الدين للمورد
                supplier = db.session.get(Supplier, int(supplier_id))
                if supplier and supplier.debt:
                    supplier.debt.total_debt += total_amount
                    supplier.debt.remaining_debt += total_amount
                
                db.session.commit()
                
                flash(f'تم إضافة الفاتورة "{invoice_number}" بنجاح', 'success')
                return redirect(url_for('invoice_detail', invoice_id=invoice.id))
                
            except Exception as e:
                db.session.rollback()
                flash(f'حدث خطأ أثناء إضافة الفاتورة: {str(e)}', 'danger')
        
        # GET request
        suppliers = Supplier.query.filter_by(is_active=True).all()
        materials = Material.query.filter_by(is_active=True).all()
        
        # التحقق من المتطلبات المسبقة
        if not suppliers:
            flash('⚠️ يجب إضافة مورد واحد على الأقل قبل إنشاء فاتورة', 'warning')
            return redirect(url_for('invoices_list'))
        
        if not materials:
            flash('⚠️ يجب إضافة مادة واحدة على الأقل قبل إنشاء فاتورة', 'warning')
            return redirect(url_for('invoices_list'))
        
        return render_template('new_invoice.html', suppliers=suppliers, materials=materials)
    
    @app.route('/invoice/<int:invoice_id>')
    @login_required
    def invoice_detail(invoice_id):
        """عرض تفاصيل فاتورة - النظام الجديد - مضاف 2025-10-19"""
        if current_user.role not in ['مدير', 'مسؤول مخزن', 'مسؤول العمليات']:
            flash('ليس لديك صلاحية للوصول إلى هذه الصفحة', 'danger')
            return redirect(url_for('dashboard'))
        
        invoice = db.get_or_404(SupplierInvoice, invoice_id)
        
        # حساب الإحصائيات
        stats = {
            'total_amount': invoice.total_amount,
            'discount': invoice.discount_amount,
            'tax': invoice.tax_amount,
            'final_amount': invoice.final_amount,
            'paid_amount': invoice.paid_amount,
            'remaining_amount': invoice.remaining_amount,
            'allocations_count': len(invoice.payment_allocations)
        }
        
        return render_template('invoice_detail.html', invoice=invoice, stats=stats)
    
    @app.route('/invoice/<int:invoice_id>/edit', methods=['GET', 'POST'])
    @login_required
    def edit_invoice(invoice_id):
        """تعديل فاتورة مورد - النظام الجديد - مضاف 2025-10-19"""
        if current_user.role not in ['مدير', 'مسؤول مخزن']:
            flash('ليس لديك صلاحية لتعديل الفواتير', 'danger')
            return redirect(url_for('dashboard'))
        
        invoice = db.get_or_404(SupplierInvoice, invoice_id)
        
        # التحقق من إمكانية التعديل
        if not invoice.is_active:
            flash('لا يمكن تعديل فاتورة ملغاة', 'warning')
            return redirect(url_for('invoice_detail', invoice_id=invoice.id))
        
        if invoice.paid_amount > 0:
            flash('لا يمكن تعديل فاتورة تم دفع جزء منها أو كلها', 'danger')
            return redirect(url_for('invoice_detail', invoice_id=invoice.id))
        
        if request.method == 'POST':
            try:
                # حفظ البيانات القديمة للتدقيق
                old_data = {
                    'supplier_id': invoice.supplier_id,
                    'invoice_number': invoice.invoice_number,
                    'invoice_date': invoice.invoice_date,
                    'due_date': invoice.due_date,
                    'total_amount': invoice.total_amount,
                    'final_amount': invoice.final_amount,
                    'debt_amount': invoice.debt_amount
                }
                
                # تحديث البيانات الأساسية
                supplier_id = request.form.get('supplier_id')
                invoice_number = request.form.get('invoice_number')
                invoice_date = request.form.get('invoice_date')
                due_date = request.form.get('due_date')
                discount_amount = float(request.form.get('discount_amount', 0))
                tax_amount = float(request.form.get('tax_amount', 0))
                notes = request.form.get('notes', '')
                
                # التحقق من تكرار رقم الفاتورة
                if invoice_number != invoice.invoice_number:
                    existing = SupplierInvoice.query.filter_by(
                        invoice_number=invoice_number,
                        is_active=True
                    ).filter(SupplierInvoice.id != invoice.id).first()
                    
                    if existing:
                        flash(f'رقم الفاتورة "{invoice_number}" مستخدم بالفعل', 'danger')
                        suppliers = Supplier.query.filter_by(is_active=True).all()
                        return render_template('edit_invoice.html', invoice=invoice, suppliers=suppliers)
                
                # تحديث بيانات الفاتورة
                invoice.supplier_id = int(supplier_id)
                invoice.invoice_number = invoice_number
                invoice.invoice_date = datetime.strptime(invoice_date, '%Y-%m-%d').date() if invoice_date else invoice.invoice_date
                invoice.due_date = datetime.strptime(due_date, '%Y-%m-%d').date() if due_date else None
                invoice.discount_amount = discount_amount
                invoice.tax_amount = tax_amount
                invoice.notes = notes
                
                # إعادة حساب المبالغ (يتم من خلال حفظ items إذا تم تعديلها)
                invoice.final_amount = invoice.total_amount - discount_amount + tax_amount
                invoice.debt_amount = invoice.final_amount
                
                # تحديث دين المورد إذا تغير المورد
                if old_data['supplier_id'] != invoice.supplier_id:
                    # إزالة من المورد القديم
                    old_supplier = Supplier.query.get(old_data['supplier_id'])
                    if old_supplier and old_supplier.debt:
                        old_supplier.debt.total_debt -= old_data['debt_amount']
                        old_supplier.debt.remaining_debt = old_supplier.debt.total_debt - old_supplier.debt.paid_amount
                    
                    # إضافة للمورد الجديد
                    new_supplier = Supplier.query.get(invoice.supplier_id)
                    if new_supplier:
                        if not new_supplier.debt:
                            new_debt = SupplierDebt(
                                supplier_id=new_supplier.id,
                                total_debt=invoice.debt_amount,
                                paid_amount=0,
                                remaining_debt=invoice.debt_amount
                            )
                            db.session.add(new_debt)
                        else:
                            new_supplier.debt.total_debt += invoice.debt_amount
                            new_supplier.debt.remaining_debt = new_supplier.debt.total_debt - new_supplier.debt.paid_amount
                
                # تسجيل في سجل التدقيق
                audit_log = AuditLog(
                    table_name='supplier_invoices',
                    record_id=invoice.id,
                    action='edit',
                    field_name='multiple_fields',
                    old_value=str(old_data),
                    new_value=f'تعديل فاتورة {invoice_number}',
                    reason='تعديل بيانات فاتورة مورد',
                    showroom_id=invoice.showroom_id,
                    user_name=current_user.username
                )
                db.session.add(audit_log)
                
                db.session.commit()
                
                flash(f'تم تعديل الفاتورة {invoice.invoice_number} بنجاح', 'success')
                return redirect(url_for('invoice_detail', invoice_id=invoice.id))
                
            except Exception as e:
                db.session.rollback()
                flash(f'حدث خطأ أثناء تعديل الفاتورة: {str(e)}', 'danger')
        
        # GET request
        suppliers = Supplier.query.filter_by(is_active=True).all()
        return render_template('edit_invoice.html', invoice=invoice, suppliers=suppliers)
    
    @app.route('/invoice/<int:invoice_id>/cancel', methods=['POST'])
    @login_required
    def cancel_invoice(invoice_id):
        """إلغاء فاتورة مورد - النظام الجديد - مضاف 2025-10-19"""
        if current_user.role not in ['مدير', 'مسؤول مخزن']:
            flash('ليس لديك صلاحية لإلغاء الفواتير', 'danger')
            return redirect(url_for('dashboard'))
        
        invoice = db.get_or_404(SupplierInvoice, invoice_id)
        
        # التحقق من إمكانية الإلغاء
        if not invoice.is_active:
            flash('هذه الفاتورة ملغاة بالفعل', 'warning')
            return redirect(url_for('invoice_detail', invoice_id=invoice.id))
        
        if invoice.paid_amount > 0:
            flash('لا يمكن إلغاء فاتورة تم دفع جزء منها أو كلها', 'danger')
            return redirect(url_for('invoice_detail', invoice_id=invoice.id))
        
        try:
            cancellation_reason = request.form.get('cancellation_reason', '')
            
            # إلغاء الفاتورة (soft delete)
            invoice.is_active = False
            invoice.notes = f"ملغاة - السبب: {cancellation_reason}\n{invoice.notes or ''}"
            
            # تحديث دين المورد
            if invoice.supplier.debt:
                invoice.supplier.debt.total_debt -= invoice.debt_amount
                invoice.supplier.debt.remaining_debt = invoice.supplier.debt.total_debt - invoice.supplier.debt.paid_amount
            
            # تسجيل في سجل التدقيق
            audit_log = AuditLog(
                table_name='supplier_invoices',
                record_id=invoice.id,
                action='cancel',
                field_name='is_active',
                old_value='True',
                new_value='False',
                reason=f'إلغاء فاتورة: {cancellation_reason}',
                notes=cancellation_reason,
                showroom_id=invoice.showroom_id,
                user_name=current_user.username
            )
            db.session.add(audit_log)
            
            db.session.commit()
            
            flash(f'تم إلغاء الفاتورة {invoice.invoice_number} بنجاح', 'success')
            return redirect(url_for('invoices_list'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'حدث خطأ أثناء إلغاء الفاتورة: {str(e)}', 'danger')
            return redirect(url_for('invoice_detail', invoice_id=invoice.id))
    
    @app.route('/invoice/<int:invoice_id>/add_payment', methods=['GET', 'POST'])
    @login_required
    def add_invoice_payment(invoice_id):
        """إضافة دفعة لفاتورة محددة - النظام الجديد - مضاف 2025-10-19"""
        if current_user.role not in ['مدير', 'مسؤول مخزن', 'مسؤول العمليات']:
            flash('ليس لديك صلاحية للوصول إلى هذه الصفحة', 'danger')
            return redirect(url_for('dashboard'))
        
        invoice = db.get_or_404(SupplierInvoice, invoice_id)
        
        if request.method == 'POST':
            amount = float(request.form.get('amount', 0))
            payment_method = request.form.get('payment_method', 'نقد')
            payment_date = request.form.get('payment_date')
            reference_number = request.form.get('reference_number', '')
            notes = request.form.get('notes', '')
            
            if amount <= 0:
                flash('المبلغ يجب أن يكون أكبر من صفر', 'danger')
                return render_template('add_invoice_payment.html', invoice=invoice)
            
            try:
                # إنشاء دفعة مرنة للمورد
                payment = SupplierPayment(
                    supplier_id=invoice.supplier_id,
                    debt_id=invoice.supplier.debt.id if invoice.supplier.debt else None,
                    amount=amount,
                    payment_date=datetime.strptime(payment_date, '%Y-%m-%d') if payment_date else datetime.now(timezone.utc),
                    payment_method=payment_method,
                    payment_type='specific_invoice',
                    allocation_method='manual',
                    reference_number=reference_number,
                    notes=notes,
                    created_by=current_user.username
                )
                
                db.session.add(payment)
                db.session.flush()
                
                # توزيع الدفعة على الفاتورة المحددة
                allocated_amount = min(amount, invoice.remaining_amount)
                
                allocation = PaymentAllocation(
                    payment_id=payment.id,
                    invoice_id=invoice.id,
                    allocated_amount=allocated_amount,
                    allocation_method='manual',
                    notes=f'دفعة مخصصة للفاتورة {invoice.invoice_number}'
                )
                
                db.session.add(allocation)
                
                # تحديث الفاتورة
                invoice.paid_amount += allocated_amount
                if invoice.paid_amount >= invoice.debt_amount:
                    invoice.debt_status = 'paid'
                else:
                    invoice.debt_status = 'partial'
                
                # تحديث دين المورد
                if invoice.supplier.debt:
                    invoice.supplier.debt.paid_amount += allocated_amount
                    invoice.supplier.debt.remaining_debt = invoice.supplier.debt.total_debt - invoice.supplier.debt.paid_amount
                
                db.session.commit()
                
                flash(f'تم إضافة الدفعة بنجاح: {amount:,.2f} د.ل', 'success')
                return redirect(url_for('invoice_detail', invoice_id=invoice.id))
                
            except Exception as e:
                db.session.rollback()
                flash(f'حدث خطأ أثناء إضافة الدفعة: {str(e)}', 'danger')
        
        return render_template('add_invoice_payment.html', invoice=invoice)
    
    # ==================== مسارات إدارة المدفوعات - النظام الجديد ====================
    
    @app.route('/supplier/<int:supplier_id>/add_payment', methods=['GET', 'POST'])
    @login_required
    def add_supplier_payment(supplier_id):
        """إضافة دفعة مرنة لمورد - النظام الجديد - مضاف 2025-10-19"""
        if current_user.role not in ['مدير', 'مسؤول مخزن', 'مسؤول العمليات']:
            flash('ليس لديك صلاحية لإضافة دفعة', 'danger')
            return redirect(url_for('dashboard'))
        
        supplier = db.get_or_404(Supplier, supplier_id)
        
        # التحقق من وجود ديون
        if supplier.total_debt <= 0:
            flash('لا توجد ديون لهذا المورد', 'warning')
            return redirect(url_for('supplier_detail', supplier_id=supplier.id))
        
        if request.method == 'POST':
            try:
                amount = float(request.form.get('amount'))
                payment_method = request.form.get('payment_method', 'نقد')
                payment_date = request.form.get('payment_date')
                reference_number = request.form.get('reference_number')
                notes = request.form.get('notes')
                allocation_method = request.form.get('allocation_method', 'auto_fifo')
                
                # التحقق من المبلغ
                if amount <= 0:
                    flash('المبلغ يجب أن يكون أكبر من صفر', 'danger')
                    return render_template('add_supplier_payment.html', supplier=supplier)
                
                if amount > supplier.total_debt:
                    flash(f'المبلغ أكبر من إجمالي الديون ({supplier.total_debt:.2f})', 'warning')
                
                # إنشاء الدفعة
                payment = SupplierPayment(
                    supplier_id=supplier.id,
                    debt_id=supplier.debt.id,
                    amount=amount,
                    payment_method=payment_method,
                    payment_date=datetime.strptime(payment_date, '%Y-%m-%d') if payment_date else datetime.now(timezone.utc),
                    reference_number=reference_number,
                    notes=notes,
                    payment_type='flexible',
                    allocation_method=allocation_method,
                    created_by=current_user.username
                )
                
                db.session.add(payment)
                db.session.flush()
                
                # توزيع تلقائي حسب FIFO
                if allocation_method == 'auto_fifo':
                    allocations, remaining = allocate_payment_fifo(payment, supplier.id, amount)
                    
                    # تحديث سجل الدين
                    allocated_total = sum(a.allocated_amount for a in allocations)
                    supplier.debt.paid_amount += allocated_total
                    supplier.debt.remaining_debt -= allocated_total
                    
                    db.session.commit()
                    
                    flash(f'تم تسجيل دفعة بمبلغ {amount:.2f} دينار وتوزيعها على {len(allocations)} فاتورة', 'success')
                else:
                    # توزيع يدوي (يُضاف لاحقاً)
                    db.session.commit()
                    flash(f'تم تسجيل دفعة بمبلغ {amount:.2f} دينار', 'success')
                
                return redirect(url_for('supplier_detail', supplier_id=supplier.id))
                
            except Exception as e:
                db.session.rollback()
                flash(f'حدث خطأ أثناء تسجيل الدفعة: {str(e)}', 'danger')
        
        # GET request - جلب الفواتير غير المدفوعة
        unpaid_invoices = [inv for inv in supplier.invoices 
                          if inv.is_active and inv.debt_status != 'paid']
        
        return render_template('add_supplier_payment.html', 
                             supplier=supplier, 
                             unpaid_invoices=unpaid_invoices)
    
    @app.route('/payments')
    @login_required
    def payments_list():
        """عرض قائمة المدفوعات - النظام الجديد - مضاف 2025-10-19"""
        if current_user.role not in ['مدير', 'مسؤول مخزن', 'مسؤول العمليات']:
            flash('ليس لديك صلاحية للوصول إلى صفحة المدفوعات', 'danger')
            return redirect(url_for('dashboard'))
        
        # جلب المدفوعات النشطة
        payments = SupplierPayment.query.filter_by(is_active=True).order_by(SupplierPayment.payment_date.desc()).all()
        
        # إحصائيات
        total_payments = len(payments)
        total_amount = sum(pay.amount for pay in payments)
        total_allocated = sum(pay.total_allocated for pay in payments)
        total_unallocated = sum(pay.unallocated_amount for pay in payments)
        
        stats = {
            'total_payments': total_payments,
            'total_amount': total_amount,
            'total_allocated': total_allocated,
            'total_unallocated': total_unallocated
        }
        
        return render_template('payments.html', payments=payments, stats=stats)
    
    @app.route('/payment/<int:payment_id>')
    @login_required
    def payment_detail(payment_id):
        """عرض تفاصيل دفعة - النظام الجديد - مضاف 2025-10-19"""
        if current_user.role not in ['مدير', 'مسؤول مخزن', 'مسؤول العمليات']:
            flash('ليس لديك صلاحية للوصول إلى هذه الصفحة', 'danger')
            return redirect(url_for('dashboard'))
        
        payment = db.get_or_404(SupplierPayment, payment_id)
        
        # إحصائيات
        stats = {
            'amount': payment.amount,
            'allocated': payment.total_allocated,
            'unallocated': payment.unallocated_amount,
            'allocations_count': len(payment.allocations)
        }
        
        return render_template('payment_detail.html', payment=payment, stats=stats)

    # ==================== API: تغيير فلتر الصالة ====================
    @app.route('/set_showroom_filter', methods=['POST'])
    @login_required
    def set_showroom_filter():
        """تغيير فلتر الصالة للمدير - API endpoint"""
        if current_user.role != 'مدير':
            return jsonify({'success': False, 'error': 'غير مصرح'}), 403
        
        data = request.get_json()
        showroom_id = data.get('showroom_id', 'all')
        
        # حفظ الفلتر في Session
        session['showroom_filter'] = showroom_id
        
        return jsonify({
            'success': True,
            'showroom_id': showroom_id,
            'message': 'تم تغيير فلتر الصالة بنجاح'
        })

# ==================== مسارات نظام الأرشفة ====================

# ديكوريتر للتحكم بصلاحيات الأرشيف
def require_archive_permission(permission_level='viewer'):
    """ديكوريتر للتحكم بصلاحيات الوصول للأرشيف"""
    from functools import wraps
    
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            if not current_user.is_authenticated:
                flash('يجب تسجيل الدخول أولاً', 'danger')
                return redirect(url_for('login'))
            
            # تحديد الأدوار المسموحة لكل مستوى صلاحية
            permission_roles = {
                'viewer': ['مدير', 'مسؤول العمليات'],
                'manager': ['مدير'],
                'admin': ['مدير']
            }
            
            allowed_roles = permission_roles.get(permission_level, ['مدير'])
            
            if current_user.role not in allowed_roles:
                flash('ليس لديك صلاحية للوصول إلى نظام الأرشيف', 'danger')
                return redirect(url_for('dashboard'))
            
            return func(*args, **kwargs)
        return wrapper
    return decorator

@app.route('/archive')
@login_required
@require_archive_permission('viewer')
def archive_dashboard():
    """لوحة معلومات الأرشيف الرئيسية"""
    
    try:
        # جمع إحصائيات الأرشيف
        stats = get_archive_dashboard_stats()
        
        return render_template('archive/dashboard.html', stats=stats)
        
    except Exception as e:
        flash(f'حدث خطأ في تحميل لوحة الأرشيف: {str(e)}', 'danger')
        return redirect(url_for('dashboard'))

@app.route('/archive/search', methods=['GET', 'POST'])
@login_required
@require_archive_permission('viewer')
def archive_search():
    """البحث المتقدم في الأرشيف"""
    
    results = []
    search_params = {}
    
    if request.method == 'POST':
        search_params = {
            'table_name': request.form.get('table_name'),
            'start_date': request.form.get('start_date'),
            'end_date': request.form.get('end_date'),
            'archive_reason': request.form.get('archive_reason'),
            'archived_by': request.form.get('archived_by'),
            'limit': int(request.form.get('limit', 100))
        }
        
        # إزالة القيم الفارغة
        search_params = {k: v for k, v in search_params.items() if v}
        
        try:
            results = search_archived_records(search_params)
            flash(f'تم العثور على {len(results)} نتيجة', 'success')
        except Exception as e:
            flash(f'حدث خطأ في البحث: {str(e)}', 'danger')
    
    # قائمة الجداول المتاحة للبحث
    available_tables = [
        {'value': 'orders', 'label': 'الطلبيات'},
        {'value': 'stages', 'label': 'مراحل الطلبيات'},
        {'value': 'technician_dues', 'label': 'مستحقات الفنيين'},
        {'value': 'audit_logs', 'label': 'سجل التدقيق'}
    ]
    
    return render_template('archive/search.html', 
                         results=results,
                         search_params=search_params,
                         available_tables=available_tables)

@app.route('/archive/orders')
@login_required  
@require_archive_permission('viewer')
def archive_orders_list():
    """عرض الطلبيات المؤرشفة"""
    
    page = request.args.get('page', 1, type=int)
    per_page = 20
    
    # فلاتر البحث
    customer_name = request.args.get('customer_name', '')
    start_date = request.args.get('start_date', '')
    end_date = request.args.get('end_date', '')
    
    try:
        # بناء استعلام البحث
        search_conditions = {'table_name': 'orders'}
        
        if customer_name:
            search_conditions['customer_name'] = customer_name
        if start_date:
            search_conditions['start_date'] = start_date
        if end_date:
            search_conditions['end_date'] = end_date
        
        # الحصول على النتائج
        all_results = search_archived_records(search_conditions)
        
        # تصفح النتائج
        total = len(all_results)
        start_idx = (page - 1) * per_page
        end_idx = start_idx + per_page
        results = all_results[start_idx:end_idx]
        
        # إنشاء كائن التصفح
        pagination = {
            'page': page,
            'per_page': per_page,
            'total': total,
            'pages': (total + per_page - 1) // per_page,
            'has_prev': page > 1,
            'has_next': page * per_page < total,
            'prev_num': page - 1 if page > 1 else None,
            'next_num': page + 1 if page * per_page < total else None
        }
        
        return render_template('archive/archived_orders.html', 
                             results=results, 
                             pagination=pagination,
                             filters={'customer_name': customer_name, 
                                    'start_date': start_date, 
                                    'end_date': end_date})
                                    
    except Exception as e:
        flash(f'حدث خطأ في تحميل الطلبيات المؤرشفة: {str(e)}', 'danger')
        return redirect(url_for('archive_dashboard'))

@app.route('/archive/restore/<table_name>/<int:record_id>', methods=['POST'])
@login_required
@require_archive_permission('manager')
def restore_archived_record_route(table_name, record_id):
    """استعادة سجل من الأرشيف"""
    
    restore_reason = request.form.get('restore_reason', 'طلب استعادة من المستخدم')
    
    try:
        success = restore_archived_record(table_name, record_id, restore_reason)
        
        if success:
            flash(f'تم استعادة السجل رقم {record_id} من {table_name} بنجاح', 'success')
            
            # تسجيل في سجل التدقيق
            log_change(
                table=f'archive_{table_name}',
                record_id=record_id,
                action='استعادة من الأرشيف',
                reason=f'تم استعادة السجل من الأرشيف. السبب: {restore_reason}',
                notes=f'استعادة بواسطة {current_user.username}'
            )
        else:
            flash(f'فشل في استعادة السجل رقم {record_id}', 'danger')
    
    except Exception as e:
        flash(f'حدث خطأ أثناء الاستعادة: {str(e)}', 'danger')
    
    return redirect(request.referrer or url_for('archive_dashboard'))

@app.route('/archive/manual/<table_name>/<int:record_id>', methods=['POST'])
@login_required
@require_archive_permission('manager')
def manual_archive_record(table_name, record_id):
    """أرشفة سجل يدوياً"""
    
    archive_reason = request.form.get('archive_reason', 'أرشفة يدوية')
    
    try:
        success = archive_single_record(table_name, record_id, archive_reason, 'manual')
        
        if success:
            flash(f'تم أرشفة السجل رقم {record_id} من {table_name} بنجاح', 'success')
            
            # تسجيل في سجل التدقيق
            log_change(
                table=table_name,
                record_id=record_id,
                action='أرشفة يدوية',
                reason=f'تم أرشفة السجل يدوياً. السبب: {archive_reason}',
                notes=f'أرشفة بواسطة {current_user.username}'
            )
        else:
            flash(f'فشل في أرشفة السجل رقم {record_id}', 'danger')
    
    except Exception as e:
        flash(f'حدث خطأ أثناء الأرشفة: {str(e)}', 'danger')
    
    return redirect(request.referrer or url_for('dashboard'))

@app.route('/archive/bulk-archive', methods=['GET', 'POST'])
@login_required
@require_archive_permission('manager')
def bulk_archive():
    """أرشفة جماعية للسجلات"""
    
    if request.method == 'POST':
        table_name = request.form.get('table_name')
        record_ids = request.form.getlist('record_ids')
        archive_reason = request.form.get('archive_reason', 'أرشفة جماعية')
        
        if not record_ids:
            flash('لم يتم اختيار أي سجلات للأرشفة', 'warning')
            return redirect(request.referrer)
        
        # تحويل معرفات السجلات إلى أرقام
        try:
            record_ids = [int(rid) for rid in record_ids]
        except ValueError:
            flash('معرفات السجلات غير صحيحة', 'danger')
            return redirect(request.referrer)
        
        # تنفيذ الأرشفة الجماعية
        result = archive_batch_records(table_name, record_ids, archive_reason)
        
        if result['success']:
            flash(f'تم أرشفة {result["successful_count"]} سجل بنجاح من أصل {result["total_records"]}', 'success')
            
            if result['failed_count'] > 0:
                flash(f'فشل في أرشفة {result["failed_count"]} سجل', 'warning')
            
            # تسجيل في سجل التدقيق
            log_change(
                table=table_name,
                record_id=0,  # للعمليات الجماعية
                action='أرشفة جماعية',
                reason=f'تم أرشفة {result["successful_count"]} سجل جماعياً. السبب: {archive_reason}',
                notes=f'أرشفة جماعية بواسطة {current_user.username}'
            )
        else:
            flash(f'فشل في العملية: {result.get("error", "خطأ غير معروف")}', 'danger')
        
        return redirect(request.referrer or url_for('archive_dashboard'))
    
    return render_template('archive/bulk_archive.html')

@app.route('/archive/auto-archive', methods=['POST'])
@login_required
@require_archive_permission('admin')
def trigger_auto_archive():
    """تشغيل الأرشفة التلقائية يدوياً"""
    
    try:
        results = auto_archive_eligible_records()
        
        total_archived = 0
        messages = []
        
        for table, result in results.items():
            if isinstance(result, dict) and result.get('success'):
                count = result['successful_count']
                total_archived += count
                messages.append(f'{table}: {count} سجل')
        
        if total_archived > 0:
            flash(f'تم أرشفة {total_archived} سجل: {", ".join(messages)}', 'success')
            
            # تسجيل في سجل التدقيق
            log_change(
                table='system',
                record_id=0,
                action='أرشفة تلقائية يدوية',
                reason=f'تم تشغيل الأرشفة التلقائية يدوياً - النتائج: {", ".join(messages)}',
                notes=f'تشغيل بواسطة {current_user.username}'
            )
        else:
            flash('لا توجد سجلات مؤهلة للأرشفة حالياً', 'info')
    
    except Exception as e:
        flash(f'حدث خطأ في الأرشفة التلقائية: {str(e)}', 'danger')
    
    return redirect(url_for('archive_dashboard'))

@app.route('/archive/statistics')
@login_required
@require_archive_permission('viewer')
def archive_statistics():
    """عرض إحصائيات مفصلة للأرشيف"""
    
    try:
        # إحصائيات شاملة
        stats = get_archive_dashboard_stats()
        
        # إحصائيات العمليات (آخر 30 يوم)
        thirty_days_ago = datetime.now(timezone.utc) - timedelta(days=30)
        
        operation_stats = db.session.execute("""
            SELECT 
                operation_type,
                status,
                COUNT(*) as count,
                AVG(duration_seconds) as avg_duration,
                SUM(record_count) as total_records
            FROM archive_operations_log 
            WHERE operation_start >= ?
            GROUP BY operation_type, status
        """, [thirty_days_ago]).fetchall()
        
        stats['operations'] = [dict(row._mapping) if hasattr(row, '_mapping') else dict(row) for row in operation_stats]
        
        # إحصائيات الاستخدام (البحث والاستعادة)
        usage_stats = db.session.execute("""
            SELECT 
                DATE(operation_start) as date,
                operation_type,
                COUNT(*) as count
            FROM archive_operations_log 
            WHERE operation_start >= ?
            AND operation_type IN ('search', 'restore')
            GROUP BY DATE(operation_start), operation_type
            ORDER BY date DESC
        """, [thirty_days_ago]).fetchall()
        
        stats['usage'] = [dict(row._mapping) if hasattr(row, '_mapping') else dict(row) for row in usage_stats]
        
        return render_template('archive/statistics.html', stats=stats)
        
    except Exception as e:
        flash(f'حدث خطأ في تحميل الإحصائيات: {str(e)}', 'danger')
        return redirect(url_for('archive_dashboard'))

# مسار API للحصول على العدادات المحدثة
@app.route('/api/archive/counts')
@login_required
@require_archive_permission('viewer')
def archive_counts_api():
    """API للحصول على عدادات الأرشيف المحدثة"""
    
    try:
        stats = get_archive_dashboard_stats()
        return jsonify({
            'success': True,
            'pending_count': stats['totals'].get('pending_archive', 0),
            'total_archived': stats['totals'].get('total_archived_records', 0),
            'total_size_mb': stats['totals'].get('total_size_mb', 0)
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# مسار API لتفاصيل السجل المؤرشف
@app.route('/api/archive/details/<table_name>/<int:record_id>')
@login_required
@require_archive_permission('viewer')
def archive_record_details_api(table_name, record_id):
    """API للحصول على تفاصيل سجل مؤرشف"""
    
    try:
        # البحث عن البيانات الوصفية
        metadata = ArchiveMetadata.query.filter_by(
            source_table=table_name, 
            source_id=record_id
        ).first()
        
        if not metadata:
            return jsonify({
                'success': False,
                'error': 'السجل غير موجود في الأرشيف'
            }), 404
        
        # إعداد البيانات للإرسال
        result = {
            'success': True,
            'archived_at': metadata.archived_at.isoformat() if metadata.archived_at else None,
            'archived_by': metadata.archived_by,
            'archive_reason': metadata.archive_reason,
            'archive_type': metadata.archive_type,
            'can_restore': metadata.can_restore,
            'data_size_bytes': metadata.data_size_bytes,
            'original_data': None
        }
        
        # إضافة البيانات الأصلية إذا كانت متاحة
        if metadata.original_record_json:
            try:
                result['original_data'] = json.loads(metadata.original_record_json)
            except:
                result['original_data'] = None
        
        return jsonify(result)
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# ==================== مسارات إدارة نظام جدولة الأرشفة ====================

@app.route('/archive/scheduler/status')
@login_required
@require_archive_permission('admin')
def archive_scheduler_status():
    """عرض حالة نظام جدولة الأرشفة"""
    
    try:
        # استيراد نظام الجدولة
        from archive_scheduler import get_scheduler_status
        
        status = get_scheduler_status()
        return render_template('archive/scheduler_status.html', status=status)
        
    except Exception as e:
        flash(f'خطأ في جلب حالة نظام الجدولة: {str(e)}', 'danger')
        return redirect(url_for('archive_dashboard'))

@app.route('/archive/scheduler/start', methods=['POST'])
@login_required
@require_archive_permission('admin')
def start_archive_scheduler():
    """بدء تشغيل نظام جدولة الأرشفة"""
    
    try:
        from archive_scheduler import initialize_scheduler
        
        scheduler = initialize_scheduler(app, app.config['SQLALCHEMY_DATABASE_URI'].replace('sqlite:///', ''))
        
        if scheduler:
            flash('تم بدء تشغيل نظام جدولة الأرشفة بنجاح', 'success')
            
            # تسجيل في سجل التدقيق
            log_change(
                table='system',
                record_id=0,
                action='تشغيل نظام جدولة الأرشفة',
                reason='تم بدء تشغيل نظام الجدولة يدوياً',
                notes=f'تشغيل بواسطة {current_user.username}'
            )
        else:
            flash('فشل في بدء تشغيل نظام الجدولة', 'danger')
            
    except Exception as e:
        flash(f'خطأ في تشغيل نظام الجدولة: {str(e)}', 'danger')
    
    return redirect(url_for('archive_scheduler_status'))

@app.route('/archive/scheduler/stop', methods=['POST'])
@login_required
@require_archive_permission('admin')
def stop_archive_scheduler():
    """إيقاف نظام جدولة الأرشفة"""
    
    try:
        from archive_scheduler import shutdown_scheduler
        
        shutdown_scheduler()
        flash('تم إيقاف نظام جدولة الأرشفة', 'warning')
        
        # تسجيل في سجل التدقيق
        log_change(
            table='system',
            record_id=0,
            action='إيقاف نظام جدولة الأرشفة',
            reason='تم إيقاف نظام الجدولة يدوياً',
            notes=f'إيقاف بواسطة {current_user.username}'
        )
        
    except Exception as e:
        flash(f'خطأ في إيقاف نظام الجدولة: {str(e)}', 'danger')
    
    return redirect(url_for('archive_scheduler_status'))

@app.route('/api/archive/scheduler/status')
@login_required
@require_archive_permission('viewer')
def archive_scheduler_status_api():
    """API للحصول على حالة نظام الجدولة"""
    
    try:
        from archive_scheduler import get_scheduler_status
        
        status = get_scheduler_status()
        return jsonify({
            'success': True,
            'status': status
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=4012, debug=True)
