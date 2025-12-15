
import pytest
from hypothesis import given, strategies as st
from datetime import datetime, timedelta
from jose import jwt
from config import settings
from auth import create_access_token, decode_access_token, TokenData, authenticate_user, MOCK_USERS_DB, verify_password, get_password_hash
from fastapi import HTTPException

# Strategies for hypothesis
username_strategy = st.text(min_size=1, max_size=50)
password_strategy = st.text(min_size=1, max_size=50)
user_id_strategy = st.integers(min_value=1)

@given(username=username_strategy, user_id=user_id_strategy)
def test_token_creation_and_decoding(username, user_id):
    """
    Property 2: Authentication Token Validity
    Req 2.4: Verify generated tokens are valid and contain correct data
    """
    data = {"sub": username, "user_id": user_id}
    token = create_access_token(data)
    
    # Decode token
    decoded_data = decode_access_token(token)
    
    assert decoded_data.username == username
    assert decoded_data.user_id == user_id

@given(username=username_strategy, user_id=user_id_strategy)
def test_token_expiration(username, user_id):
    """
    Property 2: Authentication Token Validity
    Req 2.5: Verify expired tokens are rejected
    """
    data = {"sub": username, "user_id": user_id}
    # Create a token that is already expired
    expires_delta = timedelta(minutes=-1)
    token = create_access_token(data, expires_delta=expires_delta)
    
    # Verify decoding raises HTTPException
    with pytest.raises(HTTPException) as excinfo:
        decode_access_token(token)
    
    assert excinfo.value.status_code == 401
    assert "Could not validate credentials" in excinfo.value.detail

@given(username=username_strategy, user_id=user_id_strategy)
def test_token_tampering(username, user_id):
    """
    Property 2: Authentication Token Validity
    Verify tampered tokens are rejected
    """
    data = {"sub": username, "user_id": user_id}
    token = create_access_token(data)
    
    # Tamper with the token (append characters)
    tampered_token = token + "tampered"
    
    with pytest.raises(HTTPException) as excinfo:
        decode_access_token(tampered_token)
        
    assert excinfo.value.status_code == 401

def test_password_hashing():
    """
    Verify password hashing mechanism
    """
    password = "securepassword123"
    hashed = get_password_hash(password)
    
    assert verify_password(password, hashed)
    assert not verify_password("wrongpassword", hashed)

def test_mock_authentication():
    """
    Verify authentication logic with mock DB
    """
    # Test valid credentials
    user = authenticate_user("admin", "admin123")
    assert user is not None
    assert user.username == "admin"
    
    # Test invalid username
    user = authenticate_user("nonexistent", "admin123")
    assert user is None
    
    # Test invalid password
    user = authenticate_user("admin", "wrongpassword")
    assert user is None
