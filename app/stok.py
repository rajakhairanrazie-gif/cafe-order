from decimal import Decimal
from app import db
from app.models import Ingredient, Notification


def kurangi_stok(order):
    terpakai = {}
    for item in order.items:
        for resep in item.variant.ingredients:
            jumlah = resep.amount_used * item.quantity
            terpakai[resep.ingredient_id] = terpakai.get(resep.ingredient_id, Decimal('0')) + jumlah

    for ingredient_id, jumlah in terpakai.items():
        bahan = Ingredient.query.get(ingredient_id)
        sebelum = bahan.quantity
        bahan.quantity = max(Decimal('0'), sebelum - jumlah)

        if sebelum > bahan.threshold and bahan.quantity <= bahan.threshold:
            db.session.add(Notification(
                ingredient_id=bahan.id,
                message=f'Stok {bahan.name} tinggal {bahan.quantity:g} {bahan.unit}, batas {bahan.threshold:g}'
            ))