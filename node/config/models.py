from dataclasses import dataclass, field
from typing import Any, Optional, Union


@dataclass
class NodeConfig:
    """Node configuration."""

    mnemonic: str
    oracle_currency: str
    oracle_address: str
    reward_collection_trigger: int
    reward_destination_address: str
    reward_token_hash: str | None = None
    reward_token_name: str | None = None


@dataclass
class OgmiosConfig:
    """Ogmios configuration."""

    ws_url: str
    kupo_url: str


@dataclass
class BlockfrostConfig:
    """Blockfrost configuration."""

    project_id: str
    api_url: Optional[str] = None


@dataclass
class ChainQueryConfig:
    """Chain query configuration."""

    network: str
    is_local_testnet: Optional[bool] = False
    ogmios: Optional[OgmiosConfig] = None
    blockfrost: Optional[BlockfrostConfig] = None
    external: Optional[dict[str, Union[OgmiosConfig, BlockfrostConfig]]] = None


@dataclass
class UpdaterConfig:
    """Updater configuration."""

    odv_fulfillment_inter: int
    verbosity: str = "INFO"
    percent_resolution: int = 10000


@dataclass
class SourceConfig:
    """Generic source configuration for all adapters."""

    name: str
    api_url: Optional[str] = None
    json_path: Optional[list[Union[str, int]]] = None
    headers: dict[str, str] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: Union[str, dict[str, Any]]) -> "SourceConfig":
        if isinstance(data, str):
            return cls(name=data)
        return cls(
            name=data["name"],
            api_url=data.get("api_url"),
            json_path=data.get("json_path", []),
            headers=data.get("headers", {}),
        )


@dataclass
class ExchangeSource:
    """Unified source configuration for DEX, CEX, and API adapters."""

    adapter: str
    asset_a: str
    asset_b: str
    sources: list[SourceConfig]
    quote_required: bool = False
    quote_calc_method: str = "multiply"

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ExchangeSource":
        sources = [SourceConfig.from_dict(src) for src in data.get("sources", [])]
        return cls(
            adapter=data["adapter"],
            asset_a=data["asset_a"],
            asset_b=data["asset_b"],
            sources=sources,
            quote_required=data.get("quote_required", False),
            quote_calc_method=data.get("quote_calc_method", "multiply"),
        )


@dataclass
class CurrencyConfig:
    """Currency configuration for base and quote currencies."""

    exchanges: list[ExchangeSource] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CurrencyConfig":
        exchanges = [
            ExchangeSource.from_dict(d)
            for d in data.get("dexes", [])
            + data.get("cexes", [])
            + data.get("api_sources", [])
        ]
        return cls(exchanges=exchanges)


@dataclass
class RateConfig:
    """Rate configuration."""

    general_base_symbol: str
    base_currency: CurrencyConfig
    general_quote_symbol: Optional[str] = None
    quote_currency: Optional[CurrencyConfig] = None
    min_requirement: bool = True

    @classmethod
    def from_dict(cls, config_dict: dict[str, Any]) -> "RateConfig":
        base_currency_data = config_dict.get("base_currency", {})
        base_currency = (
            CurrencyConfig.from_dict(base_currency_data)
            if isinstance(base_currency_data, dict)
            else base_currency_data
        )

        quote_currency_data = config_dict.get("quote_currency", {})
        quote_currency = (
            CurrencyConfig.from_dict(quote_currency_data)
            if isinstance(quote_currency_data, dict)
            else quote_currency_data
        )

        return cls(
            general_base_symbol=config_dict["general_base_symbol"],
            base_currency=base_currency,
            general_quote_symbol=config_dict.get("general_quote_symbol"),
            quote_currency=quote_currency,
            min_requirement=config_dict.get("min_requirement", True),
        )


@dataclass
class AppConfig:
    """Complete application configuration."""

    node: NodeConfig
    rate: RateConfig
    updater: UpdaterConfig
    chain_query: ChainQueryConfig

    @classmethod
    def from_dict(cls, config: dict[str, Any]) -> "AppConfig":
        """Create AppConfig from dictionary."""
        return cls(
            node=NodeConfig(**config.get("Node", {})),
            rate=RateConfig.from_dict(config.get("Rate", {})),
            updater=UpdaterConfig(**config.get("Updater", {})),
            chain_query=ChainQueryConfig(**config.get("ChainQuery", {})),
        )
