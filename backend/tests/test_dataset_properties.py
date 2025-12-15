
import pytest
from fastapi.testclient import TestClient
from main import app
from config import settings
from unittest.mock import MagicMock, patch
import os
import shutil

client = TestClient(app)

@pytest.fixture
def mock_upload_file(tmp_path):
    # Create a dummy CSV
    content = "col1,col2,label\n1,2,0\n3,4,1"
    file_path = tmp_path / "test.csv"
    with open(file_path, "w") as f:
        f.write(content)
    return file_path

def test_dataset_upload_integrity(mock_upload_file):
    """
    Property 14: Dataset Integrity
    Req 14.1: Verify uploaded file is processed and metadata stored correctly
    """
    # Mock DB and Auth
    # We'll use the TestClient but need to bypass Auth or use valid token
    # For property test, we focus on the logic in router function if possible
    # Or mock dependencies.
    
    # Let's mock the 'get_current_user' and 'get_db' dependencies?
    # FastAPI override_dependency is cleaner
    
    from auth import get_current_user, TokenData
    from db.db_manager import get_db
    
    mock_user = TokenData(username="testuser", user_id=1, role="admin")
    app.dependency_overrides[get_current_user] = lambda: mock_user
    
    # Mock DB Session
    mock_db = MagicMock()
    # Mock query returning None for name check
    mock_db.query.return_value.filter.return_value.first.return_value = None
    
    app.dependency_overrides[get_db] = lambda: mock_db
    
    # File upload
    with open(mock_upload_file, "rb") as f:
        response = client.post(
            f"{settings.API_V1_PREFIX}/datasets/upload",
            files={"file": ("test_upload.csv", f, "text/csv")},
            data={"name": "test_dataset", "type": "custom", "description": "test"}
        )
        
    assert response.status_code == 200
    assert response.json()["message"] == "Dataset uploaded successfully"
    assert response.json()["sample_count"] == 2 # 2 rows in dummy csv
    
    # Verify DB add called
    assert mock_db.add.called
    assert mock_db.commit.called
    
    # Cleanup overrides
    app.dependency_overrides = {}
    
    # Cleanup uploaded file (it goes to 'data' dir in real implementation)
    # In test environment, we should check if file exists and delete
    # But since we mocked DB, the router logic ran.
    # The file saving logic uses os.path.join(DATA_DIR, ...)
    # We should clean up 'data' dir files created by test
    for f in os.listdir("data"):
        if f.startswith("test_dataset"):
            os.remove(os.path.join("data", f))

def test_invalid_file_type():
    """
    Verify rejection of non-CSV files
    """
    from auth import get_current_user, TokenData
    mock_user = TokenData(username="testuser", user_id=1, role="admin")
    app.dependency_overrides[get_current_user] = lambda: mock_user
    
    response = client.post(
        f"{settings.API_V1_PREFIX}/datasets/upload",
        files={"file": ("test.txt", b"content", "text/plain")},
        data={"name": "bad_file", "type": "custom"}
    )
    
    assert response.status_code == 400
    assert "Only CSV files" in response.json()["detail"]
    
    app.dependency_overrides = {}
