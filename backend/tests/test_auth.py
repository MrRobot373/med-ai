from tests.conftest import create_patient, login, make_user


def test_login_success_and_me(client):
    user = login(client)
    assert user["role"] == "admin"
    assert client.get("/api/auth/me").json()["email"] == "admin@test.local"


def test_wrong_password_and_unknown_user_look_identical(client):
    a = client.post("/api/auth/login", json={"email": "admin@test.local", "password": "nope"})
    b = client.post("/api/auth/login", json={"email": "ghost@test.local", "password": "nope"})
    assert a.status_code == b.status_code == 401
    assert a.json()["detail"] == b.json()["detail"]


def test_login_rate_limited(client):
    for _ in range(8):
        client.post("/api/auth/login", json={"email": "admin@test.local", "password": "bad"})
    r = client.post("/api/auth/login", json={"email": "admin@test.local", "password": "Admin@12345"})
    assert r.status_code == 429


def test_requires_session(client):
    assert client.get("/api/patients").status_code == 401


def test_logout_invalidates_session(admin):
    assert admin.get("/api/auth/me").status_code == 200
    admin.post("/api/auth/logout")
    assert admin.get("/api/auth/me").status_code == 401


def test_viewer_is_read_only(client):
    make_user("view@test.local", "viewer")
    login(client, "view@test.local", "Password@123")
    assert client.get("/api/patients").status_code == 200
    r = client.post("/api/patients", json={"mrn": "X1", "first_name": "A", "last_name": "B"})
    assert r.status_code == 403


def test_clinician_cannot_touch_settings_or_users(clinician):
    assert clinician.get("/api/settings").status_code == 403
    assert clinician.get("/api/users").status_code == 403
    assert clinician.get("/api/audit").status_code == 403
    create_patient(clinician)


def test_deactivated_user_cannot_sign_in(admin, client):
    r = admin.post(
        "/api/users",
        json={"email": "temp@test.local", "full_name": "Temp", "role": "clinician", "password": "Password@123"},
    )
    uid = r.json()["id"]
    admin.patch(f"/api/users/{uid}", json={"is_active": False})
    r = client.post("/api/auth/login", json={"email": "temp@test.local", "password": "Password@123"})
    assert r.status_code == 403


def test_admin_cannot_demote_self(admin):
    me = admin.get("/api/auth/me").json()
    assert admin.patch(f"/api/users/{me['id']}", json={"role": "viewer"}).status_code == 400


def test_preferences_are_whitelisted(admin):
    r = admin.put("/api/auth/me/preferences", json={"theme": "dark", "accent": "#0EA5E9", "role": "admin_hack"})
    prefs = r.json()["preferences"]
    assert prefs == {"theme": "dark", "accent": "#0EA5E9"}


def test_branding_is_public(client):
    r = client.get("/api/branding")
    assert r.status_code == 200
    assert r.json()["product_name"]
