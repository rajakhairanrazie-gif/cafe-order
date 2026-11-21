from functools import wraps
from datetime import datetime
from flask import Blueprint, render_template, redirect, url_for, request, flash, abort
from flask_login import login_required, current_user
from app.models import Category, Product, ProductVariant, OrderItem, VariantIngredient, Payment, Order
from app import db

admin = Blueprint('admin', __name__, url_prefix='/admin')


def admin_only(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if current_user.role != 'admin':
            abort(403)
        return f(*args, **kwargs)
    return wrapper


@admin.route('/dashboard')
@login_required
@admin_only
def dashboard():
    today = datetime.now().date()
    start = datetime.combine(today, datetime.min.time())
    end = datetime.combine(today, datetime.max.time())

    payments = Payment.query.filter(Payment.paid_at >= start, Payment.paid_at <= end).all()
    omset = sum(float(p.total_amount) for p in payments)

    return render_template(
        'admin/dashboard.html',
        today=today,
        omset=omset,
        jumlah_transaksi=len(payments),
        open_bill=Order.query.filter_by(status='open').count(),
        produk_aktif=Product.query.filter_by(is_active=True).count(),
    )


# ---------- Kategori ----------

@admin.route('/kategori', methods=['GET', 'POST'])
@login_required
@admin_only
def kategori():
    if request.method == 'POST':
        name = request.form['name'].strip()
        if name:
            db.session.add(Category(name=name))
            db.session.commit()
            flash('Kategori ditambahkan')
        return redirect(url_for('admin.kategori'))

    categories = Category.query.order_by(Category.id).all()
    return render_template('admin/kategori.html', categories=categories)


@admin.route('/kategori/<int:category_id>/hapus', methods=['POST'])
@login_required
@admin_only
def kategori_hapus(category_id):
    category = Category.query.get_or_404(category_id)
    if category.products:
        flash('Kategori masih dipakai produk, tidak bisa dihapus')
    else:
        db.session.delete(category)
        db.session.commit()
        flash('Kategori dihapus')
    return redirect(url_for('admin.kategori'))


# ---------- Produk ----------

@admin.route('/produk')
@login_required
@admin_only
def produk():
    products = Product.query.order_by(Product.id.desc()).all()
    return render_template('admin/produk.html', products=products)


@admin.route('/produk/tambah', methods=['GET', 'POST'])
@login_required
@admin_only
def produk_tambah():
    categories = Category.query.order_by(Category.id).all()
    if not categories:
        flash('Buat kategori dulu sebelum menambah produk')
        return redirect(url_for('admin.kategori'))

    if request.method == 'POST':
        name = request.form['name'].strip()
        variant_name = request.form['variant_name'].strip() or 'Regular'
        price = request.form['price']

        if not name or not price:
            flash('Nama produk dan harga wajib diisi')
            return redirect(url_for('admin.produk_tambah'))

        product = Product(
            name=name,
            category_id=int(request.form['category_id']),
            is_taxable='is_taxable' in request.form,
            is_active='is_active' in request.form,
        )
        db.session.add(product)
        db.session.flush()
        db.session.add(ProductVariant(product_id=product.id, variant_name=variant_name, price=price))
        db.session.commit()

        flash('Produk ditambahkan, varian lain bisa ditambah di bawah')
        return redirect(url_for('admin.produk_edit', product_id=product.id))

    return render_template('admin/produk_form.html', categories=categories, product=None)


@admin.route('/produk/<int:product_id>/edit', methods=['GET', 'POST'])
@login_required
@admin_only
def produk_edit(product_id):
    product = Product.query.get_or_404(product_id)
    categories = Category.query.order_by(Category.id).all()

    if request.method == 'POST':
        product.name = request.form['name'].strip()
        product.category_id = int(request.form['category_id'])
        product.is_taxable = 'is_taxable' in request.form
        product.is_active = 'is_active' in request.form
        db.session.commit()
        flash('Produk disimpan')
        return redirect(url_for('admin.produk_edit', product_id=product.id))

    return render_template('admin/produk_form.html', categories=categories, product=product)


# ---------- Varian ----------

@admin.route('/produk/<int:product_id>/varian/tambah', methods=['POST'])
@login_required
@admin_only
def varian_tambah(product_id):
    product = Product.query.get_or_404(product_id)
    name = request.form['variant_name'].strip()
    price = request.form['price']

    if name and price:
        db.session.add(ProductVariant(product_id=product.id, variant_name=name, price=price))
        db.session.commit()
        flash('Varian ditambahkan')
    else:
        flash('Nama varian dan harga wajib diisi')
    return redirect(url_for('admin.produk_edit', product_id=product.id))


@admin.route('/varian/<int:variant_id>/ubah', methods=['POST'])
@login_required
@admin_only
def varian_ubah(variant_id):
    variant = ProductVariant.query.get_or_404(variant_id)
    name = request.form['variant_name'].strip()
    price = request.form['price']

    if name and price:
        variant.variant_name = name
        variant.price = price
        db.session.commit()
        flash('Varian disimpan')
    return redirect(url_for('admin.produk_edit', product_id=variant.product_id))


@admin.route('/varian/<int:variant_id>/hapus', methods=['POST'])
@login_required
@admin_only
def varian_hapus(variant_id):
    variant = ProductVariant.query.get_or_404(variant_id)
    product_id = variant.product_id

    if OrderItem.query.filter_by(variant_id=variant.id).first():
        flash('Varian ini sudah pernah dipesan, tidak bisa dihapus. Nonaktifkan produknya kalau tidak dijual lagi')
    elif len(variant.product.variants) <= 1:
        flash('Produk minimal punya 1 varian')
    else:
        VariantIngredient.query.filter_by(variant_id=variant.id).delete()
        db.session.delete(variant)
        db.session.commit()
        flash('Varian dihapus')

    return redirect(url_for('admin.produk_edit', product_id=product_id))