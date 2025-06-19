from flask import Flask, render_template, request, redirect, url_for, session
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
from flask import jsonify
from datetime import datetime
from flask import make_response
from openpyxl import Workbook
from io import BytesIO

app = Flask(__name__, template_folder='pages', static_folder='static')
app.secret_key = 'your_secret_key'

def init_db():
    conn = sqlite3.connect('AutoPro.db')
    cur = conn.cursor()
    cur.execute('DROP TABLE IF EXISTS users')
    cur.execute('DROP TABLE IF EXISTS orders')
    cur.execute('DROP TABLE IF EXISTS services')
    cur.execute('DROP TABLE IF EXISTS order_services')
    print("[LOG] Удаление базы данных")

    cur.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        )
    ''')

    cur.execute('''
        CREATE TABLE IF NOT EXISTS services (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            price INTEGER NOT NULL
        )
    ''')

    cur.execute('''
        CREATE TABLE IF NOT EXISTS orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        first_name TEXT NOT NULL,
        last_name TEXT NOT NULL,
        payment_method TEXT NOT NULL,
        total_cost REAL NOT NULL,
        status TEXT DEFAULT 'new',
        created_at TEXT NOT NULL,
        FOREIGN KEY (user_id) REFERENCES users(id)
        )
    ''')

    cur.execute('''
        CREATE TABLE IF NOT EXISTS order_services (
            order_id INTEGER NOT NULL,
            service_id INTEGER NOT NULL,
            PRIMARY KEY (order_id, service_id),
            FOREIGN KEY (order_id) REFERENCES orders(id),
            FOREIGN KEY (service_id) REFERENCES services(id)
        )
    ''')

    services_data = [
            ("Компьютерная диагностика", 5000),
            ("Диагностика подвески", 3500),
            ("Замена масла в двигателе", 2000),
            ("Замена масла в АКПП", 2500),
            ("Замена фильтров (комплекс)", 8000),
            ("Замена тормозных колодок", 3000),
            ("Замена тормозных дисков", 5000),
            ("Замена тормозной жидкости", 1500),
            ("Диагностика электрического оборудования", 2500),
            ("Замена аккумулятора", 2000),
            ("Чистка инжектора", 4000),
            ("Замена свечей зажигания", 3500),
            ("Замена ремня ГРМ", 6000),
            ("Замена жидкости ГУР", 4500)
    ]

    cur.executemany('INSERT INTO services (name, price) VALUES (?, ?)', services_data)

    print("[LOG] Инициализация базы данных")
    conn.commit()
    conn.close()

init_db()

@app.route('/export_orders_to_excel')
def export_orders_to_excel():
    if not session.get('username'):
        return redirect(url_for('login'))
    
    conn = sqlite3.connect('AutoPro.db')
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # Получаем все заказы
    cur.execute('''
        SELECT o.id, o.first_name, o.last_name, o.payment_method,
               o.total_cost, o.status, o.created_at
        FROM orders o
        ORDER BY o.created_at DESC
    ''')
    orders = cur.fetchall()

    # Создаем Excel файл
    wb = Workbook()
    ws = wb.active
    ws.title = "Все заказы"

    # Заголовки столбцов
    headers = [
        "№", "Имя", "Фамилия", "Метод оплаты",
        "Услуги", "Сумма", "Дата", "Статус"
    ]
    ws.append(headers)

    # Заполняем данные
    for idx, order in enumerate(orders, start=1):
        # Получаем услуги для каждого заказа
        cur.execute('''
            SELECT s.name
            FROM order_services os
            JOIN services s ON os.service_id = s.id
            WHERE os.order_id = ?
        ''', (order['id'],))
        services = cur.fetchall()
        service_names = [service['name'] for service in services]

        # Добавляем строку с данными
        ws.append([
            idx,
            order['first_name'],
            order['last_name'],
            order['payment_method'],
            ", ".join(service_names),
            order['total_cost'],
            order['created_at'],
            order['status']
        ])

    conn.close()

    # Создаем HTTP-ответ с файлом
    output = BytesIO()
    wb.save(output)
    output.seek(0)

    response = make_response(output.getvalue())
    response.headers['Content-Type'] = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    response.headers['Content-Disposition'] = f'attachment; filename=orders_export_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx'
    
    return response

@app.route('/')
def index():
    print(f"[LOG] Переход на главную страницу")
    return render_template('index.html')

@app.route('/about')
def about():
    print(f"[LOG] Переход на страницу 'О нас'")
    return render_template('about.html')

@app.route('/services')
def services():
    print(f"[LOG] Переход на страницу сервисов")
    return render_template('services.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    print("[LOG] Переход на страницу авторизации")
    msg = ''
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        print(f"[LOGIN] Введено имя: {username}, пароль: {password}")

        conn = sqlite3.connect('AutoPro.db')
        cur = conn.cursor()
        cur.execute('SELECT * FROM users WHERE username = ?', (username,))
        user = cur.fetchone()
        conn.close()

        if user and check_password_hash(user[3], password):
            session['user_id'] = user[0]
            session['username'] = user[1]
            print(f"[LOGIN] Успешный вход. ID: {user[0]}")
            return redirect(url_for('index'))
        else:
            msg = 'Неверный логин или пароль'
            print(f"[LOGIN] Ошибка входа для пользователя: {username}")
            return render_template('login.html', msg=msg, show_modal=True)
    return render_template('login.html')

@app.before_request
def validate_user_session():
    user_id = session.get('user_id')
    if user_id:
        conn = sqlite3.connect('AutoPro.db')
        cur = conn.cursor()
        cur.execute('SELECT id FROM users WHERE id = ?', (user_id,))
        user = cur.fetchone()
        conn.close()

        if not user:
            print("[SECURITY] Обнаружена сессия без валидного пользователя, сбрасываем.")
            session.clear()

@app.route('/register', methods=['GET', 'POST'])
def register():
    print("[LOG] Переход на страницу регистрации")
    msg = ''
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        print(f"[REGISTER] Введено имя: {username}, email: {email}, пароль: {password}")

        conn = sqlite3.connect('AutoPro.db')
        cur = conn.cursor()
        cur.execute('SELECT * FROM users WHERE username = ? OR email = ?', (username, email))
        existing_user = cur.fetchone()

        if existing_user:
            msg = 'Пользователь с таким логином или email уже существует.'
            print(f"[REGISTER] Ошибка регистрации для пользователя: {username}")
        else:
            hashed_password = generate_password_hash(password)
            cur.execute('INSERT INTO users (username, email, password) VALUES (?, ?, ?)',
                        (username, email, hashed_password))
            conn.commit()
            conn.close()
            msg = 'Регистрация прошла успешно!'
            return redirect(url_for('login'))

        conn.close()

    return render_template('register.html', msg=msg)

@app.route('/orders')
def orders_page():
    conn = sqlite3.connect('AutoPro.db')
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # Если пользователь авторизован (персонал) - показываем ВСЕ заказы
    if session.get('username'):
        cur.execute('''
            SELECT o.id, o.first_name, o.last_name, o.payment_method, 
                   o.total_cost, o.status, o.created_at
            FROM orders o
            ORDER BY o.created_at DESC
        ''')
    # Неавторизованные пользователи не имеют доступа к списку заказов
    else:
        conn.close()
        return redirect(url_for('index'))  # Или на страницу входа

    orders = cur.fetchall()

    # Получаем услуги для отображения
    cur.execute('SELECT id, name, price FROM services')
    services_data = cur.fetchall()
    services_dict = {row['id']: (row['name'], row['price']) for row in services_data}

    processed_orders = []
    for idx, order in enumerate(orders, start=1):
        # Получаем услуги для заказа
        cur.execute('''
            SELECT s.id, s.name, s.price
            FROM order_services os
            JOIN services s ON os.service_id = s.id
            WHERE os.order_id = ?
        ''', (order['id'],))
        order_services = cur.fetchall()

        processed_orders.append({
            'number': idx,
            'first_name': order['first_name'],
            'last_name': order['last_name'],
            'payment_method': order['payment_method'],
            'services': [(s['name'], s['price']) for s in order_services],
            'total_cost': order['total_cost'],
            'created_at': order['created_at'],
            'status': order['status']
        })

    conn.close()
    return render_template('orders.html', orders=processed_orders)

# Маршрут для создания заказа
@app.route('/order', methods=['POST'])
def order():
    data = request.get_json()
    created_at = datetime.now().strftime("%Y-%m-%d %H:%M")

    # Обязательные поля
    required_fields = ['firstName', 'lastName', 'paymentMethod', 'services', 'totalCost']
    if not all(field in data for field in required_fields):
        return jsonify({'error': 'Не все поля заполнены'}), 400

    conn = sqlite3.connect('AutoPro.db')
    cur = conn.cursor()

    try:
        # Для авторизованных user_id из сессии, для клиентов - NULL
        user_id = session.get('user_id')

        # Создаем заказ (user_id может быть NULL)
        cur.execute('''
            INSERT INTO orders (
                user_id, first_name, last_name, 
                payment_method, total_cost, created_at
            ) VALUES (?, ?, ?, ?, ?, ?)
        ''', (user_id, data['firstName'], data['lastName'], 
             data['paymentMethod'], data['totalCost'], created_at))
        
        order_id = cur.lastrowid
        
        # Добавляем услуги
        for service_id in data['services']:
            cur.execute('INSERT INTO order_services (order_id, service_id) VALUES (?, ?)', 
                       (order_id, service_id))
        
        conn.commit()
        return jsonify({'message': 'Заказ успешно оформлен!', 'order_id': order_id})
        
    except Exception as e:
        conn.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        conn.close()

@app.route('/logout')
def logout():
    print(f"[LOGOUT] Пользователь {session.get('username')} вышел из системы.")
    session.clear()
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True)