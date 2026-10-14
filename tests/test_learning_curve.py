import pytest
from test_training import rows, training


def test_nested_curve_is_explicit_resubstitution_and_rejects_changed_membership():
    module = training()
    values = rows()
    curve = module.learning_curve([values[:6], values[:12], values])
    assert [r['n'] for r in curve] == [6, 12, 24]
    assert all(r['evaluation'] == 'diagnostic_resubstitution' for r in curve)
    with pytest.raises(ValueError, match='nested'):
        module.learning_curve([values[:6], values[6:18]])
