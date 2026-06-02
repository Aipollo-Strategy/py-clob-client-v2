import unittest

from py_clob_client_v2.client import ClobClient
from py_clob_client_v2.clob_types import (
    BuilderFeeRate,
    FeeInfo,
    MarketOrderArgsV2,
    OrderArgsV2,
)
from py_clob_client_v2.config import DEFAULT_BUILDER_CODE
from py_clob_client_v2.constants import AMOY
from py_clob_client_v2.order_utils.model.side import Side

# publicly known private key
PRIVATE_KEY = "0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80"
TOKEN_ID = "123"
FEE_RATE = 0.25
FEE_EXPONENT = 2


def _make_cached_client(fee_slippage: float = 0) -> ClobClient:
    client = ClobClient(
        host="https://clob.polymarket.com",
        chain_id=AMOY,
        key=PRIVATE_KEY,
        fee_slippage=fee_slippage,
    )
    client._ClobClient__tick_sizes[TOKEN_ID] = "0.01"
    client._ClobClient__neg_risk[TOKEN_ID] = False
    client._ClobClient__fee_infos[TOKEN_ID] = FeeInfo(
        rate=FEE_RATE, exponent=FEE_EXPONENT
    )
    client._ClobClient__builder_fee_rates[DEFAULT_BUILDER_CODE] = BuilderFeeRate(
        maker=0.0,
        taker=0.01,
    )
    client._ClobClient__cached_version = 2
    return client


class TestClobClientFeeSlippage(unittest.TestCase):
    def test_defaults_to_zero(self):
        client = ClobClient(host="https://clob.polymarket.com", chain_id=AMOY)
        self.assertEqual(client.fee_slippage, 0)

    def test_accepts_float_between_1_and_100(self):
        client = ClobClient(
            host="https://clob.polymarket.com",
            chain_id=AMOY,
            fee_slippage=12.5,
        )
        self.assertEqual(client.fee_slippage, 12.5)

    def test_rejects_invalid_values_at_init(self):
        def make(fee_slippage):
            ClobClient(
                host="https://clob.polymarket.com",
                chain_id=AMOY,
                fee_slippage=fee_slippage,
            )

        with self.assertRaises(ValueError):
            make(0.5)
        with self.assertRaises(ValueError):
            make(101)
        with self.assertRaises(ValueError):
            make(float("nan"))


class TestClientOrderFeeAdjustment(unittest.TestCase):
    def test_adjusts_v2_buy_limit_size_when_user_usdc_balance_provided(self):
        client = _make_cached_client(fee_slippage=20)
        order = OrderArgsV2(
            token_id=TOKEN_ID,
            price=0.5,
            size=100,
            side=Side.BUY,
            user_usdc_balance=50,
        )
        signed = client.create_order(order)
        # requestedNotional = 100 * 0.5 = 50
        # feeBaseAmount = min(50, 50) = 50
        # feeRateComponent = 0.25 * (0.5 * 0.5)^2 = 0.015625
        # paddedFee = (50 / 0.5) * 0.015625 * 1.2 = 1.875
        # builderFee = 50 * 0.01 = 0.5
        # adjustedNotional = 50 - 1.875 - 0.5 = 47.625
        # adjustedSize = 47.625 / 0.5 = 95.25
        # makerAmount = 95.25 * 0.5 * 1e6 = 47625000
        # takerAmount = 95.25 * 1e6 = 95250000
        self.assertEqual(signed.makerAmount, "47625000")
        self.assertEqual(signed.takerAmount, "95250000")
        self.assertEqual(order.size, 100)

    def test_adjusts_v2_buy_limit_when_price_rounds_up_to_tick(self):
        client = _make_cached_client(fee_slippage=20)
        order = OrderArgsV2(
            token_id=TOKEN_ID,
            price=0.506,  # rounds to 0.51 for tick 0.01
            size=100,
            side=Side.BUY,
            user_usdc_balance=50,
        )
        signed = client.create_order(order)
        signed_notional = int(signed.makerAmount) / 1_000_000
        signed_shares = int(signed.takerAmount) / 1_000_000
        # Input price 0.505 rounds to 0.51
        # requestedNotional = 100 * 0.51 = 51, balance = 50
        # feeBaseAmount = min(51, 50) = 50
        # feeRateComponent = 0.25 * (0.51 * 0.49)^2 = 0.0156125025
        # paddedFeeRate = 0.0156125025 * 1.2 = 0.018735003
        # paddedFee = (50 / 0.51) * 0.018735003 ≈ 1.836765
        # builderFee = 50 * 0.01 = 0.5
        # adjustedNotional = 50 - 1.836765 - 0.5 = 47.663235
        # adjustedSize = 47.663235 / 0.51 ≈ 93.457...
        # roundDown(93.457, 2) = 93.45
        # makerAmount = 93.45 * 0.51 * 1e6 = 47659500
        # takerAmount = 93.45 * 1e6 = 93450000
        self.assertEqual(signed.makerAmount, "47659500")
        self.assertEqual(signed.takerAmount, "93450000")
        self.assertAlmostEqual(signed_notional, 47.6595, places=4)
        self.assertAlmostEqual(signed_shares, 93.45, places=2)

    def test_adjusts_v2_buy_market_amount_when_user_usdc_balance_provided(self):
        client = _make_cached_client(fee_slippage=20)
        order = MarketOrderArgsV2(
            token_id=TOKEN_ID,
            price=0.5,
            amount=50,
            side=Side.BUY,
            user_usdc_balance=50,
        )
        signed = client.create_market_order(order)
        # market BUY amount is already cash notional
        # feeBaseAmount = min(50, 50) = 50
        # paddedFee = (50 / 0.5) * 0.015625 * 1.2 = 1.875
        # builderFee = 50 * 0.01 = 0.5
        # adjustedAmount = 50 - 1.875 - 0.5 = 47.625
        # roundDown(47.625, 2) = 47.62
        # rawPrice = roundDown(0.5, 2) = 0.5
        # takerAmount = 47.62 / 0.5 = 95.24
        # makerAmount = 47.62 * 1e6 = 47620000
        # takerAmount = 95.24 * 1e6 = 95240000
        self.assertEqual(signed.makerAmount, "47620000")
        self.assertEqual(signed.takerAmount, "95240000")
        self.assertEqual(order.amount, 50)

    def test_v2_buy_limit_unchanged_without_user_usdc_balance(self):
        client = _make_cached_client(fee_slippage=20)
        order = OrderArgsV2(
            token_id=TOKEN_ID,
            price=0.5,
            size=100,
            side=Side.BUY,
        )
        signed = client.create_order(order)
        self.assertEqual(signed.makerAmount, "50000000")
        self.assertEqual(signed.takerAmount, "100000000")

    def test_v2_sell_limit_unchanged_with_user_usdc_balance(self):
        client = _make_cached_client(fee_slippage=20)
        order = OrderArgsV2(
            token_id=TOKEN_ID,
            price=0.5,
            size=100,
            side=Side.SELL,
            user_usdc_balance=50,
        )
        signed = client.create_order(order)
        self.assertEqual(signed.makerAmount, "100000000")
        self.assertEqual(signed.takerAmount, "50000000")
