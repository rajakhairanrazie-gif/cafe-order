from flask import Blueprint, render_template, redirect, url_for, request, session
from app.models import Product, Category, ProductVariant, Order, OrderItem
from app import db
from datetime import date
from app.stok import kurangi_stok

main = Blueprint('main', __name__)


@main.route('/menu')
def menu():
    products = Product.query.filter_by(is_active=True, is_taxable=True).all()
    categories = Category.query.all()
    cart_count = len(session.get('cart', []))
    return render_template('menu.html', products=products, categories=categories, cart_count=cart_count)


@main.route('/produk/<int:product_id>')
def detail_produk(product_id):
    product = Product.query.get_or_404(product_id)
    return render_template('detail_produk.html', product=product)


@main.route('/keranjang/tambah', methods=['POST'])
def tambah_keranjang():
    variant_id = int(request.form['variant_id'])
    quantity = int(request.form['quantity'])

    cart = session.get('cart', [])
    cart.append({'variant_id': variant_id, 'quantity': quantity})
    session['cart'] = cart

    return redirect(url_for('main.menu'))


@main.route('/keranjang')
def keranjang():
    cart = session.get('cart', [])
    items = []
    total = 0

    for index, entry in enumerate(cart):
        variant = ProductVariant.query.get(entry['variant_id'])
        if variant:
            subtotal = float(variant.price) * entry['quantity']
            total += subtotal
            items.append({
                'index': index,
                'variant': variant,
                'quantity': entry['quantity'],
                'subtotal': subtotal
            })

    return render_template('keranjang.html', items=items, total=total)


@main.route('/keranjang/checkout', methods=['POST'])
def checkout():
    cart = session.get('cart', [])
    if not cart:
        return redirect(url_for('main.menu'))

    today = date.today()
    last_order = Order.query.filter_by(order_date=today).order_by(Order.daily_number.desc()).first()
    next_number = (last_order.daily_number + 1) if last_order else 1

    order = Order(daily_number=next_number, order_date=today, type='online', status='open')
    db.session.add(order)
    db.session.flush()

    for entry in cart:
        variant = ProductVariant.query.get(entry['variant_id'])
        item = OrderItem(
            order_id=order.id,
            variant_id=variant.id,
            quantity=entry['quantity'],
            price_at_order=variant.price
        )
        db.session.add(item)
    
    kurangi_stok(order)
    db.session.commit()
    session.pop('cart', None)

    return redirect(url_for('main.kode_pesanan', order_id=order.id))


@main.route('/pesanan/<int:order_id>')
def kode_pesanan(order_id):
    order = Order.query.get_or_404(order_id)
    return render_template('kode_pesanan.html', order=order)


@main.route('/keranjang/ubah/<int:index>/<aksi>')
def ubah_keranjang(index, aksi):
    cart = session.get('cart', [])

    if 0 <= index < len(cart):
        if aksi == 'tambah':
            cart[index]['quantity'] += 1
        elif aksi == 'kurang':
            cart[index]['quantity'] -= 1
            if cart[index]['quantity'] <= 0:
                cart.pop(index)
        elif aksi == 'hapus':
            cart.pop(index)

    session['cart'] = cart
    return redirect(url_for('main.keranjang'))