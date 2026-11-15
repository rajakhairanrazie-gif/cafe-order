from flask import Blueprint, render_template, redirect, url_for, request, flash
from flask_login import login_required, current_user
from app.models import Order, OrderItem, Payment, PaymentOrder, Product
from app import db
from datetime import datetime

kasir = Blueprint('kasir', __name__, url_prefix='/kasir')


@kasir.route('/dashboard')
@login_required
def dashboard():
    orders = Order.query.filter_by(status='open').order_by(Order.id.desc()).all()
    return render_template('kasir/dashboard.html', orders=orders)


@kasir.route('/order/<int:order_id>')
@login_required
def detail_order(order_id):
    order = Order.query.get_or_404(order_id)
    total = sum(float(item.price_at_order) * item.quantity for item in order.items)
    return render_template('kasir/detail_order.html', order=order, total=total)


@kasir.route('/order/<int:order_id>/bayar', methods=['GET', 'POST'])
@login_required
def bayar_order(order_id):
    order = Order.query.get_or_404(order_id)
    total = sum(float(item.price_at_order) * item.quantity for item in order.items)

    if request.method == 'POST':
        method = request.form['method']

        payment = Payment(cashier_id=current_user.id, method=method, total_amount=total, paid_at=datetime.now())
        db.session.add(payment)
        db.session.flush()

        payment_order = PaymentOrder(payment_id=payment.id, order_id=order.id)
        db.session.add(payment_order)

        order.status = 'paid'
        db.session.commit()

        return redirect(url_for('kasir.pembayaran_selesai', payment_id=payment.id))

    return render_template('kasir/bayar.html', order=order, total=total)


@kasir.route('/pembayaran/<int:payment_id>/selesai')
@login_required
def pembayaran_selesai(payment_id):
    payment = Payment.query.get_or_404(payment_id)
    return render_template('kasir/selesai.html', payment=payment)


from flask import session


@kasir.route('/offline/baru')
@login_required
def offline_baru():
    products = Product.query.filter_by(is_active=True).all()
    cart = session.get('kasir_cart', [])
    return render_template('kasir/offline_baru.html', products=products, cart_count=len(cart))


@kasir.route('/offline/tambah', methods=['POST'])
@login_required
def offline_tambah():
    variant_id = int(request.form['variant_id'])

    cart = session.get('kasir_cart', [])
    cart.append({'variant_id': variant_id, 'quantity': 1})
    session['kasir_cart'] = cart

    return redirect(url_for('kasir.offline_baru'))


@kasir.route('/offline/keranjang')
@login_required
def offline_keranjang():
    from app.models import ProductVariant
    cart = session.get('kasir_cart', [])
    items = []
    total = 0

    for index, entry in enumerate(cart):
        variant = ProductVariant.query.get(entry['variant_id'])
        if variant:
            subtotal = float(variant.price) * entry['quantity']
            total += subtotal
            items.append({'index': index, 'variant': variant, 'quantity': entry['quantity'], 'subtotal': subtotal})

    return render_template('kasir/offline_keranjang.html', items=items, total=total)


@kasir.route('/offline/keranjang/ubah/<int:index>/<aksi>')
@login_required
def offline_ubah(index, aksi):
    cart = session.get('kasir_cart', [])

    if 0 <= index < len(cart):
        if aksi == 'tambah':
            cart[index]['quantity'] += 1
        elif aksi == 'kurang':
            cart[index]['quantity'] -= 1
            if cart[index]['quantity'] <= 0:
                cart.pop(index)
        elif aksi == 'hapus':
            cart.pop(index)

    session['kasir_cart'] = cart
    return redirect(url_for('kasir.offline_keranjang'))


@kasir.route('/offline/simpan/<aksi>', methods=['POST'])
@login_required
def offline_simpan(aksi):
    from app.models import ProductVariant
    cart = session.get('kasir_cart', [])
    if not cart:
        return redirect(url_for('kasir.offline_baru'))

    today = datetime.now().date()
    last_order = Order.query.filter_by(order_date=today).order_by(Order.daily_number.desc()).first()
    next_number = (last_order.daily_number + 1) if last_order else 1

    status = 'open' if aksi == 'openbill' else 'open'
    order = Order(daily_number=next_number, order_date=today, type='offline', status='open', created_by=current_user.id)
    db.session.add(order)
    db.session.flush()

    for entry in cart:
        variant = ProductVariant.query.get(entry['variant_id'])
        item = OrderItem(order_id=order.id, variant_id=variant.id, quantity=entry['quantity'], price_at_order=variant.price)
        db.session.add(item)

    db.session.commit()
    session.pop('kasir_cart', None)

    if aksi == 'bayar':
        return redirect(url_for('kasir.bayar_order', order_id=order.id))
    else:
        return redirect(url_for('kasir.dashboard'))