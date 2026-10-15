import time
from flask import Flask, g, request
from app.models import db
from app.routes import bp

def create_app(config_class=None):
    app = Flask(__name__)
    app.config['SECRET_KEY'] = 'dev-secret-key-iso-25010'
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///erp.db'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    if config_class:
        if isinstance(config_class, dict):
            app.config.update(config_class)
        else:
            app.config.from_object(config_class)

    if app.config.get('SQLALCHEMY_DATABASE_URI') == 'sqlite:///:memory:':
        from sqlalchemy.pool import StaticPool
        app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
            'connect_args': {'check_same_thread': False},
            'poolclass': StaticPool
        }

    db.init_app(app)
    app.register_blueprint(bp)

    # --- ISO/IEC 25010:2023 - Performance Efficiency (Time Behavior) ---
    # Interceptamos las peticiones para calcular el tiempo de respuesta
    @app.before_request
    def start_timer():
        g.start = time.time()

    @app.after_request
    def log_response_time(response):
        if hasattr(g, 'start'):
            exec_time = time.time() - g.start
            response.headers["X-Response-Time-Ms"] = str(round(exec_time * 1000, 2))
        return response

    with app.app_context():
        db.create_all()

        # Script de inicialización de datos base
        from app.models import Role, User, Client, Supplier, Product, EmployeePayment
        from werkzeug.security import generate_password_hash

        roles_needed = ['admin', 'almacen', 'contabilidad', 'cliente']
        for r_name in roles_needed:
            if not Role.query.filter_by(name=r_name).first():
                db.session.add(Role(name=r_name))
        db.session.commit()

        r_admin = Role.query.filter_by(name='admin').first()
        r_almacen = Role.query.filter_by(name='almacen').first()
        r_conta = Role.query.filter_by(name='contabilidad').first()

        # Cuentas distintas para cada área con contraseñas independientes
        if not User.query.filter_by(username='admin').first():
            db.session.add(User(
                username='admin',
                password_hash=generate_password_hash('admin123'),
                role_id=r_admin.id
            ))
        if not User.query.filter_by(username='almacen').first():
            db.session.add(User(
                username='almacen',
                password_hash=generate_password_hash('almacen123'),
                role_id=r_almacen.id
            ))
        if not User.query.filter_by(username='conta').first():
            db.session.add(User(
                username='conta',
                password_hash=generate_password_hash('conta123'),
                role_id=r_conta.id
            ))
        db.session.commit()

        # Semilla de proveedores para permitir registrar compras de inmediato
        if not Supplier.query.first():
            s1 = Supplier(name='Distribuidora Ferretera S.A.C.', ruc='20100011122', contact='Juan Pérez', phone='987654321', email='ventas@ferretera.com')
            s2 = Supplier(name='Herramientas y Construcción S.A.', ruc='20200033344', contact='Ana Gómez', phone='912345678', email='contacto@herramientas.com')
            db.session.add_all([s1, s2])
            db.session.commit()

        # Semilla de clientes para permitir registrar ventas de inmediato
        if not Client.query.first():
            c1 = Client(name='Carlos Mendoza', surname='', document='10234567', phone='998877665', email='carlos.mendoza@email.com')
            c2 = Client(name='María López', surname='', document='45678901', phone='955443322', email='maria.lopez@email.com')
            db.session.add_all([c1, c2])
            db.session.commit()

        # Semilla de productos (incluyendo stock bajo para el Dashboard)
        if not Product.query.first():
            p1 = Product(sku='PROD-001', name='Martillo de Acero 16oz', description='Martillo mango fibra', category='Herramientas', price_buy=15.0, price_sell=25.0, stock=20, stock_min=5)
            p2 = Product(sku='PROD-002', name='Cinta Métrica 5m', description='Cinta métrica con freno', category='Herramientas', price_buy=8.0, price_sell=14.0, stock=15, stock_min=5)
            p3 = Product(sku='PROD-003', name='Taladro Percutor 650W', description='Taladro velocidad variable', category='Maquinaria', price_buy=120.0, price_sell=180.0, stock=12, stock_min=5)
            db.session.add_all([p1, p2, p3])
            db.session.commit()

        # Semilla de pagos de personal
        if not EmployeePayment.query.first():
            admin_u = User.query.filter_by(username='admin').first()
            pay1 = EmployeePayment(
                employee_name='Roberto Quispe',
                dni='40123456',
                position='Encargado de Almacén',
                amount=1200.0,
                concept='Sueldo mensual - Almacén',
                user_id=admin_u.id if admin_u else None
            )
            pay2 = EmployeePayment(
                employee_name='Lucía Torres',
                dni='41234567',
                position='Asistente de Contabilidad',
                amount=1350.0,
                concept='Sueldo mensual - Contabilidad',
                user_id=admin_u.id if admin_u else None
            )
            db.session.add_all([pay1, pay2])
            db.session.commit()

    return app