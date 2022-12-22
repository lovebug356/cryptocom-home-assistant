from custom_components.cryptocom.utils import round_with_precision

def test_round_with_precision():
    assert round_with_precision(0.1, 0.1) == "0.1"
    assert round_with_precision(0.1, 0.01) == "0.10"
    assert round_with_precision(0.1, 1) == "0"
    assert round_with_precision(0.058442233, 0.00001) == "0.05844"