import os
import json
import pytest
from pathlib import Path

TEST_DB = "test.db"

# Flask-SQLAlchemy 3.x binds the engine when the app is imported, so the
# test database must be chosen before the import (not inside the fixture).
os.environ["DATABASE_URL"] = f"sqlite:///{Path(__file__).resolve().parent.parent.joinpath(TEST_DB)}"

from project.app import app, db


@pytest.fixture
def client():
    BASE_DIR = Path(__file__).resolve().parent.parent
    app.config["TESTING"] = True
    app.config["DATABASE"] = BASE_DIR.joinpath(TEST_DB)
    app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{BASE_DIR.joinpath(TEST_DB)}"

    with app.app_context():
        db.create_all()  # setup
        yield app.test_client()  # tests run here
        db.drop_all()  # teardown


def login(client, username, password):
    """Login helper function"""
    return client.post(
        "/login",
        data=dict(username=username, password=password),
        follow_redirects=True,
    )


def logout(client):
    """Logout helper function"""
    return client.get("/logout", follow_redirects=True)


def test_index(client):
    response = client.get("/", content_type="html/text")
    assert response.status_code == 200


def test_database(client):
    """initial test. ensure that the database exists"""
    tester = Path("test.db").is_file()
    assert tester


def test_empty_db(client):
    """Ensure database is blank"""
    rv = client.get("/")
    assert b"No entries yet. Add some!" in rv.data


def test_login_logout(client):
    """Test login and logout using helper functions"""
    rv = login(client, app.config["USERNAME"], app.config["PASSWORD"])
    assert b"You were logged in" in rv.data
    rv = logout(client)
    assert b"You were logged out" in rv.data
    rv = login(client, app.config["USERNAME"] + "x", app.config["PASSWORD"])
    assert b"Invalid username" in rv.data
    rv = login(client, app.config["USERNAME"], app.config["PASSWORD"] + "x")
    assert b"Invalid password" in rv.data


def test_messages(client):
    """Ensure that user can post messages"""
    login(client, app.config["USERNAME"], app.config["PASSWORD"])
    rv = client.post(
        "/add",
        data=dict(title="<Hello>", text="<strong>HTML</strong> allowed here"),
        follow_redirects=True,
    )
    assert b"No entries here so far" not in rv.data
    assert b"&lt;Hello&gt;" in rv.data
    assert b"<strong>HTML</strong> allowed here" in rv.data


def test_delete_message(client):
    """Ensure the messages are being deleted"""
    rv = client.get("/delete/1")
    data = json.loads(rv.data)
    assert data["status"] == 0
    login(client, app.config["USERNAME"], app.config["PASSWORD"])
    rv = client.get("/delete/1")
    data = json.loads(rv.data)
    assert data["status"] == 1


def test_delete_requires_login(client):
    """Ensure logged-out users get a 401 and the post is kept"""
    login(client, app.config["USERNAME"], app.config["PASSWORD"])
    client.post("/add", data=dict(title="Keep me", text="still here"))
    logout(client)
    rv = client.get("/delete/1")
    assert rv.status_code == 401
    assert json.loads(rv.data) == {"status": 0, "message": "Please log in."}
    assert b"Keep me" in client.get("/").data


def test_search_page(client):
    """Ensure the search page loads without a query"""
    rv = client.get("/search/")
    assert rv.status_code == 200
    assert b"Search:" in rv.data


def test_search_results(client):
    """Ensure search matches title or text, case-insensitively"""
    login(client, app.config["USERNAME"], app.config["PASSWORD"])
    client.post("/add", data=dict(title="Flask Tips", text="routing"))
    client.post("/add", data=dict(title="Cooking", text="pasta recipe"))
    client.post("/add", data=dict(title="Misc", text="more FLASK things"))
    rv = client.get("/search/?query=flask")
    assert b"Flask Tips" in rv.data
    assert b"more FLASK things" in rv.data
    assert b"Cooking" not in rv.data
