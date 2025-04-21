import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional, Tuple, Union

import yaml
from charli3_offchain_core.blockchain.chain_query import ChainQuery
from charli3_offchain_core.blockchain.transactions import TransactionManager
from pycardano import BlockFrostChainContext, Network, OgmiosV6ChainContext
from pycardano.backend.kupo import KupoChainContextExtension

logger = logging.getLogger(__name__)


@dataclass
class OgmiosConfig:
    """Ogmios configuration settings."""

    ws_url: str
    kupo_url: str


@dataclass
class BlockfrostConfig:
    """Blockfrost configuration settings."""

    project_id: str
    api_url: Optional[str] = None


@dataclass
class ChainQueryConfig:
    """Chain query configuration settings."""

    network: str
    is_local_testnet: Optional[bool] = False
    ogmios: Optional[OgmiosConfig] = None
    blockfrost: Optional[BlockfrostConfig] = None
    external: Optional[dict[str, Union[OgmiosConfig, BlockfrostConfig]]] = None


@dataclass
class ValidityWindow:
    """Validity window structure for transaction timing."""

    validity_start: int
    validity_end: int


def load_locust_config(config_path: str = "locust.yml") -> Dict[str, Any]:
    """Loads config from the specified YAML file."""
    try:
        config_file = Path(config_path)
        if not config_file.exists():
            logger.warning(f"Config file not found: {config_path}")
            return {}

        with open(config_file) as f:
            config_dict = yaml.safe_load(f)
            return config_dict or {}
    except Exception as e:
        logger.error(f"Failed to load config: {e}")
        return {}


def convert_to_chain_query_config(config: Dict[str, Any]) -> ChainQueryConfig:
    """Converts dictionary config to ChainQueryConfig object."""
    if not config or "ChainQuery" not in config:
        logger.error("ChainQuery configuration missing")
        raise ValueError("ChainQuery configuration is required")

    chain_config = config["ChainQuery"]

    # Create ogmios config if present
    ogmios = None
    if "ogmios" in chain_config:
        ogmios_dict = chain_config["ogmios"]
        ogmios = OgmiosConfig(
            ws_url=ogmios_dict["ws_url"], kupo_url=ogmios_dict["kupo_url"]
        )

    # Create blockfrost config if present
    blockfrost = None
    if "blockfrost" in chain_config:
        bf_dict = chain_config["blockfrost"]
        blockfrost = BlockfrostConfig(
            project_id=bf_dict["project_id"], api_url=bf_dict.get("api_url")
        )

    # Create external config if present
    external = None
    if "external" in chain_config:
        external_dict = chain_config["external"]
        external = {}

        if "ogmios" in external_dict:
            ext_ogmios = external_dict["ogmios"]
            external["ogmios"] = OgmiosConfig(
                ws_url=ext_ogmios["ws_url"], kupo_url=ext_ogmios["kupo_url"]
            )

        if "blockfrost" in external_dict:
            ext_bf = external_dict["blockfrost"]
            external["blockfrost"] = BlockfrostConfig(
                project_id=ext_bf["project_id"], api_url=ext_bf.get("api_url")
            )

    return ChainQueryConfig(
        network=chain_config["network"],
        is_local_testnet=chain_config.get("is_local_testnet", False),
        ogmios=ogmios,
        blockfrost=blockfrost,
        external=external,
    )


def setup_network(config: ChainQueryConfig) -> Network:
    """Sets up network based on configuration."""
    network_name = config.network.lower()

    if network_name == "mainnet":
        return Network.MAINNET
    else:
        return Network.TESTNET


def setup_blockfrost_context(
    config: ChainQueryConfig, network: Network
) -> Optional[BlockFrostChainContext]:
    """Sets up BlockFrost context if configured."""
    if not config.blockfrost:
        return None

    return BlockFrostChainContext(
        project_id=config.blockfrost.project_id,
        base_url=config.blockfrost.api_url,
        network=network,
    )


def setup_ogmios_context(
    config: ChainQueryConfig, network: Network
) -> Optional[KupoChainContextExtension]:
    """Setup Ogmios chain context if configuration is provided."""
    ogmios_config = config.ogmios
    if ogmios_config and hasattr(ogmios_config, "ws_url") and ogmios_config.ws_url:
        try:
            _, ws_string = ogmios_config.ws_url.split("ws://")
            ws_url, port = ws_string.split(":")
        except ValueError:
            logger.error("Invalid Ogmios WebSocket URL format")
            return None

        ogmios_context = OgmiosV6ChainContext(
            host=ws_url,
            port=int(port),
            secure=False,
            network=network,
            refetch_chain_tip_interval=None,
        )
        kupo_context = KupoChainContextExtension(
            ogmios_context,
            ogmios_config.kupo_url,
        )
        return kupo_context

    return None


def setup_chain_query_and_tx_manager(
    config: Dict[str, Any]
) -> Tuple[ChainQuery, TransactionManager]:
    """Sets up chain query and transaction manager."""
    chain_config = convert_to_chain_query_config(config)

    network = setup_network(chain_config)
    blockfrost_context = setup_blockfrost_context(chain_config, network)
    ogmios_context = setup_ogmios_context(chain_config, network)

    if not ogmios_context and not blockfrost_context:
        raise ValueError("No valid blockchain context configured")

    chain_query = ChainQuery(
        blockfrost_context=blockfrost_context, kupo_ogmios_context=ogmios_context
    )

    tx_manager = TransactionManager(chain_query=chain_query)
    return chain_query, tx_manager
