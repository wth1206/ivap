"""Password hashing tests."""

from app.core.security import hash_password, verify_password


def test_password_hash_roundtrip():
    encoded = hash_password("S3cret-password!")
    assert encoded.startswith("pbkdf2_sha256$600000$")
    assert verify_password("S3cret-password!", encoded) is True
    assert verify_password("wrong-password", encoded) is False


def test_invalid_encoded_hash_is_rejected():
    assert verify_password("anything", "not-a-valid-hash") is False
    assert verify_password("anything", "pbkdf2_sha256$0$00$00") is False
