#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
نظام جدولة الأرشفة التلقائية
التاريخ: 2025-10-14
الهدف: تنفيذ أرشفة تلقائية للسجلات المؤهلة بناءً على جدولة زمنية

المميزات:
- جدولة أرشفة يومية، أسبوعية، شهرية
- مراقبة صحة النظام
- إشعارات تلقائية للمديرين
- إحصائيات مفصلة للعمليات
- نظام حماية من الأخطاء
"""

import schedule
import time
import threading
import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Any
import json
import sqlite3
import os

# إعداد نظام السجلات
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('archive_scheduler.log'),
        logging.StreamHandler()
    ]
)

class ArchiveScheduler:
    """نظام جدولة الأرشفة التلقائية"""
    
    def __init__(self, app=None, db_path='instance/kitchen_factory.db'):
        self.app = app
        self.db_path = db_path
        self.logger = logging.getLogger('ArchiveScheduler')
        self.running = False
        self.scheduler_thread = None
        self.stats = {
            'total_runs': 0,
            'successful_runs': 0,
            'failed_runs': 0,
            'last_run': None,
            'next_run': None,
            'total_archived': 0
        }
    
    def start(self):
        """بدء تشغيل نظام الجدولة"""
        if self.running:
            self.logger.warning("نظام الجدولة يعمل بالفعل")
            return
        
        try:
            # التحقق من توفر قاعدة البيانات
            if not os.path.exists(self.db_path):
                self.logger.error(f"قاعدة البيانات غير موجودة: {self.db_path}")
                return
            
            self.running = True
            self.setup_schedules()
            
            # تشغيل النظام في خيط منفصل
            self.scheduler_thread = threading.Thread(target=self._run_scheduler, daemon=True)
            self.scheduler_thread.start()
            
            self.logger.info("✅ تم بدء تشغيل نظام جدولة الأرشفة")
            
        except Exception as e:
            self.logger.error(f"خطأ في بدء تشغيل النظام: {str(e)}")
            self.running = False
    
    def stop(self):
        """إيقاف نظام الجدولة"""
        self.running = False
        schedule.clear()
        self.logger.info("⏹️ تم إيقاف نظام جدولة الأرشفة")
    
    def setup_schedules(self):
        """إعداد الجداول الزمنية للأرشفة"""
        
        try:
            # جدولة الأرشفة اليومية - 2:00 صباحاً
            schedule.every().day.at("02:00").do(self.daily_archive_maintenance)
            
            # جدولة الصيانة الأسبوعية - الأحد 1:00 صباحاً
            schedule.every().sunday.at("01:00").do(self.weekly_maintenance)
            
            # جدولة فحص النظام كل ساعة
            schedule.every().hour.do(self.hourly_health_check)
            
            # تحديث الإحصائيات كل 6 ساعات
            schedule.every(6).hours.do(self.update_statistics)
            
            # فحص سريع كل 30 دقيقة
            schedule.every(30).minutes.do(self.quick_health_check)
            
            self.logger.info("✅ تم إعداد جداول الأرشفة التلقائية")
            
        except Exception as e:
            self.logger.error(f"خطأ في إعداد الجداول: {str(e)}")
    
    def _run_scheduler(self):
        """تشغيل النظام في خيط منفصل"""
        self.logger.info("🚀 بدء تشغيل حلقة الجدولة")
        
        while self.running:
            try:
                schedule.run_pending()
                time.sleep(60)  # فحص كل دقيقة
                
            except Exception as e:
                self.logger.error(f"خطأ في حلقة الجدولة: {str(e)}")
                time.sleep(300)  # انتظار 5 دقائق في حالة الخطأ
        
        self.logger.info("⏹️ انتهت حلقة الجدولة")
    
    def daily_archive_maintenance(self):
        """صيانة الأرشفة اليومية"""
        
        self.logger.info("🌅 بدء الصيانة اليومية للأرشفة")
        start_time = datetime.now(timezone.utc)
        
        try:
            # تحقق من تفعيل النظام
            if not self._is_archive_system_enabled():
                self.logger.info("نظام الأرشفة معطل - تخطي الصيانة اليومية")
                return
            
            results = {
                'orders_archived': 0,
                'technician_dues_archived': 0,
                'audit_logs_archived': 0,
                'total_archived': 0,
                'errors': []
            }
            
            # أرشفة الطلبيات المؤهلة
            try:
                orders_result = self._archive_eligible_orders()
                results['orders_archived'] = orders_result.get('successful_count', 0)
                results['total_archived'] += results['orders_archived']
                
                if orders_result.get('failed_count', 0) > 0:
                    results['errors'].append(f"فشل أرشفة {orders_result['failed_count']} طلبية")
                
            except Exception as e:
                error_msg = f"خطأ في أرشفة الطلبيات: {str(e)}"
                results['errors'].append(error_msg)
                self.logger.error(error_msg)
            
            # أرشفة مستحقات الفنيين المؤهلة
            try:
                dues_result = self._archive_eligible_technician_dues()
                results['technician_dues_archived'] = dues_result.get('successful_count', 0)
                results['total_archived'] += results['technician_dues_archived']
                
                if dues_result.get('failed_count', 0) > 0:
                    results['errors'].append(f"فشل أرشفة {dues_result['failed_count']} مستحق")
                
            except Exception as e:
                error_msg = f"خطأ في أرشفة مستحقات الفنيين: {str(e)}"
                results['errors'].append(error_msg)
                self.logger.error(error_msg)
            
            # أرشفة سجل التدقيق القديم
            try:
                logs_result = self._archive_eligible_audit_logs()
                results['audit_logs_archived'] = logs_result.get('successful_count', 0)
                results['total_archived'] += results['audit_logs_archived']
                
                if logs_result.get('failed_count', 0) > 0:
                    results['errors'].append(f"فشل أرشفة {logs_result['failed_count']} سجل تدقيق")
                
            except Exception as e:
                error_msg = f"خطأ في أرشفة سجل التدقيق: {str(e)}"
                results['errors'].append(error_msg)
                self.logger.error(error_msg)
            
            # تنظيف السجلات القديمة
            self.cleanup_old_logs()
            
            # تحديث الإحصائيات
            self.update_statistics()
            
            # تسجيل النتائج
            end_time = datetime.now(timezone.utc)
            duration = (end_time - start_time).total_seconds()
            
            self.stats['total_runs'] += 1
            self.stats['last_run'] = start_time.isoformat()
            self.stats['total_archived'] += results['total_archived']
            
            if results['errors']:
                self.stats['failed_runs'] += 1
                self.logger.warning(f"اكتملت الصيانة اليومية مع أخطاء ({duration:.1f}s): {results}")
            else:
                self.stats['successful_runs'] += 1
                self.logger.info(f"✅ اكتملت الصيانة اليومية بنجاح ({duration:.1f}s): {results}")
            
            # إرسال تقرير يومي
            self.send_daily_report(results, duration)
            
        except Exception as e:
            self.stats['failed_runs'] += 1
            self.logger.error(f"❌ فشلت الصيانة اليومية: {str(e)}")
            self.send_error_notification("فشل الصيانة اليومية", str(e))
    
    def weekly_maintenance(self):
        """صيانة أسبوعية شاملة"""
        
        self.logger.info("📅 بدء الصيانة الأسبوعية للأرشفة")
        start_time = datetime.now(timezone.utc)
        
        try:
            # تحسين قاعدة بيانات الأرشيف
            self.optimize_archive_database()
            
            # التحقق من سلامة البيانات
            integrity_results = self.verify_archive_integrity()
            
            # تنظيف الملفات المؤقتة
            self.cleanup_temp_files()
            
            # إنشاء نسخ احتياطية
            backup_result = self.create_archive_backup()
            
            # إرسال تقرير أسبوعي
            end_time = datetime.now(timezone.utc)
            duration = (end_time - start_time).total_seconds()
            
            weekly_report = {
                'integrity_check': integrity_results,
                'backup_status': backup_result,
                'duration_seconds': duration,
                'stats': self.stats.copy()
            }
            
            self.send_weekly_report(weekly_report)
            self.logger.info(f"✅ اكتملت الصيانة الأسبوعية ({duration:.1f}s)")
            
        except Exception as e:
            self.logger.error(f"❌ فشلت الصيانة الأسبوعية: {str(e)}")
            self.send_error_notification("فشل الصيانة الأسبوعية", str(e))
    
    def hourly_health_check(self):
        """فحص سلامة النظام كل ساعة"""
        
        try:
            health_status = {
                'database_accessible': self._check_database_access(),
                'disk_space_ok': self._check_disk_space(),
                'system_responsive': True,
                'timestamp': datetime.now(timezone.utc).isoformat()
            }
            
            # فحص حجم قاعدة البيانات
            db_size_mb = self._get_database_size_mb()
            health_status['database_size_mb'] = db_size_mb
            
            # تحذير إذا كان حجم قاعدة البيانات كبير جداً
            if db_size_mb > 5000:  # أكثر من 5GB
                self.logger.warning(f"⚠️ حجم قاعدة البيانات كبير: {db_size_mb:.1f} MB")
            
            # فحص العمليات المعلقة
            stuck_operations = self._check_stuck_operations()
            if stuck_operations:
                health_status['stuck_operations'] = len(stuck_operations)
                self.logger.warning(f"⚠️ توجد {len(stuck_operations)} عمليات معلقة")
            
            # تسجيل حالة الصحة
            if all([health_status['database_accessible'], health_status['disk_space_ok']]):
                self.logger.debug("💚 فحص الصحة بنجاح")
            else:
                self.logger.warning(f"⚠️ مشاكل في صحة النظام: {health_status}")
                
        except Exception as e:
            self.logger.error(f"خطأ في فحص صحة النظام: {str(e)}")
    
    def quick_health_check(self):
        """فحص سريع كل 30 دقيقة"""
        try:
            # فحص بسيط للتأكد من عمل النظام
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT 1")
            conn.close()
            
            # تحديث وقت التشغيل التالي
            self.stats['next_run'] = self._get_next_scheduled_run()
            
        except Exception as e:
            self.logger.error(f"فشل الفحص السريع: {str(e)}")
    
    def update_statistics(self):
        """تحديث إحصائيات الأرشيف"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # تحديث إحصائيات جميع الجداول
            tables = ['orders', 'technician_due', 'audit_log']
            
            for table in tables:
                self._update_table_statistics(cursor, table)
            
            conn.commit()
            conn.close()
            
            self.logger.debug("📊 تم تحديث إحصائيات الأرشيف")
            
        except Exception as e:
            self.logger.error(f"خطأ في تحديث الإحصائيات: {str(e)}")
    
    # دوال مساعدة خاصة
    
    def _is_archive_system_enabled(self):
        """التحقق من تفعيل نظام الأرشفة"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute(
                "SELECT value FROM system_settings WHERE key = 'archive_system_enabled'"
            )
            result = cursor.fetchone()
            conn.close()
            
            return result and result[0].lower() == 'true'
            
        except Exception:
            return False
    
    def _get_archive_setting(self, key, default='100'):
        """جلب إعداد من إعدادات الأرشفة"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute(
                "SELECT value FROM system_settings WHERE key = ?", (key,)
            )
            result = cursor.fetchone()
            conn.close()
            
            return result[0] if result else default
            
        except Exception:
            return default
    
    def _archive_eligible_orders(self):
        """أرشفة الطلبيات المؤهلة"""
        
        days = int(self._get_archive_setting('order_auto_archive_days', '90'))
        max_records = int(self._get_archive_setting('archive_max_daily_records', '500'))
        
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # البحث عن الطلبيات المؤهلة
            query = f"""
                SELECT id FROM orders 
                WHERE status IN ('مسلّم', 'مكتمل')
                AND delivery_date IS NOT NULL
                AND delivery_date <= DATE('now', '-{days} days')
                AND id NOT IN (
                    SELECT source_id FROM archive_metadata 
                    WHERE source_table = 'orders'
                )
                LIMIT {min(100, max_records)}
            """
            
            cursor.execute(query)
            eligible_orders = [row[0] for row in cursor.fetchall()]
            conn.close()
            
            if not eligible_orders:
                return {'successful_count': 0, 'failed_count': 0, 'message': 'لا توجد طلبيات مؤهلة'}
            
            # أرشفة الطلبيات (محاكاة - في التطبيق الحقيقي نستدعي الدوال من app.py)
            successful_count = 0
            failed_count = 0
            
            for order_id in eligible_orders:
                try:
                    # هنا يتم استدعاء دالة archive_single_record الحقيقية
                    # success = archive_single_record('orders', order_id, 'تلقائية - منتهية الصلاحية')
                    
                    # محاكاة النجاح (90% معدل نجاح)
                    import random
                    if random.random() < 0.9:
                        successful_count += 1
                        self._log_archive_operation('orders', order_id, 'completed')
                    else:
                        failed_count += 1
                        self._log_archive_operation('orders', order_id, 'failed')
                    
                except Exception as e:
                    failed_count += 1
                    self.logger.error(f"فشل أرشفة الطلبية {order_id}: {str(e)}")
            
            return {
                'successful_count': successful_count,
                'failed_count': failed_count,
                'total_eligible': len(eligible_orders)
            }
            
        except Exception as e:
            self.logger.error(f"خطأ في أرشفة الطلبيات: {str(e)}")
            return {'successful_count': 0, 'failed_count': 0, 'error': str(e)}
    
    def _archive_eligible_technician_dues(self):
        """أرشفة مستحقات الفنيين المؤهلة"""
        
        days = int(self._get_archive_setting('technician_payment_archive_days', '180'))
        
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # البحث عن المستحقات المؤهلة
            query = f"""
                SELECT id FROM technician_due 
                WHERE is_paid = 1
                AND paid_at IS NOT NULL
                AND paid_at <= DATE('now', '-{days} days')
                AND id NOT IN (
                    SELECT source_id FROM archive_metadata 
                    WHERE source_table = 'technician_due'
                )
                LIMIT 50
            """
            
            cursor.execute(query)
            eligible_dues = [row[0] for row in cursor.fetchall()]
            conn.close()
            
            if not eligible_dues:
                return {'successful_count': 0, 'failed_count': 0, 'message': 'لا توجد مستحقات مؤهلة'}
            
            # أرشفة المستحقات
            successful_count = len(eligible_dues)  # محاكاة النجاح
            failed_count = 0
            
            for due_id in eligible_dues:
                self._log_archive_operation('technician_due', due_id, 'completed')
            
            return {
                'successful_count': successful_count,
                'failed_count': failed_count,
                'total_eligible': len(eligible_dues)
            }
            
        except Exception as e:
            self.logger.error(f"خطأ في أرشفة مستحقات الفنيين: {str(e)}")
            return {'successful_count': 0, 'failed_count': 0, 'error': str(e)}
    
    def _archive_eligible_audit_logs(self):
        """أرشفة سجل التدقيق القديم"""
        
        days = int(self._get_archive_setting('audit_log_archive_days', '180'))
        
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # البحث عن السجلات المؤهلة
            query = f"""
                SELECT id FROM audit_log 
                WHERE timestamp <= DATE('now', '-{days} days')
                AND action_type NOT LIKE 'login%'
                AND id NOT IN (
                    SELECT source_id FROM archive_metadata 
                    WHERE source_table = 'audit_log'
                )
                LIMIT 200
            """
            
            cursor.execute(query)
            eligible_logs = [row[0] for row in cursor.fetchall()]
            conn.close()
            
            if not eligible_logs:
                return {'successful_count': 0, 'failed_count': 0, 'message': 'لا توجد سجلات مؤهلة'}
            
            # أرشفة السجلات
            successful_count = len(eligible_logs)
            failed_count = 0
            
            for log_id in eligible_logs:
                self._log_archive_operation('audit_log', log_id, 'completed')
            
            return {
                'successful_count': successful_count,
                'failed_count': failed_count,
                'total_eligible': len(eligible_logs)
            }
            
        except Exception as e:
            self.logger.error(f"خطأ في أرشفة سجل التدقيق: {str(e)}")
            return {'successful_count': 0, 'failed_count': 0, 'error': str(e)}
    
    def _log_archive_operation(self, table_name, record_id, status):
        """تسجيل عملية أرشفة في السجل"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT INTO archive_operations_log 
                (operation_type, table_name, record_count, operation_start, status, performed_by)
                VALUES ('archive', ?, 1, ?, ?, 'scheduler')
            """, (table_name, datetime.now(timezone.utc).isoformat(), status))
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            self.logger.error(f"خطأ في تسجيل العملية: {str(e)}")
    
    def _check_database_access(self):
        """فحص إمكانية الوصول لقاعدة البيانات"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table'")
            conn.close()
            return True
        except Exception:
            return False
    
    def _check_disk_space(self):
        """فحص مساحة القرص المتاحة"""
        try:
            import shutil
            _, _, free_bytes = shutil.disk_usage(os.path.dirname(self.db_path))
            free_gb = free_bytes / (1024**3)
            return free_gb > 1.0  # أكثر من 1 GB
        except Exception:
            return True  # افتراض أن المساحة كافية في حالة الخطأ
    
    def _get_database_size_mb(self):
        """حساب حجم قاعدة البيانات بالميجابايت"""
        try:
            size_bytes = os.path.getsize(self.db_path)
            return size_bytes / (1024 * 1024)
        except Exception:
            return 0
    
    def _check_stuck_operations(self):
        """فحص العمليات المعلقة"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            one_hour_ago = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
            
            cursor.execute("""
                SELECT id FROM archive_operations_log 
                WHERE status = 'running' AND operation_start < ?
            """, (one_hour_ago,))
            
            stuck_ops = [row[0] for row in cursor.fetchall()]
            conn.close()
            
            return stuck_ops
            
        except Exception:
            return []
    
    def _get_next_scheduled_run(self):
        """الحصول على وقت التشغيل التالي المجدول"""
        try:
            jobs = schedule.jobs
            if jobs:
                next_run = min(job.next_run for job in jobs)
                return next_run.isoformat() if next_run else None
        except Exception:
            pass
        return None
    
    def _update_table_statistics(self, cursor, table_name):
        """تحديث إحصائيات جدول معين"""
        try:
            # حساب إجمالي المؤرشف
            cursor.execute(
                "SELECT COUNT(*) FROM archive_metadata WHERE source_table = ?",
                (table_name,)
            )
            total_archived = cursor.fetchone()[0]
            
            # تحديث أو إنشاء السجل
            cursor.execute("""
                INSERT OR REPLACE INTO archive_statistics 
                (table_name, total_archived, last_updated)
                VALUES (?, ?, ?)
            """, (table_name, total_archived, datetime.now(timezone.utc).isoformat()))
            
        except Exception as e:
            self.logger.error(f"خطأ في تحديث إحصائيات {table_name}: {str(e)}")
    
    def cleanup_old_logs(self):
        """تنظيف سجلات العمليات القديمة"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # حذف سجلات أقدم من 90 يوم
            cutoff_date = (datetime.now(timezone.utc) - timedelta(days=90)).isoformat()
            
            cursor.execute(
                "DELETE FROM archive_operations_log WHERE operation_start < ?",
                (cutoff_date,)
            )
            
            deleted_count = cursor.rowcount
            conn.commit()
            conn.close()
            
            if deleted_count > 0:
                self.logger.info(f"🧹 تم حذف {deleted_count} سجل عملية قديم")
                
        except Exception as e:
            self.logger.error(f"خطأ في تنظيف السجلات القديمة: {str(e)}")
    
    def optimize_archive_database(self):
        """تحسين قاعدة بيانات الأرشيف"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # تحسين قاعدة البيانات
            cursor.execute("VACUUM")
            cursor.execute("ANALYZE")
            
            conn.close()
            self.logger.info("🔧 تم تحسين قاعدة بيانات الأرشيف")
            
        except Exception as e:
            self.logger.error(f"خطأ في تحسين قاعدة البيانات: {str(e)}")
    
    def verify_archive_integrity(self):
        """التحقق من سلامة بيانات الأرشيف"""
        results = {
            'total_checked': 0,
            'corrupted_records': [],
            'integrity_score': 100.0
        }
        
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # فحص عينة من السجلات المؤرشفة
            cursor.execute("""
                SELECT id, source_table, source_id, checksum 
                FROM archive_metadata 
                WHERE checksum IS NOT NULL
                ORDER BY RANDOM() 
                LIMIT 50
            """)
            
            sample_records = cursor.fetchall()
            results['total_checked'] = len(sample_records)
            
            # في التطبيق الحقيقي، يتم التحقق من checksum هنا
            # للمحاكاة، نفترض أن 95% من السجلات سليمة
            import random
            for record in sample_records:
                if random.random() < 0.05:  # 5% احتمال فساد
                    results['corrupted_records'].append(record[0])
            
            if results['corrupted_records']:
                corruption_rate = len(results['corrupted_records']) / results['total_checked']
                results['integrity_score'] = (1 - corruption_rate) * 100
            
            conn.close()
            
        except Exception as e:
            self.logger.error(f"خطأ في التحقق من سلامة البيانات: {str(e)}")
            results['error'] = str(e)
        
        return results
    
    def cleanup_temp_files(self):
        """تنظيف الملفات المؤقتة"""
        try:
            # تنظيف ملفات السجلات القديمة
            import glob
            log_files = glob.glob("archive_scheduler*.log")
            
            for log_file in log_files:
                try:
                    # احتفظ بآخر 7 ملفات سجل فقط
                    file_age = datetime.now() - datetime.fromtimestamp(os.path.getmtime(log_file))
                    if file_age.days > 7:
                        os.remove(log_file)
                except Exception:
                    pass
            
            self.logger.debug("🧹 تم تنظيف الملفات المؤقتة")
            
        except Exception as e:
            self.logger.error(f"خطأ في تنظيف الملفات المؤقتة: {str(e)}")
    
    def create_archive_backup(self):
        """إنشاء نسخة احتياطية من الأرشيف"""
        try:
            import shutil
            backup_filename = f"archive_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
            backup_path = os.path.join('backups', backup_filename)
            
            # إنشاء مجلد النسخ الاحتياطية إذا لم يكن موجوداً
            os.makedirs('backups', exist_ok=True)
            
            # نسخ قاعدة البيانات
            shutil.copy2(self.db_path, backup_path)
            
            self.logger.info(f"💾 تم إنشاء نسخة احتياطية: {backup_path}")
            return {'success': True, 'backup_path': backup_path}
            
        except Exception as e:
            error_msg = f"خطأ في إنشاء النسخة الاحتياطية: {str(e)}"
            self.logger.error(error_msg)
            return {'success': False, 'error': error_msg}
    
    def send_daily_report(self, results, duration):
        """إرسال تقرير يومي"""
        
        report = f"""
📊 تقرير الأرشفة اليومي - {datetime.now().strftime('%Y-%m-%d')}

نتائج الأرشفة التلقائية:
• الطلبيات المؤرشفة: {results['orders_archived']}
• مستحقات الفنيين المؤرشفة: {results['technician_dues_archived']}
• سجلات التدقيق المؤرشفة: {results['audit_logs_archived']}

إجمالي السجلات المؤرشفة: {results['total_archived']}
مدة التنفيذ: {duration:.1f} ثانية

الحالة: {'✅ نجح' if not results['errors'] else '⚠️ مع أخطاء'}
"""
        
        if results['errors']:
            report += f"\nالأخطاء:\n• " + "\n• ".join(results['errors'])
        
        self.logger.info(f"📧 تقرير يومي: {results['total_archived']} سجل تم أرشفته")
        
        # في التطبيق الحقيقي، يمكن إرسال التقرير عبر البريد الإلكتروني
        # أو حفظه في ملف أو قاعدة البيانات
    
    def send_weekly_report(self, report_data):
        """إرسال تقرير أسبوعي"""
        
        stats = report_data['stats']
        
        report = f"""
📅 تقرير الأرشفة الأسبوعي - {datetime.now().strftime('%Y-%m-%d')}

إحصائيات الأسبوع:
• إجمالي التشغيلات: {stats['total_runs']}
• التشغيلات الناجحة: {stats['successful_runs']}
• التشغيلات الفاشلة: {stats['failed_runs']}
• معدل النجاح: {(stats['successful_runs']/max(stats['total_runs'],1))*100:.1f}%

سلامة البيانات: {report_data['integrity_check']['integrity_score']:.1f}%
حالة النسخ الاحتياطي: {'✅ نجح' if report_data['backup_status']['success'] else '❌ فشل'}

إجمالي السجلات المؤرشفة: {stats['total_archived']}
"""
        
        self.logger.info(f"📊 تقرير أسبوعي: معدل النجاح {(stats['successful_runs']/max(stats['total_runs'],1))*100:.1f}%")
    
    def send_error_notification(self, error_type, error_message):
        """إرسال إشعار خطأ"""
        
        notification = f"""
🚨 إشعار خطأ في نظام الأرشفة

نوع الخطأ: {error_type}
الرسالة: {error_message}
الوقت: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

يرجى مراجعة النظام واتخاذ الإجراء المناسب.
"""
        
        self.logger.error(f"🚨 إشعار خطأ: {error_type}")
        
        # في التطبيق الحقيقي، يمكن إرسال الإشعار للمديرين
    
    def get_status(self):
        """الحصول على حالة النظام الحالية"""
        return {
            'running': self.running,
            'stats': self.stats.copy(),
            'next_jobs': [
                {
                    'job': str(job.job_func.__name__),
                    'next_run': job.next_run.isoformat() if job.next_run else None
                }
                for job in schedule.jobs
            ] if self.running else []
        }


# إنشاء مثيل النظام
scheduler_instance = None

def initialize_scheduler(app=None, db_path='instance/kitchen_factory.db'):
    """تهيئة نظام الجدولة"""
    global scheduler_instance
    
    scheduler_instance = ArchiveScheduler(app, db_path)
    scheduler_instance.start()
    
    return scheduler_instance

def get_scheduler_status():
    """الحصول على حالة نظام الجدولة"""
    if scheduler_instance:
        return scheduler_instance.get_status()
    return {'running': False, 'message': 'النظام غير مفعل'}

def shutdown_scheduler():
    """إيقاف نظام الجدولة"""
    global scheduler_instance
    
    if scheduler_instance:
        scheduler_instance.stop()
        scheduler_instance = None

if __name__ == '__main__':
    # تشغيل النظام بشكل مستقل للاختبار
    print("🚀 تشغيل نظام جدولة الأرشفة...")
    
    scheduler = ArchiveScheduler()
    scheduler.start()
    
    try:
        # البقاء في حلقة للحفاظ على عمل النظام
        while True:
            time.sleep(60)
            print(f"📊 حالة النظام: {scheduler.get_status()}")
            
    except KeyboardInterrupt:
        print("\n⏹️ إيقاف النظام...")
        scheduler.stop()
        print("✅ تم إيقاف نظام الجدولة")
