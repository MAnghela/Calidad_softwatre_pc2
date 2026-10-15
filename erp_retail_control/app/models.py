from datetime import datetime, timezone
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

# ---------------------------------------------------------
# ISO/IEC 25010:2023 - Maintainability (Modularity & Analysability)
# Separación en modelos ORM claros. Facilita extender el sistema.
# ---------------------------------------------------------

class Role(db.Model):
    __tablename__ = 'roles'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)
    users = db.relationship('User', back_populates='role')

class User(db.Model):
    __tablename__ = 'usuarios'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    # ISO 25010:2023 - Security (Confidentiality). Protege los datos contra lectura no autorizada.
    password_hash = db.Column(db.String(256), nullable=False)
    role_id = db.Column(db.Integer, db.ForeignKey('roles.id'), nullable=False)
    role = db.relationship('Role', back_populates='users')

class Client(db.Model):
    __tablename__ = 'clientes'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    surname = db.Column(db.String(100), nullable=True, default='')
    document = db.Column(db.String(20), unique=True, nullable=False)
    phone = db.Column(db.String(50))
    address = db.Column(db.String(200))
    email = db.Column(db.String(100))
    active = db.Column(db.Boolean, default=True)

    def __init__(self, **kwargs):
        if 'dni' in kwargs and 'document' not in kwargs:
            kwargs['document'] = kwargs.pop('dni')
        super().__init__(**kwargs)

    @property
    def dni(self):
        return self.document

    @dni.setter
    def dni(self, value):
        self.document = value

class Supplier(db.Model):
    __tablename__ = 'proveedores'
    id = db.Column(db.Integer, primary_key=True)
    ruc = db.Column(db.String(20), unique=True, nullable=True)
    name = db.Column(db.String(100), nullable=False)
    contact = db.Column(db.String(100))
    phone = db.Column(db.String(50))
    email = db.Column(db.String(100))
    address = db.Column(db.String(200))
    active = db.Column(db.Boolean, default=True)

class Product(db.Model):
    __tablename__ = 'productos'
    id = db.Column(db.Integer, primary_key=True)
    sku = db.Column(db.String(50), unique=True, nullable=False)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    category = db.Column(db.String(50))
    price_buy = db.Column(db.Float, nullable=False, default=0.0)
    price_sell = db.Column(db.Float, nullable=False, default=0.0)
    stock = db.Column(db.Integer, nullable=False, default=0)
    stock_min = db.Column(db.Integer, nullable=False, default=5)

class Purchase(db.Model):
    __tablename__ = 'compras'
    id = db.Column(db.Integer, primary_key=True)
    supplier_id = db.Column(db.Integer, db.ForeignKey('proveedores.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=False)
    total = db.Column(db.Float, nullable=False, default=0.0)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    items = db.relationship('PurchaseItem', back_populates='purchase')
    supplier = db.relationship('Supplier')
    user = db.relationship('User')

class PurchaseItem(db.Model):
    __tablename__ = 'detalle_compra'
    id = db.Column(db.Integer, primary_key=True)
    purchase_id = db.Column(db.Integer, db.ForeignKey('compras.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('productos.id'), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    unit_price = db.Column(db.Float, nullable=False)
    subtotal = db.Column(db.Float, nullable=False)
    purchase = db.relationship('Purchase', back_populates='items')
    product = db.relationship('Product')

class Sale(db.Model):
    __tablename__ = 'ventas'
    id = db.Column(db.Integer, primary_key=True)
    client_id = db.Column(db.Integer, db.ForeignKey('clientes.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=True)
    total = db.Column(db.Float, nullable=False, default=0.0)
    origin = db.Column(db.String(20), default='tienda') # 'tienda' o 'administracion'
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    items = db.relationship('SaleItem', back_populates='sale')
    client = db.relationship('Client')
    user = db.relationship('User')

class SaleItem(db.Model):
    __tablename__ = 'detalle_venta'
    id = db.Column(db.Integer, primary_key=True)
    sale_id = db.Column(db.Integer, db.ForeignKey('ventas.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('productos.id'), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    unit_price = db.Column(db.Float, nullable=False)
    subtotal = db.Column(db.Float, nullable=False)
    sale = db.relationship('Sale', back_populates='items')
    product = db.relationship('Product')

class EmployeePayment(db.Model):
    __tablename__ = 'pagos_personal'
    id = db.Column(db.Integer, primary_key=True)
    employee_name = db.Column(db.String(100), nullable=False)
    dni = db.Column(db.String(20), nullable=True)
    position = db.Column(db.String(100), nullable=True)
    amount = db.Column(db.Float, nullable=False, default=0.0)
    concept = db.Column(db.String(200), nullable=False, default='Pago de sueldo')
    payment_date = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    user_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=True)
    user = db.relationship('User')
