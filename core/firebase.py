"""
core/firebase.py — Firebase REST API istemcisi
Firestore + Öğrenci No Tabanlı Auth

Mimari:
- firebase_config.json repoda herkese açık şekilde bulunur
- Her öğrenci no → deterministik Firebase email/password hesabı
- Şifre kullanıcıya sorulmaz, uygulama otomatik türetir
- Admin işlemleri sadece Firebase Console üzerinden yapılır
- Web API key public'tir, güvenlik Firebase Security Rules ile sağlanır
"""
from __future__ import annotations

import hashlib
import hmac as _hmac
import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests

from utils.paths import CONFIG_DIR

log = logging.getLogger(__name__)

# Proje kökü
_ROOT = Path(__file__).parent.parent

# Dosya yolları
# 1. Repodaki public config (herkes alır, git ile gelir)
_REPO_CONFIG  = _ROOT / "firebase_config.json"
# 2. Kullanıcının local config (override için, genelde kullanılmaz)
_LOCAL_CONFIG = CONFIG_DIR / "firebase.json"
# 3. Auth token (cihaza özel, gitignore'da)
_TOKEN_FILE   = CONFIG_DIR / "firebase_token.json"

# Firebase REST uç noktaları (v1)
_AUTH_SIGNUP   = "https://identitytoolkit.googleapis.com/v1/accounts:signUp"
_AUTH_SIGNIN   = "https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword"
_AUTH_REFRESH  = "https://securetoken.googleapis.com/v1/token"
_FS_BASE       = "https://firestore.googleapis.com/v1/projects/{project}/databases/(default)/documents"
_FS_QUERY      = "https://firestore.googleapis.com/v1/projects/{project}/databases/(default)/documents:runQuery"

# Öğrenci no → deterministik Firebase hesabı için gömülü anahtar.
# Gerçek bir şifre değil; öğrenci no + bu sabit = hesap başına benzersiz kimlik.
# Kaynak kodda açık olsa da trol için her girişim gerçek bir öğrenci no gerektirir.
_APP_SECRET = b"alms-igumail-auth-v2-9f3k2m"

_http = requests.Session()
_http.headers.update({"Content-Type": "application/json"})


# ── Yapılandırma ──────────────────────────────────────────────

def load_config() -> dict | None:
    """
    Firebase config'i yükler.
    Öncelik: local override → repo config
    """
    # 1. Local override (manuel setup ile girilen)
    if _LOCAL_CONFIG.exists():
        try:
            data = json.loads(_LOCAL_CONFIG.read_text(encoding="utf-8"))
            if data.get("apiKey") and data.get("projectId"):
                return data
        except Exception:
            pass

    # 2. Repodaki public config (git ile gelir)
    if _REPO_CONFIG.exists():
        try:
            data = json.loads(_REPO_CONFIG.read_text(encoding="utf-8"))
            if data.get("apiKey") and data.get("projectId"):
                return data
        except Exception:
            pass

    return None


def is_configured() -> bool:
    return load_config() is not None


def save_local_config(api_key: str, project_id: str, **extra):
    """Admin tarafından yapılan local override config kaydı."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    data = {"apiKey": api_key, "projectId": project_id, **extra}
    _LOCAL_CONFIG.write_text(json.dumps(data, indent=2), encoding="utf-8")
    _LOCAL_CONFIG.chmod(0o600)


def save_repo_config(api_key: str, project_id: str, **extra):
    """
    Repo'ya eklenecek public config dosyasını yazar.
    Geliştirici bunu bir kez yapar, commit'ler.
    Bu dosya hassas değildir — Firebase Security Rules korur.
    """
    data = {
        "apiKey":    api_key,
        "projectId": project_id,
        "_note":     "Bu dosya herkese açıktır. Güvenlik Firebase Security Rules ile sağlanır.",
        **extra,
    }
    _REPO_CONFIG.write_text(json.dumps(data, indent=2), encoding="utf-8")
    log.info("Repo config kaydedildi: %s", _REPO_CONFIG)


def setup_firebase(as_admin: bool = False):
    """
    Firebase bağlantısını kur.
    as_admin=True: geliştirici modunda, repo config'i yazar.
    as_admin=False: sadece local override yazar.
    """
    print("\n── Firebase Kurulumu ─────────────────────────────────")

    if as_admin:
        print("GELİŞTİRİCİ MODU — Repo config dosyası oluşturulacak")
        print("Bu dosyayı git'e commit'leyin — diğer kullanıcılar otomatik alır")
    else:
        print("Adımlar:")
        print("  1. console.firebase.google.com → Projenizi seçin")
        print("  2. Build → Authentication → Anonymous → Enable")
        print("  3. Proje Ayarları → Genel → Web Uygulaması → Config")

    print()
    try:
        api_key    = input("  apiKey    : ").strip()
        project_id = input("  projectId : ").strip()
        auth_domain = input("  authDomain (boş OK): ").strip()
        app_id      = input("  appId      (boş OK): ").strip()
    except (KeyboardInterrupt, EOFError):
        print("\n❌ İptal edildi.")
        return False

    if not api_key or not project_id:
        print("❌ apiKey ve projectId zorunlu.")
        return False

    extras = {}
    if auth_domain: extras["authDomain"] = auth_domain
    if app_id:      extras["appId"]      = app_id

    # Test et
    print("\n  Bağlantı test ediliyor...")
    ok = _test_api_key(api_key)

    if ok:
        print("  ✅ Bağlantı başarılı!")
        if as_admin:
            save_repo_config(api_key, project_id, **extras)
            print(f"\n  📄 {_REPO_CONFIG} dosyası oluşturuldu.")
            print("  → git add firebase_config.json && git commit -m 'firebase config'")
            print("  → git push — diğer kullanıcılar güncelleyince otomatik alır")
        else:
            save_local_config(api_key, project_id, **extras)
        return True
    else:
        print("  ❌ Bağlantı başarısız!")
        print()
        print("  Kontrol edin:")
        print("  • Firebase Console → Authentication → Anonymous → Enabled mi?")
        print("  • API Key doğru mu?")
        print("  • İnternet bağlantısı var mı?")
        return False


# ── Kimlik doğrulama ──────────────────────────────────────────

def _load_token() -> dict | None:
    if not _TOKEN_FILE.exists():
        return None
    try:
        return json.loads(_TOKEN_FILE.read_text(encoding="utf-8"))
    except Exception:
        return None


def _save_token(data: dict):
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    _TOKEN_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")
    _TOKEN_FILE.chmod(0o600)


def _test_api_key(api_key: str) -> bool:
    """
    API key geçerli mi test et — hesap oluşturmadan.
    accounts:lookup endpoint'ine sahte token gönder:
    - "API key not valid" içeren mesaj → key yanlış
    - INVALID_ID_TOKEN vb. → key doğru (beklenen Firebase hatası)
    """
    try:
        r = _http.post(
            f"https://identitytoolkit.googleapis.com/v1/accounts:lookup?key={api_key}",
            json={"idToken": "test"},
            timeout=10,
        )
        msg = r.json().get("error", {}).get("message", "")
        # Geçersiz key → "API key not valid..." veya "API_KEY_INVALID"
        invalid = "API key not valid" in msg or "API_KEY_INVALID" in msg
        return not invalid
    except Exception:
        return False


def _student_email(student_no: str) -> str:
    """Öğrenci no → deterministik Firebase email (student_no görünmez)."""
    h = hashlib.sha256(b"alms-email-v2:" + student_no.encode()).hexdigest()[:24]
    return f"s{h}@alms.igumail.app"


def _student_password(student_no: str) -> str:
    """Öğrenci no → HMAC türetilmiş Firebase şifresi (kullanıcıya sorulmaz)."""
    return _hmac.new(_APP_SECRET, student_no.encode(), hashlib.sha256).hexdigest()


def _parse_token(d: dict) -> dict:
    return {
        "idToken":      d["idToken"],
        "refreshToken": d["refreshToken"],
        "localId":      d["localId"],
        "expiresAt":    time.time() + int(d.get("expiresIn", 3600)),
    }


def _do_student_signin(student_no: str, api_key: str) -> dict | None:
    """Mevcut öğrenci Firebase hesabına giriş yap."""
    try:
        r = _http.post(
            f"{_AUTH_SIGNIN}?key={api_key}",
            json={
                "email":             _student_email(student_no),
                "password":          _student_password(student_no),
                "returnSecureToken": True,
            },
            timeout=10,
        )
        if r.status_code == 200:
            return _parse_token(r.json())
        log.debug("Student signin (%s): %s", r.status_code, r.text[:200])
        return None
    except Exception as e:
        log.debug("Student signin exception: %s", e)
        return None


def _do_student_signup(student_no: str, api_key: str) -> dict | None:
    """Yeni öğrenci Firebase hesabı oluştur."""
    try:
        r = _http.post(
            f"{_AUTH_SIGNUP}?key={api_key}",
            json={
                "email":             _student_email(student_no),
                "password":          _student_password(student_no),
                "returnSecureToken": True,
            },
            timeout=10,
        )
        if r.status_code == 200:
            return _parse_token(r.json())
        log.debug("Student signup (%s): %s", r.status_code, r.text[:200])
        return None
    except Exception as e:
        log.debug("Student signup exception: %s", e)
        return None


def firebase_login(student_no: str) -> bool:
    """
    Öğrenci no ile Firebase'e giriş / kayıt.
    - Hesap varsa → signin
    - Yoksa → signup (ilk kullanım)
    - Token locale kaydedilir; sonraki çağrılar refresh ile devam eder.
    """
    if not student_no or not is_configured():
        return False
    cfg = load_config()
    if not cfg:
        return False

    # Token geçerliyse tekrar auth etme
    tok = _load_token()
    if tok and time.time() < tok.get("expiresAt", 0) - 60:
        return True

    api_key = cfg["apiKey"]

    # Önce signin, yoksa signup
    new_tok = _do_student_signin(student_no, api_key) or _do_student_signup(student_no, api_key)
    if new_tok:
        new_tok["_auth_method"] = "email"   # migration ayırt edici işaret
        _save_token(new_tok)
        # Öğrenci kaydını oluştur/güncelle (UID artık geçerli)
        try:
            import platform as _plat
            from core.config import get as _cfg
            version = str(_cfg("version") or "")
            register_student(student_no, version=version, platform=_plat.system())
        except Exception as e:
            log.debug("register_student: %s", e)
        return True
    return False


def _refresh_token(refresh_token: str, api_key: str) -> dict | None:
    """
    Token yenile.
    Endpoint: POST securetoken.googleapis.com/v1/token
    Content-Type: application/x-www-form-urlencoded  ← önemli, JSON değil
    """
    try:
        r = requests.post(  # _http değil — Content-Type farklı
            f"{_AUTH_REFRESH}?key={api_key}",
            data=f"grant_type=refresh_token&refresh_token={refresh_token}",
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=10,
        )
        if r.status_code == 200:
            d = r.json()
            return {
                "idToken":      d["id_token"],
                "refreshToken": d["refresh_token"],
                "localId":      d["user_id"],
                "expiresAt":    time.time() + int(d.get("expires_in", 3600)),
            }
        log.debug("Token refresh hatası (%s): %s", r.status_code, r.text[:200])
        return None
    except Exception as e:
        log.debug("Token refresh exception: %s", e)
        return None


def _get_or_refresh_token() -> str | None:
    """
    Geçerli ID token döner.
    1. Cache'de geçerliyse → direkt döner
    2. Süresi dolduysa → refresh eder
    3. Hiç yoksa → None (firebase_login(student_no) ile giriş gerekli)
    """
    cfg = load_config()
    if not cfg:
        return None
    api_key = cfg["apiKey"]

    tok = _load_token()
    if tok:
        if time.time() < tok.get("expiresAt", 0) - 60:
            return tok["idToken"]
        if tok.get("refreshToken"):
            new_tok = _refresh_token(tok["refreshToken"], api_key)
            if new_tok:
                _save_token(new_tok)
                return new_tok["idToken"]

    return None


def get_uid() -> str | None:
    tok = _load_token()
    return tok.get("localId") if tok else None


# ── Veri tipi dönüştürücüler ──────────────────────────────────

def _to_fs(value: Any) -> dict:
    if isinstance(value, bool):
        return {"booleanValue": value}
    if isinstance(value, int):
        return {"integerValue": str(value)}
    if isinstance(value, float):
        return {"doubleValue": value}
    if isinstance(value, datetime):
        return {"timestampValue": value.strftime("%Y-%m-%dT%H:%M:%SZ")}
    if isinstance(value, str):
        return {"stringValue": value}
    if isinstance(value, list):
        return {"arrayValue": {"values": [_to_fs(v) for v in value]}}
    if isinstance(value, dict):
        return {"mapValue": {"fields": {k: _to_fs(v) for k, v in value.items()}}}
    if value is None:
        return {"nullValue": None}
    return {"stringValue": str(value)}


def _from_fs(field: dict) -> Any:
    if "stringValue"    in field: return field["stringValue"]
    if "integerValue"   in field: return int(field["integerValue"])
    if "doubleValue"    in field: return field["doubleValue"]
    if "booleanValue"   in field: return field["booleanValue"]
    if "nullValue"      in field: return None
    if "timestampValue" in field: return field["timestampValue"]
    if "arrayValue"     in field:
        return [_from_fs(v) for v in field["arrayValue"].get("values", [])]
    if "mapValue"       in field:
        return {k: _from_fs(v) for k, v in field["mapValue"]["fields"].items()}
    return None


def _doc_to_dict(doc: dict) -> dict:
    fields = doc.get("fields", {})
    result = {k: _from_fs(v) for k, v in fields.items()}
    name = doc.get("name", "")
    if "/" in name:
        result["_id"] = name.split("/")[-1]
    return result


def _dict_to_fields(data: dict) -> dict:
    return {k: _to_fs(v) for k, v in data.items() if not k.startswith("_")}


# ── Firestore CRUD ────────────────────────────────────────────

def _fs_url(project_id: str, *parts: str) -> str:
    base = _FS_BASE.format(project=project_id)
    return (base + "/" + "/".join(str(p) for p in parts)) if parts else base


def _auth_hdr(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def get_document(collection: str, doc_id: str) -> dict | None:
    cfg = load_config(); token = _get_or_refresh_token()
    if not cfg or not token: return None
    try:
        r = _http.get(_fs_url(cfg["projectId"], collection, doc_id),
                      headers=_auth_hdr(token), timeout=10)
        return _doc_to_dict(r.json()) if r.status_code == 200 else None
    except Exception as e:
        log.debug("get_document: %s", e); return None


def set_document(collection: str, doc_id: str, data: dict) -> bool:
    cfg = load_config(); token = _get_or_refresh_token()
    if not cfg or not token: return False
    try:
        r = _http.patch(_fs_url(cfg["projectId"], collection, doc_id),
                        headers=_auth_hdr(token),
                        json={"fields": _dict_to_fields(data)}, timeout=10)
        return r.status_code in (200, 201)
    except Exception as e:
        log.debug("set_document: %s", e); return False


def add_document(collection: str, data: dict) -> str | None:
    cfg = load_config(); token = _get_or_refresh_token()
    if not cfg or not token: return None
    try:
        r = _http.post(_fs_url(cfg["projectId"], collection),
                       headers=_auth_hdr(token),
                       json={"fields": _dict_to_fields(data)}, timeout=10)
        if r.status_code in (200, 201):
            name = r.json().get("name", "")
            return name.split("/")[-1] if "/" in name else None
        return None
    except Exception as e:
        log.debug("add_document: %s", e); return None


def update_document(collection: str, doc_id: str, data: dict) -> bool:
    cfg = load_config(); token = _get_or_refresh_token()
    if not cfg or not token: return False
    try:
        fields = _dict_to_fields(data)
        mask   = "&".join(f"updateMask.fieldPaths={k}" for k in fields)
        r = _http.patch(f"{_fs_url(cfg['projectId'], collection, doc_id)}?{mask}",
                        headers=_auth_hdr(token),
                        json={"fields": fields}, timeout=10)
        return r.status_code in (200, 201)
    except Exception as e:
        log.debug("update_document: %s", e); return False


def list_collection(collection: str, limit: int = 100) -> list[dict]:
    """
    Koleksiyondaki tüm belgeleri döner.
    Firestore REST API list documents endpoint kullanır.
    Filtre yok — index gerektirmez — client-side filtrele.
    """
    cfg = load_config(); token = _get_or_refresh_token()
    if not cfg or not token: return []

    url = f"{_fs_url(cfg['projectId'], collection)}?pageSize={limit}"
    results = []
    try:
        while url:
            r = _http.get(url, headers=_auth_hdr(token), timeout=15)
            if r.status_code != 200:
                log.debug("list_collection (%s): %s", r.status_code, r.text[:200])
                break
            data = r.json()
            for doc in data.get("documents", []):
                results.append(_doc_to_dict(doc))
            # Sayfalama
            next_token = data.get("nextPageToken")
            if next_token:
                base = f"{_fs_url(cfg['projectId'], collection)}?pageSize={limit}"
                url  = f"{base}&pageToken={next_token}"
            else:
                break
    except Exception as e:
        log.debug("list_collection exception: %s", e)
    return results


def query_collection(
    collection: str,
    filters: list[tuple] | None = None,
    order_by: str | None = None,
    limit: int = 100,
    descending: bool = True,
) -> list[dict]:
    """
    Koleksiyonu sorgular.
    filters=None → list_collection kullanır (index gerektirmez).
    filters varsa → runQuery kullanır (tek filtre, index gerektirmez).
    """
    # Filtre yoksa doğrudan list API
    if not filters and not order_by:
        return list_collection(collection, limit)

    cfg = load_config(); token = _get_or_refresh_token()
    if not cfg or not token: return []

    query: dict = {
        "structuredQuery": {
            "from": [{"collectionId": collection}],
            "limit": limit,
        }
    }

    if filters and len(filters) == 1:
        f, op, val = filters[0]
        query["structuredQuery"]["where"] = {
            "fieldFilter": {"field": {"fieldPath": f}, "op": op, "value": _to_fs(val)}
        }
    elif filters and len(filters) > 1:
        query["structuredQuery"]["where"] = {
            "compositeFilter": {
                "op": "AND",
                "filters": [
                    {"fieldFilter": {"field": {"fieldPath": f}, "op": op, "value": _to_fs(val)}}
                    for f, op, val in filters
                ],
            }
        }

    # orderBy sadece filtre yoksa ekle (composite index sorunundan kaçın)
    if order_by and not filters:
        query["structuredQuery"]["orderBy"] = [
            {"field": {"fieldPath": order_by},
             "direction": "DESCENDING" if descending else "ASCENDING"}
        ]

    try:
        r = _http.post(
            _FS_QUERY.format(project=cfg["projectId"]),
            headers=_auth_hdr(token),
            json=query,
            timeout=15,
        )
        if r.status_code != 200:
            log.debug("query_collection (%s): %s", r.status_code, r.text[:200])
            return []
        return [_doc_to_dict(item["document"])
                for item in r.json() if "document" in item]
    except Exception as e:
        log.debug("query_collection exception: %s", e)
        return []


# ── Öğrenci kaydı ─────────────────────────────────────────────

def student_hash(student_no: str) -> str:
    """Öğrenci no → tek yönlü hash. Firebase'de no saklanmaz."""
    salt = b"alms-firebase-v1:"
    return hashlib.sha256(salt + student_no.encode()).hexdigest()[:32]


def register_student(student_no: str, version: str = "", platform: str = "") -> bool:
    """
    Öğrenci kaydını Firebase'e yazar/günceller.
    Doc ID: Firebase UID (request.auth.uid ile eşleşir → Security Rules çalışır).
    student_hash alan olarak saklanır (gizlilik için).
    """
    if not is_configured():
        return False
    uid = get_uid()
    if not uid:
        return False
    shash = student_hash(student_no)
    now   = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    existing = get_document("students", uid)
    if existing:
        return update_document("students", uid, {
            "last_login": now, "version": version, "platform": platform,
        })
    import platform as _plat
    return set_document("students", uid, {
        "student_hash":     shash,
        "last_login":       now,
        "created_at":       now,
        "version":          version,
        "platform":         platform or _plat.system(),
        "login_count":      1,
        "is_admin":         False,
        "admin_role":       None,
        "admin_faculty":    None,
        "admin_department": None,
    })


def is_admin(student_no: str) -> tuple[bool, str | None, str | None]:
    """
    Admin kontrolü Firebase UID üzerinden yapar.
    Security Rules isAdmin() ile aynı mantık — doc ID = Firebase UID.
    """
    if not is_configured():
        return False, None, None
    uid = get_uid()
    if not uid:
        return False, None, None
    doc = get_document("students", uid)
    if not doc:
        return False, None, None
    if doc.get("is_admin"):
        return True, doc.get("admin_role"), doc.get("admin_department")
    return False, None, None
