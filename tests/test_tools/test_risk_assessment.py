"""Tests for risk_assessment tool."""

import pytest

from src.tools.risk_assessment import (
    AssetClassExposure,
    ConcentrationRisk,
    DiversificationMetrics,
    GeographicExposure,
    RiskAssessmentResult,
    SectorExposure,
    VolatilityMetrics,
    calculate_concentration_score,
    calculate_diversification_asset_score,
    calculate_sector_concentration_score,
    generate_recommendations,
    get_risk_level,
    risk_assessment,
)


class TestCalculateConcentrationScore:
    """Tests for the concentration score calculator."""

    def test_empty_holdings(self):
        """Empty holdings should return 0 score."""
        score, max_pct, symbol = calculate_concentration_score([])
        assert score == 0.0
        assert max_pct == 0.0
        assert symbol is None

    def test_single_holding_high_concentration(self):
        """Single holding over 50% should give max concentration score."""
        holdings = [{"symbol": "AAPL", "allocation_pct": 100.0}]
        score, max_pct, symbol = calculate_concentration_score(holdings)
        assert score == 40  # Max score for single asset > 50%
        assert max_pct == 100.0
        assert symbol == "AAPL"

    def test_single_holding_30_to_50(self):
        """Single holding 30-50% should give 25 points plus top 3 bonus if applicable."""
        holdings = [
            {"symbol": "AAPL", "allocation_pct": 40.0},
            {"symbol": "MSFT", "allocation_pct": 35.0},
            {"symbol": "GOOGL", "allocation_pct": 25.0},
        ]
        score, max_pct, symbol = calculate_concentration_score(holdings)
        # Top 3 = 100% > 70%, so 25 + 20 = 45, capped at 40
        assert score == 40
        assert max_pct == 40.0
        assert symbol == "AAPL"

    def test_single_holding_20_to_30(self):
        """Single holding 20-30% should give 15 points plus top 3 bonus if applicable."""
        holdings = [
            {"symbol": "AAPL", "allocation_pct": 25.0},
            {"symbol": "MSFT", "allocation_pct": 25.0},
            {"symbol": "GOOGL", "allocation_pct": 25.0},
            {"symbol": "AMZN", "allocation_pct": 25.0},
        ]
        score, max_pct, symbol = calculate_concentration_score(holdings)
        # Top 3 = 75% > 70%, so 15 + 20 = 35
        assert score == 35.0
        assert max_pct == 25.0

    def test_top_3_over_70_adds_points(self):
        """Top 3 holdings over 70% should add 20 points to concentration score."""
        # Use a case where top 3 > 70% but single asset doesn't trigger concentration points
        holdings = [
            {"symbol": "AAPL", "allocation_pct": 24.0},
            {"symbol": "MSFT", "allocation_pct": 24.0},
            {"symbol": "GOOGL", "allocation_pct": 24.0},  # Total 72%
            {"symbol": "AMZN", "allocation_pct": 28.0},  # Single asset at 28% -> 15 points
        ]
        score, max_pct, symbol = calculate_concentration_score(holdings)
        # Single asset 28% (20-30 range) -> 15 pts, Top 3 = 76% > 70% -> +20 pts = 35
        assert score == 35.0
        assert max_pct == 28.0

    def test_handles_camel_case_keys(self):
        """Should handle both snake_case and camelCase keys."""
        holdings = [
            {"symbol": "AAPL", "allocationPct": 60.0},
        ]
        score, max_pct, symbol = calculate_concentration_score(holdings)
        assert score == 40
        assert max_pct == 60.0

    def test_well_diversified_low_score(self):
        """Well-diversified holdings should have low concentration score."""
        holdings = [
            {"symbol": f"STOCK{i}", "allocation_pct": 5.0} for i in range(20)
        ]
        score, max_pct, symbol = calculate_concentration_score(holdings)
        # Single asset only 5%, top 3 only 15% - no concentration points
        assert score == 0


class TestCalculateDiversificationAssetScore:
    """Tests for asset class diversification score."""

    def test_empty_holdings(self):
        """Empty holdings should return score for 0 asset classes."""
        score = calculate_diversification_asset_score([])
        assert score == 30  # 0 classes = high risk

    def test_single_asset_class(self):
        """Single asset class should give max points (high risk)."""
        holdings = [
            {"symbol": "AAPL", "allocation_pct": 50.0, "asset_class": "EQUITY"},
            {"symbol": "MSFT", "allocation_pct": 50.0, "asset_class": "EQUITY"},
        ]
        score = calculate_diversification_asset_score(holdings)
        assert score == 30

    def test_two_asset_classes(self):
        """Two asset classes should still give max points."""
        holdings = [
            {"symbol": "AAPL", "allocation_pct": 50.0, "asset_class": "EQUITY"},
            {"symbol": "BND", "allocation_pct": 50.0, "asset_class": "FIXED_INCOME"},
        ]
        score = calculate_diversification_asset_score(holdings)
        assert score == 30  # < 3 classes

    def test_three_to_five_asset_classes(self):
        """3-5 asset classes should give 15 points."""
        holdings = [
            {"symbol": "AAPL", "allocation_pct": 25.0, "asset_class": "EQUITY"},
            {"symbol": "BND", "allocation_pct": 25.0, "asset_class": "FIXED_INCOME"},
            {"symbol": "BTC", "allocation_pct": 25.0, "asset_class": "CRYPTOCURRENCY"},
            {"symbol": "REIT", "allocation_pct": 25.0, "asset_class": "REAL_ESTATE"},
        ]
        score = calculate_diversification_asset_score(holdings)
        assert score == 15

    def test_more_than_five_asset_classes(self):
        """>5 asset classes should give minimum points (best diversification)."""
        holdings = [
            {"symbol": "VTI", "allocation_pct": 20.0, "asset_class": "EQUITY"},
            {"symbol": "BND", "allocation_pct": 20.0, "asset_class": "FIXED_INCOME"},
            {"symbol": "BTC", "allocation_pct": 15.0, "asset_class": "CRYPTOCURRENCY"},
            {"symbol": "REIT", "allocation_pct": 15.0, "asset_class": "REAL_ESTATE"},
            {"symbol": "GLD", "allocation_pct": 15.0, "asset_class": "COMMODITY"},
            {"symbol": "CASH", "allocation_pct": 15.0, "asset_class": "CASH"},
        ]
        score = calculate_diversification_asset_score(holdings)
        assert score == 5

    def test_handles_camel_case(self):
        """Should handle camelCase assetClass key."""
        holdings = [
            {"symbol": "AAPL", "allocation_pct": 50.0, "assetClass": "EQUITY"},
            {"symbol": "BND", "allocation_pct": 50.0, "assetClass": "FIXED_INCOME"},
            {"symbol": "BTC", "allocation_pct": 50.0, "assetClass": "CRYPTOCURRENCY"},
        ]
        score = calculate_diversification_asset_score(holdings)
        assert score == 15


class TestCalculateSectorConcentrationScore:
    """Tests for sector concentration score."""

    def test_empty_holdings(self):
        """Empty holdings should return base score."""
        score, sectors = calculate_sector_concentration_score([])
        assert score == 10
        assert sectors == {}

    def test_top_sector_over_60(self):
        """Top sector over 60% should give max points."""
        holdings = [
            {"symbol": "AAPL", "allocation_pct": 65.0, "asset_class": "EQUITY"},
            {"symbol": "BND", "allocation_pct": 35.0, "asset_class": "FIXED_INCOME"},
        ]
        score, sectors = calculate_sector_concentration_score(holdings)
        assert score == 30
        assert "EQUITY" in sectors
        assert sectors["EQUITY"] == 65.0

    def test_top_sector_40_to_60(self):
        """Top sector 40-60% should give 20 points."""
        holdings = [
            {"symbol": "AAPL", "allocation_pct": 50.0, "asset_class": "EQUITY"},
            {"symbol": "BND", "allocation_pct": 30.0, "asset_class": "FIXED_INCOME"},
            {"symbol": "BTC", "allocation_pct": 20.0, "asset_class": "CRYPTOCURRENCY"},
        ]
        score, sectors = calculate_sector_concentration_score(holdings)
        assert score == 20

    def test_top_sector_under_40(self):
        """Top sector under 40% should give minimum points."""
        holdings = [
            {"symbol": "AAPL", "allocation_pct": 25.0, "asset_class": "EQUITY"},
            {"symbol": "BND", "allocation_pct": 25.0, "asset_class": "FIXED_INCOME"},
            {"symbol": "BTC", "allocation_pct": 25.0, "asset_class": "CRYPTOCURRENCY"},
            {"symbol": "REIT", "allocation_pct": 25.0, "asset_class": "REAL_ESTATE"},
        ]
        score, sectors = calculate_sector_concentration_score(holdings)
        assert score == 10

    def test_aggregates_allocations(self):
        """Should aggregate allocations by sector."""
        holdings = [
            {"symbol": "AAPL", "allocation_pct": 30.0, "asset_class": "EQUITY"},
            {"symbol": "MSFT", "allocation_pct": 30.0, "asset_class": "EQUITY"},
            {"symbol": "BND", "allocation_pct": 40.0, "asset_class": "FIXED_INCOME"},
        ]
        score, sectors = calculate_sector_concentration_score(holdings)
        assert sectors["EQUITY"] == 60.0
        assert sectors["FIXED_INCOME"] == 40.0
        assert score == 20  # Top sector (EQUITY) is 60%, which is in 40-60 range


class TestGenerateRecommendations:
    """Tests for recommendation generation."""

    def test_single_asset_over_30(self):
        """Should recommend reducing single large position."""
        recommendations = generate_recommendations(
            single_asset_max=45.0,
            max_symbol="AAPL",
            num_asset_classes=3,
            top_3_sum=75.0,
            overall_score=65.0,
        )
        assert any("AAPL" in r for r in recommendations)
        assert any("30%" in r for r in recommendations)

    def test_few_asset_classes(self):
        """Should recommend diversifying asset classes."""
        recommendations = generate_recommendations(
            single_asset_max=20.0,
            max_symbol="AAPL",
            num_asset_classes=2,
            top_3_sum=50.0,
            overall_score=40.0,
        )
        assert any("asset class" in r.lower() for r in recommendations)

    def test_top_3_over_70(self):
        """Should recommend broad market ETFs."""
        recommendations = generate_recommendations(
            single_asset_max=25.0,
            max_symbol="AAPL",
            num_asset_classes=3,
            top_3_sum=75.0,
            overall_score=50.0,
        )
        assert any("70%" in r for r in recommendations)

    def test_high_overall_risk(self):
        """Should recommend fixed income for high risk."""
        recommendations = generate_recommendations(
            single_asset_max=25.0,
            max_symbol="AAPL",
            num_asset_classes=4,
            top_3_sum=60.0,
            overall_score=75.0,
        )
        assert any("fixed income" in r.lower() for r in recommendations)

    def test_low_risk_positive_feedback(self):
        """Low risk portfolio should get positive recommendation."""
        recommendations = generate_recommendations(
            single_asset_max=15.0,
            max_symbol="AAPL",
            num_asset_classes=5,
            top_3_sum=40.0,
            overall_score=20.0,
        )
        assert any("well-diversified" in r.lower() for r in recommendations)

    def test_always_at_least_one_recommendation(self):
        """Should always have at least one recommendation."""
        recommendations = generate_recommendations(
            single_asset_max=10.0,
            max_symbol="AAPL",
            num_asset_classes=6,
            top_3_sum=25.0,
            overall_score=15.0,
        )
        assert len(recommendations) >= 1


class TestGetRiskLevel:
    """Tests for risk level conversion."""

    def test_low_risk(self):
        """Score under 25 should be LOW."""
        assert get_risk_level(0) == "LOW"
        assert get_risk_level(24) == "LOW"

    def test_medium_risk(self):
        """Score 25-49 should be MEDIUM."""
        assert get_risk_level(25) == "MEDIUM"
        assert get_risk_level(49) == "MEDIUM"

    def test_high_risk(self):
        """Score 50-74 should be HIGH."""
        assert get_risk_level(50) == "HIGH"
        assert get_risk_level(74) == "HIGH"

    def test_very_high_risk(self):
        """Score 75+ should be VERY_HIGH."""
        assert get_risk_level(75) == "VERY_HIGH"
        assert get_risk_level(100) == "VERY_HIGH"


class TestConcentrationRisk:
    """Tests for ConcentrationRisk model."""

    def test_valid_concentration_risk(self):
        """Create valid concentration risk."""
        risk = ConcentrationRisk(
            top_holdings_pct=65.0,
            single_asset_max=35.0,
            top_holdings=[{"symbol": "AAPL", "percentage": 35.0}],
            top_sectors=[SectorExposure(sector="EQUITY", percentage=60.0)],
        )
        assert risk.top_holdings_pct == 65.0
        assert risk.single_asset_max == 35.0
        assert len(risk.top_holdings) == 1


class TestDiversificationMetrics:
    """Tests for DiversificationMetrics model."""

    def test_valid_diversification_metrics(self):
        """Create valid diversification metrics."""
        metrics = DiversificationMetrics(
            sectors=[SectorExposure(sector="EQUITY", percentage=60.0)],
            asset_types=[AssetClassExposure(asset_class="EQUITY", percentage=60.0)],
            geographic=[GeographicExposure(region="US", percentage=80.0)],
            num_sectors=3,
            num_asset_types=4,
            num_holdings=10,
        )
        assert metrics.num_sectors == 3
        assert metrics.num_asset_types == 4
        assert metrics.num_holdings == 10


class TestRiskAssessmentResult:
    """Tests for RiskAssessmentResult model."""

    def test_valid_result(self):
        """Create valid risk assessment result."""
        result = RiskAssessmentResult(
            overall_risk_score=45.0,
            risk_level="MEDIUM",
            concentration_risk=ConcentrationRisk(
                top_holdings_pct=65.0,
                single_asset_max=35.0,
            ),
            diversification=DiversificationMetrics(
                num_sectors=3,
                num_asset_types=3,
            ),
            recommendations=["Diversify further"],
            last_updated="2024-02-24T12:00:00",
        )
        assert result.overall_risk_score == 45.0
        assert result.risk_level == "MEDIUM"
        assert result.data_source == "ghostfolio"

    def test_result_with_volatility(self):
        """Create result with volatility metrics."""
        result = RiskAssessmentResult(
            overall_risk_score=55.0,
            risk_level="HIGH",
            concentration_risk=ConcentrationRisk(
                top_holdings_pct=75.0,
                single_asset_max=40.0,
            ),
            diversification=DiversificationMetrics(),
            volatility_metrics=VolatilityMetrics(
                portfolio_volatility=0.18,
                max_drawdown=-0.15,
            ),
            recommendations=["Add bonds"],
            last_updated="2024-02-24T12:00:00",
        )
        assert result.volatility_metrics is not None
        assert result.volatility_metrics.portfolio_volatility == 0.18


class TestRiskAssessmentTool:
    """Tests for the risk_assessment tool."""

    @pytest.mark.asyncio
    async def test_basic_assessment(self):
        """Test basic risk assessment returns valid result."""
        result = await risk_assessment.ainvoke({})

        assert isinstance(result, RiskAssessmentResult)
        assert 0 <= result.overall_risk_score <= 100
        assert result.risk_level in ["LOW", "MEDIUM", "HIGH", "VERY_HIGH"]
        assert len(result.recommendations) >= 1

    @pytest.mark.asyncio
    async def test_concentration_risk_calculated(self):
        """Test that concentration risk is calculated."""
        result = await risk_assessment.ainvoke({})

        assert result.concentration_risk.top_holdings_pct >= 0
        assert result.concentration_risk.single_asset_max >= 0

    @pytest.mark.asyncio
    async def test_diversification_metrics_calculated(self):
        """Test that diversification metrics are calculated."""
        result = await risk_assessment.ainvoke({})

        assert result.diversification.num_holdings >= 0
        assert result.diversification.num_asset_types >= 0

    @pytest.mark.asyncio
    async def test_recommendations_present(self):
        """Test that recommendations are always provided."""
        result = await risk_assessment.ainvoke({})

        assert len(result.recommendations) >= 1
        for rec in result.recommendations:
            assert len(rec) > 0

    @pytest.mark.asyncio
    async def test_with_custom_portfolio_data(self):
        """Test assessment with custom portfolio data."""
        custom_portfolio = {
            "holdings": [
                {"symbol": "VTI", "allocation_pct": 40.0, "asset_class": "EQUITY"},
                {"symbol": "VXUS", "allocation_pct": 30.0, "asset_class": "EQUITY"},
                {"symbol": "BND", "allocation_pct": 20.0, "asset_class": "FIXED_INCOME"},
                {"symbol": "BTC", "allocation_pct": 10.0, "asset_class": "CRYPTOCURRENCY"},
            ]
        }

        result = await risk_assessment.ainvoke({"portfolio_data": custom_portfolio})

        assert isinstance(result, RiskAssessmentResult)
        assert result.diversification.num_holdings == 4
        # Well-diversified: single asset max 40% (25 pts), 3 asset classes (15 pts), sector ~70% (20 pts)
        # Total should be around 60

    @pytest.mark.asyncio
    async def test_highly_concentrated_portfolio(self):
        """Test assessment of highly concentrated portfolio."""
        concentrated_portfolio = {
            "holdings": [
                {"symbol": "GME", "allocation_pct": 80.0, "asset_class": "EQUITY"},
                {"symbol": "AMC", "allocation_pct": 20.0, "asset_class": "EQUITY"},
            ]
        }

        result = await risk_assessment.ainvoke({"portfolio_data": concentrated_portfolio})

        assert result.overall_risk_score >= 60  # Should be high risk
        assert result.risk_level in ["HIGH", "VERY_HIGH"]
        assert len(result.warnings) > 0  # Should have warnings

    @pytest.mark.asyncio
    async def test_empty_portfolio(self):
        """Test assessment of empty portfolio."""
        empty_portfolio = {"holdings": []}

        result = await risk_assessment.ainvoke({"portfolio_data": empty_portfolio})

        assert result.overall_risk_score == 0.0
        assert result.risk_level == "LOW"

    @pytest.mark.asyncio
    async def test_data_source_is_ghostfolio(self):
        """Test that data source is set correctly."""
        result = await risk_assessment.ainvoke({})

        assert result.data_source == "ghostfolio"

    @pytest.mark.asyncio
    async def test_last_updated_is_set(self):
        """Test that last_updated timestamp is set."""
        result = await risk_assessment.ainvoke({})

        assert result.last_updated is not None
        assert len(result.last_updated) > 0
