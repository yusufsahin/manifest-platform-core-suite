import pytest
from unittest.mock import MagicMock
from mpc.features.workflow.persistence import RedisStateStore

def test_redis_persistence():
    mock_redis = MagicMock()
    store = RedisStateStore(client=mock_redis, prefix="test:")
    
    state_data = {"active_states": ["S1"], "is_active": True}
    store.save_state("inst1", state_data)
    
    # Verify Redis SET call
    mock_redis.set.assert_called_once()
    args, kwargs = mock_redis.set.call_args
    assert args[0] == "test:inst1"
    
    # Load state
    mock_redis.get.return_value = '{"active_states": ["S1"], "is_active": True}'
    loaded = store.load_state("inst1")
    assert loaded == state_data
    
    # Audit record
    store.record_audit("inst1", {"event": "E1"})
    mock_redis.rpush.assert_called_once()
    assert "audit:inst1" in mock_redis.rpush.call_args[0][0]

if __name__ == "__main__":
    test_redis_persistence()
    print("Redis persistence tests passed!")
