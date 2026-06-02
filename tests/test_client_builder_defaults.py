import unittest
from typing import Optional

from py_clob_client_v2.client import ClobClient
from py_clob_client_v2.clob_types import BuilderConfig, OrderArgsV2
from py_clob_client_v2.config import DEFAULT_BUILDER_CODE
from py_clob_client_v2.constants import AMOY
from py_clob_client_v2.order_utils.model.side import Side


PRIVATE_KEY = "0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80"
USER_BUILDER_CODE = "0x" + "12" * 32
CLIENT_BUILDER_CODE = "0x" + "ab" * 32
TOKEN_ID = "123"


def _make_client(builder_config: Optional[BuilderConfig] = None) -> ClobClient:
    return ClobClient(
        host="https://clob.polymarket.com",
        chain_id=AMOY,
        key=PRIVATE_KEY,
        builder_config=builder_config,
    )


def _prime_client(client: ClobClient):
    client._ClobClient__tick_sizes[TOKEN_ID] = "0.01"
    client._ClobClient__neg_risk[TOKEN_ID] = False
    client._ClobClient__cached_version = 2


class TestClientBuilderDefaults(unittest.TestCase):
    def test_uses_predx_builder_code_when_none_is_provided(self):
        client = _make_client()
        self.assertEqual(client.builder_config.builder_code, DEFAULT_BUILDER_CODE)

    def test_ignores_caller_supplied_builder_config(self):
        client = _make_client(BuilderConfig(builder_code=CLIENT_BUILDER_CODE))
        self.assertEqual(client.builder_config.builder_code, DEFAULT_BUILDER_CODE)

    def test_overrides_per_order_builder_code(self):
        client = _make_client()
        _prime_client(client)
        signed = client.create_order(
            OrderArgsV2(
                token_id=TOKEN_ID,
                price=0.5,
                size=10,
                side=Side.BUY,
                builder_code=USER_BUILDER_CODE,
            )
        )

        self.assertEqual(signed.builder, DEFAULT_BUILDER_CODE)


if __name__ == "__main__":
    unittest.main()
