from node.core.aggregator import RateAggregator


def test_detect_outliers_no_outliers():
    aggregator = RateAggregator(base_symbol="ADA-USD")
    rates = [10.0, 10.1, 10.2, 9.9, 9.8]
    filtered, outliers = aggregator.detect_outliers(rates)

    assert len(outliers) == 0
    assert len(filtered) == 5
    assert all(r in filtered for r in rates)


def test_detect_outliers_with_extreme_values():
    aggregator = RateAggregator(base_symbol="ADA-USD")
    # IQR method:
    # Q1 (25th): 10.0
    # Q3 (75th): 11.0
    # IQR: 1.0
    # Lower bound: 10.0 - 3*1.0 = 7.0
    # Upper bound: 11.0 + 3*1.0 = 14.0
    rates = [10.0, 10.5, 11.0, 10.2, 10.8, 1.0, 100.0]
    filtered, outliers = aggregator.detect_outliers(rates)

    assert 1.0 in outliers
    assert 100.0 in outliers
    assert len(outliers) == 2
    assert len(filtered) == 5
    assert all(7.0 <= r <= 14.0 for r in filtered)


def test_get_asset_symbol():
    # Simple symbol
    aggregator = RateAggregator(base_symbol="ADA-USD")
    assert aggregator.get_asset_symbol() == "ADA-USD"

    # Complex symbol with quote conversion
    # base: ADA-BTC, quote: BTC-USD -> final: ADA-USD
    aggregator = RateAggregator(
        base_symbol="ADA-BTC", quote_currency=True, quote_symbol="BTC-USD"
    )
    assert aggregator.get_asset_symbol() == "ADA-USD"
