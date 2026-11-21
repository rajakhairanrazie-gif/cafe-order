from functools import wraps
from datetime import datetime
from flask import Blueprint, render_template, redirect, url_for, request, flash, abort
from flask_login import login_required, current_user
from werkzeug.security import generate_password_hash
from app.models import Category, Product, ProductVariant, OrderItem, VariantIngredient, Payment, Order, Ingredient, Notification, User
from app import db
from app.pengaturan import DEFAULT_NOTA, get_settings, set_setting

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
        stok_kritis=Ingredient.query.filter(Ingredient.quantity <= Ingredient.threshold).all(),
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

# ---------- Bahan baku ----------

@admin.route('/bahan', methods=['GET', 'POST'])
@login_required
@admin_only
def bahan():
    if request.method == 'POST':
        name = request.form['name'].strip()
        if name:
            db.session.add(Ingredient(
                name=name,
                unit=request.form['unit'],
                quantity=request.form['quantity'] or 0,
                threshold=request.form['threshold'] or 0,
            ))
            db.session.commit()
            flash('Bahan baku ditambahkan')
        return redirect(url_for('admin.bahan'))

    ingredients = Ingredient.query.order_by(Ingredient.name).all()
    return render_template('admin/bahan.html', ingredients=ingredients)


@admin.route('/bahan/<int:ingredient_id>/ubah', methods=['POST'])
@login_required
@admin_only
def bahan_ubah(ingredient_id):
    bahan = Ingredient.query.get_or_404(ingredient_id)
    bahan.name = request.form['name'].strip()
    bahan.quantity = request.form['quantity'] or 0
    bahan.threshold = request.form['threshold'] or 0
    db.session.commit()
    flash('Bahan disimpan')
    return redirect(url_for('admin.bahan'))


@admin.route('/bahan/<int:ingredient_id>/isi', methods=['POST'])
@login_required
@admin_only
def bahan_isi(ingredient_id):
    bahan = Ingredient.query.get_or_404(ingredient_id)
    try:
        tambahan = float(request.form['jumlah'])
    except ValueError:
        tambahan = 0
    if tambahan > 0:
        bahan.quantity = float(bahan.quantity) + tambahan
        db.session.commit()
        flash(f'Stok {bahan.name} ditambah {tambahan:g} {bahan.unit}')
    return redirect(url_for('admin.bahan'))


@admin.route('/bahan/<int:ingredient_id>/hapus', methods=['POST'])
@login_required
@admin_only
def bahan_hapus(ingredient_id):
    bahan = Ingredient.query.get_or_404(ingredient_id)
    if VariantIngredient.query.filter_by(ingredient_id=bahan.id).first():
        flash('Bahan masih dipakai di resep, hapus dari resep dulu')
    else:
        Notification.query.filter_by(ingredient_id=bahan.id).delete()
        db.session.delete(bahan)
        db.session.commit()
        flash('Bahan dihapus')
    return redirect(url_for('admin.bahan'))


# ---------- Resep ----------

@admin.route('/varian/<int:variant_id>/resep', methods=['GET', 'POST'])
@login_required
@admin_only
def resep(variant_id):
    variant = ProductVariant.query.get_or_404(variant_id)

    if request.method == 'POST':
        ingredient_id = int(request.form['ingredient_id'])
        amount = request.form['amount_used']
        if amount and float(amount) > 0:
            ada = VariantIngredient.query.filter_by(variant_id=variant.id, ingredient_id=ingredient_id).first()
            if ada:
                ada.amount_used = amount
            else:
                db.session.add(VariantIngredient(variant_id=variant.id, ingredient_id=ingredient_id, amount_used=amount))
            db.session.commit()
            flash('Resep disimpan')
        return redirect(url_for('admin.resep', variant_id=variant.id))

    ingredients = Ingredient.query.order_by(Ingredient.name).all()
    return render_template('admin/resep.html', variant=variant, ingredients=ingredients)


@admin.route('/resep/<int:resep_id>/hapus', methods=['POST'])
@login_required
@admin_only
def resep_hapus(resep_id):
    item = VariantIngredient.query.get_or_404(resep_id)
    variant_id = item.variant_id
    db.session.delete(item)
    db.session.commit()
    return redirect(url_for('admin.resep', variant_id=variant_id))

# ---------- Akun ----------

@admin.route('/akun', methods=['GET', 'POST'])
@login_required
@admin_only
def akun():
    if request.method == 'POST':
        name = request.form['name'].strip()
        email = request.form['email'].strip().lower()
        password = request.form['password']
        role = request.form['role']

        if not name or not email or len(password) < 6:
            flash('Nama, email wajib diisi dan password minimal 6 karakter')
        elif role not in ('admin', 'kasir', 'pajak'):
            flash('Role tidak valid')
        elif User.query.filter_by(email=email).first():
            flash('Email sudah dipakai')
        else:
            db.session.add(User(name=name, email=email, role=role,
                                password=generate_password_hash(password), is_active_account=True))
            db.session.commit()
            flash('Akun ditambahkan')
        return redirect(url_for('admin.akun'))

    users = User.query.order_by(User.id).all()
    return render_template('admin/akun.html', users=users)


@admin.route('/akun/<int:user_id>/status', methods=['POST'])
@login_required
@admin_only
def akun_status(user_id):
    user = User.query.get_or_404(user_id)
    if user.id == current_user.id:
        flash('Akun yang sedang dipakai tidak bisa dinonaktifkan')
    else:
        user.is_active_account = not user.is_active_account
        db.session.commit()
        flash('Status akun diubah')
    return redirect(url_for('admin.akun'))


@admin.route('/akun/<int:user_id>/password', methods=['POST'])
@login_required
@admin_only
def akun_password(user_id):
    user = User.query.get_or_404(user_id)
    password = request.form['password']
    if len(password) < 6:
        flash('Password minimal 6 karakter')
    else:
        user.password = generate_password_hash(password)
        db.session.commit()
        flash('Password diubah')
    return redirect(url_for('admin.akun'))

# ---------- Pengaturan nota ----------

@admin.route('/pengaturan', methods=['GET', 'POST'])
@login_required
@admin_only
def pengaturan():
    if request.method == 'POST':
        for key in DEFAULT_NOTA:
            set_setting(key, request.form.get(key, '').strip())
        db.session.commit()
        flash('Pengaturan nota disimpan')
        return redirect(url_for('admin.pengaturan'))

    return render_template('admin/pengaturan.html', s=get_settings())