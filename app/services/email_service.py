import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from flask import current_app
from ..models.user_models import EmailRecipient, User
from ..core.extensions import db

def send_email(subject, html_body):
    """Отправляет email-сообщение с указанной темой и HTML-содержимым."""
    config = current_app.config
    sender_email = config['MAIL_USERNAME']
    recipients_from_db = db.session.query(User.email).join(EmailRecipient).all()
    recipients = [email for email, in recipients_from_db]

    # --- НАЧАЛО БЛОКА ЛОГИРОВАНИЯ ---
    print("\n" + "=" * 50)
    print("[EMAIL SERVICE] 📨 НАЧАЛО ПРОЦЕССА ОТПРАВКИ ПИСЬМА")
    print(f"[EMAIL SERVICE] Отправитель: {sender_email}")
    print(f"[EMAIL SERVICE] Получатели: {recipients}")
    print(f"[EMAIL SERVICE] Тема: {subject}")
    # --- КОНЕЦ БЛОКА ЛОГИРОВАНИЯ ---

    if not recipients or not recipients[0] or "example.com" in recipients[0]:
        print("[EMAIL SERVICE] ❌ ОШИБКА: Получатели не заданы или используется адрес-заглушка.")
        print("[EMAIL SERVICE] Пожалуйста, укажите реальный адрес в MAIL_RECIPIENTS в файле config.py.")
        print("=" * 50 + "\n")
        return

    msg = MIMEMultipart('alternative')
    msg['Subject'] = subject
    msg['From'] = sender_email
    msg['To'] = ", ".join(recipients)

    part = MIMEText(html_body, 'html')
    msg.attach(part)

    try:
        print(f"[EMAIL SERVICE] Попытка подключения к серверу: {config['MAIL_SERVER']}:{config['MAIL_PORT']}")
        server = smtplib.SMTP(config['MAIL_SERVER'], config['MAIL_PORT'])

        # --- ВКЛЮЧАЕМ РАСШИРЕННЫЙ РЕЖИМ ОТЛАДКИ ---
        # Этот режим покажет в консоли весь диалог между нашим приложением и почтовым сервером.
        server.set_debuglevel(1)
        # --------------------------------------------

        if config['MAIL_USE_TLS']:
            print("[EMAIL SERVICE] Попытка запуска TLS...")
            server.starttls()
            print("[EMAIL SERVICE] TLS запущен.")

        print(f"[EMAIL SERVICE] Попытка авторизации с пользователем: {config['MAIL_USERNAME']}...")
        server.login(config['MAIL_USERNAME'], config['MAIL_PASSWORD'])
        print("[EMAIL SERVICE] Авторизация прошла успешно.")

        print("[EMAIL SERVICE] Попытка отправки письма...")
        server.sendmail(sender_email, recipients, msg.as_string())
        print("[EMAIL SERVICE] Команда отправки выполнена.")

    except Exception as e:
        print(f"[EMAIL SERVICE] ❌ КРИТИЧЕСКАЯ ОШИБКА ПРИ ОТПРАВКЕ: {type(e).__name__}: {e}")
    finally:
        # Убеждаемся, что сессия с сервером всегда закрывается
        if 'server' in locals() and server:
            print("[EMAIL SERVICE] Попытка закрытия соединения с сервером...")
            server.quit()
        print("[EMAIL SERVICE] 🏁 ЗАВЕРШЕНИЕ ПРОЦЕССА ОТПРАВКИ")
        print("=" * 50 + "\n")