from functools import wraps
from flask import Blueprint, flash, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash
from app.models import (
    Client, EmployeePayment, Product, Purchase, PurchaseItem,
    Role, Sale, SaleItem, Supplier, User, db
)

bp = Blueprint('main', __name__)

def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if 'role' not in session:
            flash('Por favor inicia sesión para continuar.', 'error')
            return redirect(url_for('main.login'))
        return view(*args, **kwargs)
    return wrapped

def role_required(*allowed_roles):
    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if 'role' not in session:
                flash('Por favor inicia sesión para acceder al módulo.', 'error')
                return redirect(url_for('main.login'))
            user_role = session.get('role')
            if user_role not in allowed_roles:
                flash(f'Acceso no autorizado a este módulo. Tu rol actual es: {user_role}.', 'error')
                if user_role == 'cliente':
                    return redirect(url_for('main.tienda'))
                elif user_role == 'almacen':
                    return redirect(url_for('main.almacen'))
                elif user_role == 'contabilidad':
                    return redirect(url_for('main.contabilidad'))
                elif user_role == 'admin':
                    return redirect(url_for('main.administracion'))
                return redirect(url_for('main.login'))
            return view(*args, **kwargs)
        return wrapped
    return decorator

@bp.route('/')
def index():
    if 'role' in session:
        role = session.get('role')
        if role == 'cliente':
            return redirect(url_for('main.tienda'))
        elif role == 'almacen':
            return redirect(url_for('main.almacen'))
        elif role == 'contabilidad':
            return redirect(url_for('main.contabilidad'))
        elif role == 'admin':
            return redirect(url_for('main.administracion'))
    return redirect(url_for('main.login'))

@bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        login_type = request.form.get('login_type', 'staff')

        # 1. Acceso Clientes (Tienda Virtual): solo celular, nombre y DNI
        if login_type == 'client':
            name = request.form.get('client_name', '').strip()
            document = request.form.get('client_document', '').strip()
            phone = request.form.get('client_phone', '').strip()

            if not name or not document or not phone:
                flash('Debes ingresar tu nombre, DNI y número de celular para entrar a la tienda.', 'error')
                return redirect(url_for('main.login'))

            client = Client.query.filter_by(document=document).first()
            if not client:
                client = Client(name=name, surname='', document=document, phone=phone)
                db.session.add(client)
                db.session.commit()
            else:
                client.name = name or client.name
                client.phone = phone or client.phone
                db.session.commit()

            session.clear()
            session['client_id'] = client.id
            session['username'] = client.name
            session['client_name'] = client.name
            session['client_doc'] = client.document
            session['role'] = 'cliente'
            flash(f'¡Bienvenido a la Tienda, {client.name}!', 'success')
            return redirect(url_for('main.tienda'))

        # 2. Acceso Personal / Administración (admin, almacen, contabilidad)
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        user = User.query.filter_by(username=username).first()

        if user and check_password_hash(user.password_hash, password):
            session.clear()
            session['user_id'] = user.id
            session['username'] = user.username
            role_name = user.role.name if user.role else 'admin'
            session['role'] = role_name

            flash(f'Bienvenido al sistema, {user.username}. Rol: {role_name.capitalize()}', 'success')
            if role_name == 'almacen':
                return redirect(url_for('main.almacen'))
            elif role_name == 'contabilidad':
                return redirect(url_for('main.contabilidad'))
            else:
                return redirect(url_for('main.administracion'))

        flash('Credenciales de administración inválidas', 'error')

    return render_template('login.html')

@bp.route('/tienda/login', methods=['POST'])
def tienda_login():
    name = request.form.get('client_name', '').strip()
    document = request.form.get('client_document', '').strip()
    phone = request.form.get('client_phone', '').strip()

    if not name or not document or not phone:
        flash('Debes ingresar tu nombre, DNI y número de celular para identificarte.', 'error')
        return redirect(url_for('main.tienda'))

    client = Client.query.filter_by(document=document).first()
    if not client:
        client = Client(name=name, surname='', document=document, phone=phone)
        db.session.add(client)
        db.session.commit()
    else:
        client.name = name or client.name
        client.phone = phone or client.phone
        db.session.commit()

    session.clear()
    session['client_id'] = client.id
    session['username'] = client.name
    session['client_name'] = client.name
    session['client_doc'] = client.document
    session['role'] = 'cliente'
    flash(f'¡Sesión iniciada en la Tienda como {client.name}!', 'success')
    return redirect(url_for('main.tienda'))

@bp.route('/logout')
def logout():
    session.clear()
    flash('Has cerrado sesión correctamente.', 'success')
    return redirect(url_for('main.login'))

# ==============================================================================
# MÓDULO 1: ADMINISTRACIÓN (Compras y Ventas de la empresa, Pagos del Personal)
# ==============================================================================
@bp.route('/administracion', methods=['GET', 'POST'])
@role_required('admin')
def administracion():
    if request.method == 'POST':
        action = request.form.get('action')

        # 1. Registrar Compra de la Empresa
        if action == 'compra':
            try:
                supplier_id = int(request.form.get('supplier_id', 0))
                product_id = int(request.form.get('product_id', 0))
                quantity = int(request.form.get('quantity', 0) or 0)
                unit_price = float(request.form.get('unit_price', 0) or 0)
            except (ValueError, TypeError):
                flash('Valores numéricos inválidos en la compra', 'error')
                return redirect(url_for('main.administracion'))

            supplier = db.session.get(Supplier, supplier_id)
            product = db.session.get(Product, product_id)
            if not supplier or not product or quantity <= 0 or unit_price <= 0:
                flash('Debe completar proveedor, producto, cantidad (>0) y costo unitario (>0).', 'error')
                return redirect(url_for('main.administracion'))

            subtotal = quantity * unit_price
            user_id = session.get('user_id')
            purchase = Purchase(supplier_id=supplier.id, user_id=user_id, total=subtotal)
            db.session.add(purchase)
            db.session.flush()

            db.session.add(PurchaseItem(
                purchase_id=purchase.id,
                product_id=product.id,
                quantity=quantity,
                unit_price=unit_price,
                subtotal=subtotal,
            ))

            product.stock += quantity
            product.price_buy = unit_price
            db.session.commit()
            flash(f'Compra registrada. El stock de "{product.name}" aumentó a {product.stock} unidades (actualizado en Almacén y Tienda).', 'success')
            return redirect(url_for('main.administracion'))

        # 2. Registrar Venta de la Empresa
        elif action == 'venta':
            try:
                client_id = int(request.form.get('client_id', 0))
                product_id = int(request.form.get('product_id', 0))
                quantity = int(request.form.get('quantity', 0) or 0)
                unit_price = float(request.form.get('unit_price', 0) or 0)
            except (ValueError, TypeError):
                flash('Valores numéricos inválidos en la venta', 'error')
                return redirect(url_for('main.administracion'))

            client = db.session.get(Client, client_id)
            product = db.session.get(Product, product_id)
            if not client or not product or quantity <= 0 or unit_price <= 0:
                flash('Debe completar cliente, producto, cantidad (>0) y precio (>0).', 'error')
                return redirect(url_for('main.administracion'))

            if product.stock < quantity:
                flash(f'Stock insuficiente para vender {quantity} unidades de "{product.name}". Disponible: {product.stock}.', 'error')
                return redirect(url_for('main.administracion'))

            subtotal = quantity * unit_price
            sale = Sale(client_id=client.id, user_id=session.get('user_id'), total=subtotal, origin='administracion')
            db.session.add(sale)
            db.session.flush()

            db.session.add(SaleItem(
                sale_id=sale.id,
                product_id=product.id,
                quantity=quantity,
                unit_price=unit_price,
                subtotal=subtotal,
            ))

            product.stock -= quantity
            product.price_sell = unit_price
            db.session.commit()
            flash(f'Venta corporativa registrada. Nuevo stock de "{product.name}": {product.stock} unidades (sincronizado en Almacén).', 'success')
            return redirect(url_for('main.administracion'))

        # 3. Registrar Pago de Personal
        elif action == 'pago_personal':
            employee_name = request.form.get('employee_name', '').strip()
            dni = request.form.get('dni', '').strip()
            position = request.form.get('position', '').strip()
            concept = request.form.get('concept', '').strip()
            try:
                amount = float(request.form.get('amount', 0) or 0)
            except (ValueError, TypeError):
                amount = 0.0

            if not employee_name or amount <= 0:
                flash('Debe indicar el nombre del empleado y un monto válido a pagar.', 'error')
                return redirect(url_for('main.administracion'))

            payment = EmployeePayment(
                employee_name=employee_name,
                dni=dni,
                position=position,
                amount=amount,
                concept=concept or 'Pago de haberes / nómina',
                user_id=session.get('user_id')
            )
            db.session.add(payment)
            db.session.commit()
            flash(f'Pago de personal registrado correctamente: ${amount:.2f} a {employee_name} (reportado a Contabilidad).', 'success')
            return redirect(url_for('main.administracion'))

    # Datos para la vista de Administración
    suppliers = Supplier.query.order_by(Supplier.name).all()
    clients = Client.query.order_by(Client.name).all()
    products = Product.query.order_by(Product.name).all()
    purchases = Purchase.query.order_by(Purchase.created_at.desc()).all()
    sales = Sale.query.order_by(Sale.created_at.desc()).all()
    payments = EmployeePayment.query.order_by(EmployeePayment.payment_date.desc()).all()

    total_purchases = sum(p.total for p in purchases)
    total_sales = sum(s.total for s in sales)
    total_payroll = sum(p.amount for p in payments)

    return render_template(
        'administracion.html',
        suppliers=suppliers,
        clients=clients,
        products=products,
        purchases=purchases,
        sales=sales,
        payments=payments,
        total_purchases=total_purchases,
        total_sales=total_sales,
        total_payroll=total_payroll,
    )

# ==============================================================================
# MÓDULO 2: ALMACÉN (Stock e Inventario en tiempo real)
# ==============================================================================
@bp.route('/almacen', methods=['GET', 'POST'])
@role_required('almacen', 'admin')
def almacen():
    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'nuevo_producto':
            sku = request.form.get('sku', '').strip()
            name = request.form.get('name', '').strip()
            category = request.form.get('category', '').strip()
            description = request.form.get('description', '').strip()
            try:
                price_buy = float(request.form.get('price_buy', 0) or 0)
                price_sell = float(request.form.get('price_sell', 0) or 0)
                stock = int(request.form.get('stock', 0) or 0)
                stock_min = int(request.form.get('stock_min', 5) or 5)
            except (ValueError, TypeError):
                flash('Valores numéricos inválidos en el producto', 'error')
                return redirect(url_for('main.almacen'))

            if not sku or not name or not category:
                flash('SKU, nombre y categoría son obligatorios.', 'error')
                return redirect(url_for('main.almacen'))

            if Product.query.filter_by(sku=sku).first():
                flash(f'El SKU "{sku}" ya se encuentra registrado.', 'error')
                return redirect(url_for('main.almacen'))

            product = Product(
                sku=sku, name=name, description=description, category=category,
                price_buy=price_buy, price_sell=price_sell, stock=stock, stock_min=stock_min
            )
            db.session.add(product)
            db.session.commit()
            flash(f'Producto "{name}" añadido exitosamente al almacén y catálogo general.', 'success')
            return redirect(url_for('main.almacen'))

    products = Product.query.order_by(Product.name).all()
    low_stock = [p for p in products if p.stock <= p.stock_min]
    total_units = sum(p.stock for p in products)
    
    # Movimientos físicos recientes (entradas por compras y salidas por ventas)
    recent_purchases = Purchase.query.order_by(Purchase.created_at.desc()).limit(6).all()
    recent_sales = Sale.query.order_by(Sale.created_at.desc()).limit(6).all()

    return render_template(
        'almacen.html',
        products=products,
        low_stock=low_stock,
        total_units=total_units,
        recent_purchases=recent_purchases,
        recent_sales=recent_sales,
    )

# ==============================================================================
# MÓDULO 3: TIENDA (Compra y Venta a nivel cliente)
# ==============================================================================
@bp.route('/tienda')
def tienda():
    products = Product.query.order_by(Product.name).all()
    client = None
    sales = []
    if session.get('client_id'):
        client = db.session.get(Client, session['client_id'])
        if client:
            sales = (
                Sale.query.filter_by(client_id=client.id, origin='tienda')
                .order_by(Sale.created_at.desc())
                .all()
            )

    cart = session.get('shopping_cart', {})
    cart_quantities = {}
    for product_id, quantity in cart.items():
        try:
            parsed_product_id = int(product_id)
        except (ValueError, TypeError):
            continue
        if isinstance(quantity, int) and quantity > 0:
            cart_quantities[parsed_product_id] = quantity
    cart_items = [
        {
            'product': product,
            'quantity': cart_quantities.get(product.id, 0),
            'subtotal': product.price_sell * cart_quantities.get(product.id, 0),
        }
        for product in products
        if cart_quantities.get(product.id, 0) > 0
    ]

    return render_template(
        'tienda.html',
        products=products,
        client=client,
        sales=sales,
        cart_items=cart_items,
        cart_quantities=cart_quantities,
        cart_quantity=sum(cart_quantities.values()),
        cart_total=sum(item['subtotal'] for item in cart_items),
    )

@bp.route('/tienda/comprar', methods=['POST'])
def tienda_comprar():
    client_id = session.get('client_id')
    if not client_id or session.get('role') != 'cliente':
        flash('Identifícate para agregar productos al carrito.', 'error')
        return redirect(url_for('main.tienda'))

    try:
        product_id = int(request.form.get('product_id', 0))
        quantity = int(request.form.get('quantity', 1) or 1)
    except (ValueError, TypeError):
        flash('Datos de compra inválidos', 'error')
        return redirect(url_for('main.tienda'))

    product = db.session.get(Product, product_id)
    if not product or quantity <= 0:
        flash('Producto no encontrado o cantidad inválida.', 'error')
        return redirect(url_for('main.tienda'))

    cart = session.get('shopping_cart', {})
    current_quantity = cart.get(str(product_id), 0)
    if not isinstance(current_quantity, int) or current_quantity < 0:
        current_quantity = 0

    if product.stock < current_quantity + quantity:
        flash(f'Lo sentimos, solo quedan {product.stock} unidades disponibles de "{product.name}".', 'error')
        return redirect(url_for('main.tienda'))

    cart[str(product_id)] = current_quantity + quantity
    session['shopping_cart'] = cart
    return redirect(url_for('main.tienda'))

@bp.route('/tienda/carrito/<int:product_id>/quitar', methods=['POST'])
def tienda_quitar_del_carrito(product_id):
    if not session.get('client_id') or session.get('role') != 'cliente':
        flash('Identifícate para modificar el carrito.', 'error')
        return redirect(url_for('main.tienda'))

    cart = session.get('shopping_cart', {})
    if str(product_id) not in cart:
        flash('El producto no está en el carrito.', 'error')
        return redirect(url_for('main.tienda'))

    cart.pop(str(product_id))
    session['shopping_cart'] = cart
    return redirect(url_for('main.tienda'))

@bp.route('/tienda/finalizar-compra', methods=['POST'])
def tienda_finalizar_compra():
    client_id = session.get('client_id')
    if not client_id or session.get('role') != 'cliente':
        flash('Identifícate para finalizar la compra.', 'error')
        return redirect(url_for('main.tienda'))

    client = db.session.get(Client, client_id)
    if not client:
        session.pop('shopping_cart', None)
        flash('No se encontró tu cuenta de cliente. Identifícate nuevamente.', 'error')
        return redirect(url_for('main.tienda'))

    cart = session.get('shopping_cart', {})
    if not cart:
        flash('El carrito está vacío.', 'error')
        return redirect(url_for('main.tienda'))

    order_items = []
    total = 0
    for product_id, quantity in cart.items():
        try:
            parsed_product_id = int(product_id)
        except (ValueError, TypeError):
            flash('El carrito contiene un producto inválido. Revísalo antes de continuar.', 'error')
            return redirect(url_for('main.tienda'))

        product = db.session.get(Product, parsed_product_id)
        if not product or not isinstance(quantity, int) or quantity <= 0:
            flash('El carrito contiene un producto o una cantidad inválida.', 'error')
            return redirect(url_for('main.tienda'))
        if product.stock < quantity:
            flash(f'Stock insuficiente para "{product.name}". Disponible: {product.stock}.', 'error')
            return redirect(url_for('main.tienda'))

        subtotal = quantity * product.price_sell
        order_items.append((product, quantity, subtotal))
        total += subtotal

    sale = Sale(client_id=client_id, user_id=None, total=total, origin='tienda')
    db.session.add(sale)
    db.session.flush()

    for product, quantity, subtotal in order_items:
        db.session.add(SaleItem(
            sale_id=sale.id,
            product_id=product.id,
            quantity=quantity,
            unit_price=product.price_sell,
            subtotal=subtotal,
        ))
        product.stock -= quantity

    db.session.commit()
    session.pop('shopping_cart', None)
    return redirect(url_for('main.tienda_mis_pedidos'))

@bp.route('/tienda/mis-pedidos')
def tienda_mis_pedidos():
    client_id = session.get('client_id')
    if not client_id:
        flash('Por favor identifícate para ver tus pedidos.', 'error')
        return redirect(url_for('main.tienda'))

    return redirect(url_for('main.tienda'))

@bp.route('/tienda/mis-pedidos/<int:sale_id>/eliminar', methods=['POST'])
def eliminar_pedido_tienda(sale_id):
    client_id = session.get('client_id')
    if not client_id:
        flash('Por favor identifícate para eliminar un pedido.', 'error')
        return redirect(url_for('main.tienda'))

    sale = Sale.query.filter_by(id=sale_id, client_id=client_id, origin='tienda').first()
    if not sale:
        flash('No se encontró el pedido o no tienes permiso para eliminarlo.', 'error')
        return redirect(url_for('main.tienda_mis_pedidos'))

    for item in sale.items:
        product = db.session.get(Product, item.product_id)
        if product:
            product.stock += item.quantity

    sale_id_for_message = sale.id
    for item in sale.items:
        db.session.delete(item)
    db.session.delete(sale)
    db.session.commit()

    flash(f'El pedido #{sale_id_for_message} fue eliminado y los productos se devolvieron al inventario.', 'success')
    return redirect(url_for('main.tienda_mis_pedidos'))

# ==============================================================================
# MÓDULO 4: CONTABILIDAD (Ingresos, Egresos y Balance General)
# ==============================================================================
@bp.route('/contabilidad')
@role_required('contabilidad', 'admin')
def contabilidad():
    sales = Sale.query.order_by(Sale.created_at.desc()).all()
    purchases = Purchase.query.order_by(Purchase.created_at.desc()).all()
    payroll = EmployeePayment.query.order_by(EmployeePayment.payment_date.desc()).all()

    # Ingresos (Todas las ventas: tienda virtual + corporativas)
    total_ingresos = sum(s.total for s in sales)
    tienda_ingresos = sum(s.total for s in sales if s.origin == 'tienda')
    admin_ingresos = sum(s.total for s in sales if s.origin != 'tienda')

    # Egresos (Compras a proveedores + Pagos del personal)
    total_compras = sum(p.total for p in purchases)
    total_sueldos = sum(p.amount for p in payroll)
    total_egresos = total_compras + total_sueldos

    # Balance Financiero Neto
    balance_neto = total_ingresos - total_egresos

    return render_template(
        'contabilidad.html',
        sales=sales,
        purchases=purchases,
        payroll=payroll,
        total_ingresos=total_ingresos,
        tienda_ingresos=tienda_ingresos,
        admin_ingresos=admin_ingresos,
        total_compras=total_compras,
        total_sueldos=total_sueldos,
        total_egresos=total_egresos,
        balance_neto=balance_neto,
    )

# ==============================================================================
# Rutas de Redirección y Compatibilidad
# ==============================================================================
@bp.route('/dashboard')
@login_required
def dashboard():
    role = session.get('role')
    if role == 'almacen':
        return redirect(url_for('main.almacen'))
    elif role == 'contabilidad':
        return redirect(url_for('main.contabilidad'))
    elif role == 'cliente':
        return redirect(url_for('main.tienda'))
    return redirect(url_for('main.administracion'))

@bp.route('/products', methods=['GET', 'POST'])
@login_required
def products():
    return redirect(url_for('main.almacen'))

@bp.route('/purchases', methods=['GET', 'POST'])
@login_required
def purchases():
    return redirect(url_for('main.administracion'))

@bp.route('/sales', methods=['GET', 'POST'])
@login_required
def sales():
    return redirect(url_for('main.administracion'))

@bp.route('/reports')
@login_required
def reports():
    return redirect(url_for('main.contabilidad'))

@bp.route('/clients', methods=['GET', 'POST'])
@login_required
def clients():
    return redirect(url_for('main.administracion'))

@bp.route('/suppliers', methods=['GET', 'POST'])
@login_required
def suppliers():
    return redirect(url_for('main.administracion'))
