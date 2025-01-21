import logging
import os
from logging.config import dictConfig
from pathlib import Path
from typing import Optional

import click
import yaml
from charli3_dendrite.backend import set_backend
from charli3_dendrite.backend.blockfrost import BlockFrostBackend
from charli3_dendrite.backend.ogmios_kupo import OgmiosKupoBackend
from charli3_offchain_core.blockchain.chain_query import ChainQuery
from charli3_offchain_core.blockchain.transactions import TransactionManager
from logfiles.logging_config import LEVEL_COLORS, get_log_config
from pycardano import (
    BlockFrostChainContext,
    ExtendedSigningKey,
    HDWallet,
    KupoOgmiosV6ChainContext,
    Network,
    PaymentVerificationKey,
)

from .models import AppConfig

logger = logging.getLogger(__name__)


def setup_dendrite_backend(config):
    """Setup the backend based on the provided configuration."""
    # Extract chain configuration (blockfrost or ogmios)
    chain_query_config = config.chain_query  # Access directly
    external_config = chain_query_config.external  # Access directly

    network = chain_query_config.network.lower()  # Access directly

    # Set the backend based on the network type (mainnet or testnet)
    if network == "testnet":
        # Handle testnet-specific setup
        blockfrost_config = external_config.get("blockfrost", {})
        blockfrost_id = blockfrost_config.get("project_id")

        external_ogmios_config = external_config.get("ogmios", {})
        external_ws_url = external_ogmios_config.get("ws_url")
        external_kupo_url = external_ogmios_config.get("kupo_url")

        # If external Ogmios or Blockfrost configuration is provided, use those
        if external_ws_url and external_kupo_url:
            set_backend(
                OgmiosKupoBackend(
                    external_ws_url,
                    external_kupo_url,
                    Network.TESTNET,  # Adjust based on the network
                )
            )
            logger.warning("External Ogmios backend configured for Testnet.")
        elif blockfrost_id:
            set_backend(BlockFrostBackend(blockfrost_id))
            logger.warning("Blockfrost backend configured for Testnet.")
        else:
            logger.error(
                "❌ Missing external Ogmios or Blockfrost configuration for Testnet."
            )
            return False
    else:
        # Handle mainnet setup
        ogmios_config = chain_query_config.ogmios
        if "ws_url" in ogmios_config and "kupo_url" in ogmios_config:
            set_backend(
                OgmiosKupoBackend(
                    ogmios_config["ws_url"], ogmios_config["kupo_url"], Network.MAINNET
                )
            )
            logger.warning("Ogmios backend configured for Mainnet.")
        else:
            logger.error("❌ Missing Ogmios configuration for Mainnet.")
            return False

    return True


def setup_blockfrost_context(
    config: AppConfig, network: Network
) -> Optional[BlockFrostChainContext]:
    """
    Setup BlockFrost chain context if configuration is provided.

    Args:
        config (AppConfig): Application configuration object.
        network (Network): Cardano network.

    Returns:
        Optional[BlockFrostChainContext]: Configured BlockFrost context or None.
    """
    blockfrost_config = config.chain_query.blockfrost

    if blockfrost_config and blockfrost_config.project_id:
        os.environ["PROJECT_ID"] = blockfrost_config.project_id

        return BlockFrostChainContext(
            blockfrost_config.project_id,
            network,
            base_url=blockfrost_config.base_url or "",
        )

    return None


def setup_ogmios_context(
    config: AppConfig, network: Network
) -> Optional[KupoOgmiosV6ChainContext]:
    """
    Setup Ogmios chain context if configuration is provided.

    Args:
        config (AppConfig): Application configuration object.
        network (Network): Cardano network.

    Returns:
        Optional[KupoOgmiosV6ChainContext]: Configured Ogmios context or None.
    """
    ogmios_config = config.chain_query.ogmios
    if ogmios_config and ogmios_config["ws_url"]:
        try:
            _, ws_string = ogmios_config["ws_url"].split("ws://")
            ws_url, port = ws_string.split(":")
        except ValueError:
            logger.error("Invalid Ogmios WebSocket URL format")
            return None

        return KupoOgmiosV6ChainContext(
            host=ws_url,
            port=int(port),
            secure=False,
            refetch_chain_tip_interval=None,
            network=network,
            kupo_url=ogmios_config["kupo_url"],
        )

    return None


def setup_network(config) -> Network:
    """Setup the network based on the specified configuration."""
    network_config = config.chain_query
    network = (
        Network.TESTNET if network_config.network == "TESTNET" else Network.MAINNET
    )
    os.environ["NETWORK"] = "preprod" if network == Network.TESTNET else "mainnet"
    return network


def setup_chain_query_and_tx_manager(
    config: AppConfig,
) -> tuple[ChainQuery, TransactionManager]:
    """
    Setup and initialize chain query and tx manager based on application configuration.

    Args:
        config (AppConfig): Application configuration object.

    Returns:
        Tuple[ChainQuery]: Configured chain query and tx manager instances.
    """
    network = setup_network(config)

    blockfrost_context = setup_blockfrost_context(config, network)
    ogmios_context = setup_ogmios_context(config, network)

    chain_query = ChainQuery(
        blockfrost_context=blockfrost_context, kupo_ogmios_context=ogmios_context
    )

    tx_manager = TransactionManager(chain_query=chain_query)
    return chain_query, tx_manager


def load_keys(config: AppConfig) -> list:
    """Returns complete set of node keys from config

    Returns:
        List containing in order:
        - node_sk: Node signing key for oracle operations
        - node_vk: Node verification key
        - node_vkh: Node verification key hash
        - payment_sk: Signing key for payments
        - payment_vk: Verification key for payments
        - payment_vkh: Payment verification key hash
    """
    hdwallet = HDWallet.from_mnemonic(config.node.mnemonic)

    # Generate node keys (for oracle operations)
    node_hdwallet = hdwallet.derive_from_path("m/1852'/1815'/0'/0/0")
    node_sk = ExtendedSigningKey.from_hdwallet(node_hdwallet)
    node_vk = PaymentVerificationKey.from_primitive(node_hdwallet.public_key)
    node_vkh = node_vk.hash()

    # Generate payment keys (for funds management)
    payment_hdwallet = hdwallet.derive_from_path("m/1852'/1815'/0'/2/0")
    payment_sk = ExtendedSigningKey.from_hdwallet(payment_hdwallet)
    payment_vk = PaymentVerificationKey.from_primitive(payment_hdwallet.public_key)
    payment_vkh = payment_vk.hash()

    return [node_sk, node_vk, node_vkh, payment_sk, payment_vk, payment_vkh]


def setup_logging(config: dict) -> logging.Logger:
    """Initialize and configure logger with color support."""
    # Configure using dictConfig
    dictConfig(get_log_config(config["Updater"]))

    # Setup color formatter
    original_factory = logging.getLogRecordFactory()

    def record_factory(*args, **kwargs):
        record = original_factory(*args, **kwargs)
        record.level_color = LEVEL_COLORS.get(record.levelno // 10, "\033[0m")
        record.end_color = "\033[0m"
        return record

    logging.setLogRecordFactory(record_factory)

    # Create and return logger
    return logging.getLogger(__name__)


def load_config(config_path: str) -> AppConfig:
    """Load and validate application configuration."""
    try:
        config_file = Path(config_path)
        if not config_file.exists():
            raise FileNotFoundError(f"Config file not found: {config_path}")

        with open(config_file) as f:
            config_dict = yaml.safe_load(f)
            if not config_dict:
                raise ValueError("Empty configuration file")

        setup_logging(config_dict)
        welcome_message()
        return AppConfig.from_dict(config_dict)

    except Exception as e:
        logger.error(f"Failed to load config: {e}")
        raise click.ClickException(str(e))


def welcome_message():
    """Prints a welcome message with ASCII art."""
    try:
        current_dir = Path(__file__).parent.parent
        ascii_file = current_dir / "charli3.txt"
        with open(ascii_file, "r") as file:
            ascii_art = file.read()
            print(ascii_art)
    except FileNotFoundError:
        logger.warning("ASCII art file not found.")
    logger.info(
        "------------------------------------------------------------------------------"
    )
    logger.info("Welcome to CHARLI3's Multisig ODV Node Network as a Node Operator!")
    logger.info(
        "------------------------------------------------------------------------------"
    )
