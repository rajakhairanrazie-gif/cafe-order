from app import db
from app.models import Setting

DEFAULT_NOTA = {
    'cafe_name': 'To Where Coffee',
    'cafe_address': '',
    'cafe_phone': '',
    'footer_text': 'Terima kasih sudah berkunjung!',
}


def get_settings():
    data = dict(DEFAULT_NOTA)
    for s in Setting.query.all():
        if s.key in data and s.value is not None:
            data[s.key] = s.value
    return data


def set_setting(key, value):
    s = Setting.query.filter_by(key=key).first()
    if s:
        s.value = value
    else:
        db.session.add(Setting(key=key, value=value))