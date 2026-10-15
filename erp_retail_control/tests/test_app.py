from app import create_app


def test_login_page_loads():
    app = create_app({'TESTING': True, 'SQLALCHEMY_DATABASE_URI': 'sqlite:///:memory:'})
    with app.test_client() as client:
        response = client.get('/login')
        assert response.status_code == 200
        assert b'RetailControl' in response.data


def test_admin_login_redirects_to_administracion():
    app = create_app({'TESTING': True, 'SQLALCHEMY_DATABASE_URI': 'sqlite:///:memory:'})
    with app.test_client() as client:
        response = client.post('/login', data={'username': 'admin', 'password': 'admin123'}, follow_redirects=True)
        assert response.status_code == 200
        assert b'Administraci' in response.data


def test_almacen_login_redirects_to_almacen():
    app = create_app({'TESTING': True, 'SQLALCHEMY_DATABASE_URI': 'sqlite:///:memory:'})
    with app.test_client() as client:
        response = client.post('/login', data={'username': 'almacen', 'password': 'almacen123'}, follow_redirects=True)
        assert response.status_code == 200
        assert b'Almac' in response.data


def test_almacen_products_table_has_no_edit_or_delete_actions():
    app = create_app({'TESTING': True, 'SQLALCHEMY_DATABASE_URI': 'sqlite:///:memory:'})
    with app.test_client() as client:
        client.post('/login', data={'username': 'almacen', 'password': 'almacen123'})
        inventory = client.get('/almacen')
        assert inventory.status_code == 200
        assert b'Acciones' not in inventory.data
        assert b'Editar producto' not in inventory.data
        assert b'confirmarEliminarProducto' not in inventory.data


def test_contabilidad_login_redirects_to_contabilidad():
    app = create_app({'TESTING': True, 'SQLALCHEMY_DATABASE_URI': 'sqlite:///:memory:'})
    with app.test_client() as client:
        response = client.post('/login', data={'username': 'conta', 'password': 'conta123'}, follow_redirects=True)
        assert response.status_code == 200
        assert b'Contabilidad' in response.data


def test_client_login_with_phone_name_dni():
    app = create_app({'TESTING': True, 'SQLALCHEMY_DATABASE_URI': 'sqlite:///:memory:'})
    with app.test_client() as client:
        response = client.post('/login', data={
            'login_type': 'client',
            'client_name': 'Pedro Castillo',
            'client_document': '77889900',
            'client_phone': '999111222'
        }, follow_redirects=True)
        assert response.status_code == 200
        assert b'Pedro Castillo' in response.data
        assert b'Tienda' in response.data
        assert b'id="carritoCompras"' in response.data
        assert b'Tu carrito est\xc3\xa1 vac\xc3\xado' in response.data
        old_orders_url = client.get('/tienda/mis-pedidos', follow_redirects=True)
        assert old_orders_url.status_code == 200
        assert b'historialCompras' in old_orders_url.data


def test_tienda_purchase_updates_stock_in_almacen_and_records_in_contabilidad():
    app = create_app({'TESTING': True, 'SQLALCHEMY_DATABASE_URI': 'sqlite:///:memory:'})
    with app.app_context():
        from app.models import Product, db
        products = {
            product.sku: product
            for product in Product.query.filter(Product.sku.in_(['PROD-001', 'PROD-002'])).all()
        }
        initial_stocks = {sku: product.stock for sku, product in products.items()}
        product_ids = {sku: product.id for sku, product in products.items()}
        unit_prices = {sku: product.price_sell for sku, product in products.items()}

    with app.test_client() as client:
        client.post('/tienda/login', data={
            'client_name': 'Cliente Tienda',
            'client_document': '88990011',
            'client_phone': '987654321'
        }, follow_redirects=True)
        for sku, quantity in [('PROD-001', 3), ('PROD-002', 2)]:
            response = client.post('/tienda/comprar', data={
                'product_id': str(product_ids[sku]),
                'quantity': str(quantity)
            }, follow_redirects=True)
            assert response.status_code == 200
            assert b'id="carritoCompras"' in response.data
            assert b'Confirmar compra' in response.data
            assert b'Martillo de Acero 16oz' in response.data

        # Agregar productos al carrito no registra la venta ni descuenta stock.
        with app.app_context():
            from app.models import Sale, db
            assert Sale.query.count() == 0
            for sku, product_id in product_ids.items():
                assert db.session.get(Product, product_id).stock == initial_stocks[sku]

        response = client.post('/tienda/finalizar-compra', follow_redirects=True)
        assert response.status_code == 200
        assert b'Mis compras' in response.data
        assert b'Martillo de Acero 16oz' in response.data
        assert b'Cinta M' in response.data
        assert b'Compra exitosa' not in response.data

    # 1. Verificar que el stock se descontó
    with app.app_context():
        from app.models import Product, Sale, db
        for sku, quantity in [('PROD-001', 3), ('PROD-002', 2)]:
            updated_prod = db.session.get(Product, product_ids[sku])
            assert updated_prod.stock == initial_stocks[sku] - quantity
        sale = Sale.query.one()
        assert sale.total == unit_prices['PROD-001'] * 3 + unit_prices['PROD-002'] * 2
        assert len(sale.items) == 2

    # 2. Verificar que Almacén ve el nuevo stock descontado
    with app.test_client() as client:
        client.post('/login', data={'username': 'almacen', 'password': 'almacen123'})
        resp_almacen = client.get('/almacen')
        assert resp_almacen.status_code == 200
        assert f"{initial_stocks['PROD-001'] - 3} un.".encode('utf-8') in resp_almacen.data

    # 3. Verificar que Contabilidad registra el ingreso por la venta
    with app.test_client() as client:
        client.post('/login', data={'username': 'conta', 'password': 'conta123'})
        resp_conta = client.get('/contabilidad')
        assert resp_conta.status_code == 200
        assert b'Cliente Tienda' in resp_conta.data
        assert b'Tienda Virtual' in resp_conta.data


def test_tienda_checkout_revalidates_stock_before_recording_sale():
    app = create_app({'TESTING': True, 'SQLALCHEMY_DATABASE_URI': 'sqlite:///:memory:'})
    with app.app_context():
        from app.models import Product, db
        product = Product.query.filter_by(sku='PROD-001').first()
        product_id = product.id

    with app.test_client() as client:
        client.post('/tienda/login', data={
            'client_name': 'Cliente Tienda',
            'client_document': '88990011',
            'client_phone': '987654321'
        })
        client.post('/tienda/comprar', data={
            'product_id': str(product_id),
            'quantity': '2'
        })

        with app.app_context():
            from app.models import Product, Sale, db
            product = db.session.get(Product, product_id)
            product.stock = 1
            db.session.commit()

        response = client.post('/tienda/finalizar-compra', follow_redirects=True)
        assert response.status_code == 200
        assert b'Stock insuficiente' in response.data

    with app.app_context():
        from app.models import Sale
        assert Sale.query.count() == 0


def test_administracion_purchase_increases_stock_connected_to_almacen():
    app = create_app({'TESTING': True, 'SQLALCHEMY_DATABASE_URI': 'sqlite:///:memory:'})
    with app.app_context():
        from app.models import Product, Supplier
        prod = Product.query.filter_by(sku='PROD-002').first()
        supp = Supplier.query.first()
        initial_stock = prod.stock
        prod_id = prod.id
        supp_id = supp.id

    with app.test_client() as client:
        client.post('/login', data={'username': 'admin', 'password': 'admin123'})
        response = client.post('/administracion', data={
            'action': 'compra',
            'supplier_id': str(supp_id),
            'product_id': str(prod_id),
            'quantity': '10',
            'unit_price': '9.00'
        }, follow_redirects=True)
        assert response.status_code == 200
        assert b'aument' not in response.data

    with app.app_context():
        from app.models import Product, db
        updated_prod = db.session.get(Product, prod_id)
        assert updated_prod.stock == initial_stock + 10


def test_administracion_payroll_recorded_and_visible_in_contabilidad():
    app = create_app({'TESTING': True, 'SQLALCHEMY_DATABASE_URI': 'sqlite:///:memory:'})
    with app.test_client() as client:
        client.post('/login', data={'username': 'admin', 'password': 'admin123'})
        response = client.post('/administracion', data={
            'action': 'pago_personal',
            'employee_name': 'Esteban Morales',
            'dni': '33445566',
            'position': 'Técnico de Mantenimiento',
            'amount': '950.00',
            'concept': 'Quincena Octubre'
        }, follow_redirects=True)
        assert response.status_code == 200
        assert b'Pago de personal registrado' not in response.data

    # Verificar que el pago aparece como Egreso en Contabilidad
    with app.test_client() as client:
        client.post('/login', data={'username': 'conta', 'password': 'conta123'})
        resp_conta = client.get('/contabilidad')
        assert resp_conta.status_code == 200
        assert b'Esteban Morales' in resp_conta.data
        assert b'950.00' in resp_conta.data


def test_role_restriction_blocks_unauthorized_module():
    app = create_app({'TESTING': True, 'SQLALCHEMY_DATABASE_URI': 'sqlite:///:memory:'})
    with app.test_client() as client:
        # Iniciar sesión como almacén
        client.post('/login', data={'username': 'almacen', 'password': 'almacen123'})
        # Intentar acceder a contabilidad (prohibido para almacén)
        response = client.get('/contabilidad', follow_redirects=True)
        assert response.status_code == 200
        assert b'Acceso no autorizado' in response.data
        # Es redirigido a su módulo correspondiente (Almacén)
        assert b'Almac' in response.data


def test_response_time_header_iso_25010():
    app = create_app({'TESTING': True, 'SQLALCHEMY_DATABASE_URI': 'sqlite:///:memory:'})
    with app.test_client() as client:
        response = client.get('/login')
        assert 'X-Response-Time-Ms' in response.headers
        duration = float(response.headers['X-Response-Time-Ms'])
        assert duration < 2000.0
