from functools import wraps
from datetime import datetime
from flask import Blueprint, render_template, request, abort
from flask_login import login_required, current_user
from app import db
from app.models import Payment, PaymentOrder, Order, OrderItem, ProductVariant, Product

pajak = Blueprint('pajak', __name__, url_prefix='/pajak')


def pajak_only(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if current_user.role != 'pajak':
            abort(403)
        return f(*args, **kwargs)
    return wrapper


def _periode():
    bulan = request.args.get('bulan') or datetime.now().strftime('%Y-%m')
    try:
        awal = datetime.strptime(bulan, '%Y-%m')
    except ValueError:
        awal = datetime.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        bulan = awal.strftime('%Y-%m')

    if awal.month == 12:
        akhir = awal.replace(year=awal.year + 1, month=1)
    else:
        akhir = awal.replace(month=awal.month + 1)
    return bulan, awal, akhir


def _data_pajak(awal, akhir):
    rows = (
        db.session.query(Payment, Order, OrderItem, Product)
        .join(PaymentOrder, PaymentOrder.payment_id == Payment.id)
        .join(Order, Order.id == PaymentOrder.order_id)
        .join(OrderItem, OrderItem.order_id == Order.id)
        .join(ProductVariant, ProductVariant.id == OrderItem.variant_id)
        .join(Product, Product.id == ProductVariant.product_id)
        .filter(Product.is_taxable == True, Payment.paid_at >= awal, Payment.paid_at < akhir)
        .all()
    )

    per_order = {}
    per_produk = {}
    for payment, order, item, product in rows:
        subtotal = float(item.price_at_order) * item.quantity

        o = per_order.setdefault(order.id, {'order': order, 'payment': payment, 'total': 0, 'items': []})
        o['total'] += subtotal
        o['items'].append(f'{product.name} x{item.quantity}')

        p = per_produk.setdefault(product.id, {'nama': product.name, 'qty': 0, 'total': 0})
        p['qty'] += item.quantity
        p['total'] += subtotal

    daftar_order = sorted(per_order.values(), key=lambda x: x['payment'].paid_at, reverse=True)
    daftar_produk = sorted(per_produk.values(), key=lambda x: x['total'], reverse=True)
    omset = sum(o['total'] for o in daftar_order)
    return daftar_order, daftar_produk, omset


@pajak.route('/dashboard')
@login_required
@pajak_only
def dashboard():
    bulan, awal, akhir = _periode()
    daftar_order, daftar_produk, omset = _data_pajak(awal, akhir)
    return render_template('pajak/dashboard.html', bulan=bulan, omset=omset,
                           jumlah=len(daftar_order), produk=daftar_produk)


@pajak.route('/riwayat')
@login_required
@pajak_only
def riwayat():
    bulan, awal, akhir = _periode()
    daftar_order, daftar_produk, omset = _data_pajak(awal, akhir)
    return render_template('pajak/riwayat.html', bulan=bulan, omset=omset, daftar=daftar_order)