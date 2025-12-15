
import pytest
from fastapi.testclient import TestClient
from main import app
from config import settings
from unittest.mock import MagicMock
from ml.detection_engine import SystemState

client = TestClient(app)

def test_config_consistency():
    """
    Property 15: Configuration Consistency
    Req 14.1: Verify config updates are reflected in system
    """
    # Mock Auth and Engine
    from auth import get_current_user, TokenData
    from api.routers.system import get_engine
    
    mock_user = TokenData(username="admin", user_id=1, role="admin")
    app.dependency_overrides[get_current_user] = lambda: mock_user
    
    mock_engine = MagicMock()
    mock_engine.state = SystemState.IDLE
    app.dependency_overrides[get_engine] = lambda: mock_engine
    
    # 1. Get initial config
    initial_threshold = settings.ALERT_THRESHOLD
    
    # 2. Update config
    new_threshold = 0.95
    response = client.put(
        f"{settings.API_V1_PREFIX}/system/config",
        json={"alert_threshold": new_threshold}
    )
    assert response.status_code == 200
    
    # 3. Verify settings updated
    assert settings.ALERT_THRESHOLD == new_threshold
    
    # 4. Verify Get returns new value
    response = client.get(f"{settings.API_V1_PREFIX}/system/config")
    assert response.json()["alert_threshold"] == new_threshold
    
    # Cleanup
    settings.ALERT_THRESHOLD = initial_threshold
    app.dependency_overrides = {}

def test_config_update_blocking():
    """
    Property 15: Configuration Consistency
    Req 14.2: Verify config cannot be updated while running
    """
    from auth import get_current_user, TokenData
    from api.routers.system import get_engine
    
    mock_user = TokenData(username="admin", user_id=1, role="admin")
    app.dependency_overrides[get_current_user] = lambda: mock_user
    
    mock_engine = MagicMock()
    mock_engine.state = SystemState.RUNNING
    app.dependency_overrides[get_engine] = lambda: mock_engine
    
    response = client.put(
        f"{settings.API_V1_PREFIX}/system/config",
        json={"alert_threshold": 0.5}
    )
    assert response.status_code == 400
    
    app.dependency_overrides = {}
