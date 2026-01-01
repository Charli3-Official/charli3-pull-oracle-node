# Charli3 Pull Oracle ODV Node Operator Backend

This project provides a backend for Node Operators participating in Charli3's ODV (On-Demand Validation) Oracle network. It is designed to fetch, aggregate and validate price data for specified assets, and participate in the ODV protocol through feed signing and transaction aggregation. The node utilizes the pycardano library for Cardano blockchain interactions.


## Getting Started

### Dependencies

This project uses Poetry to manage dependencies. If you don't have Poetry installed, you can install it by following the instructions at [Poetry documentation](https://python-poetry.org/docs/).

To install the required Python packages, run:
```bash
poetry install
```

Next, you will need to create a config.yml file containing the necessary configuration settings. You can use the provided [example-config.yml](example-config.yml) as a starting point.

## Running the Backend

### Locally

To run the backend locally, execute the main.py script inside the Poetry environment:

```bash
poetry run python node/main.py run -c config.yml
```

### Docker

Build image and run two nodes using this command:

```bash
docker compose build node1 && docker compose up -d
```

Attach to one of the nodes:

```bash
docker compose logs -f node1
```

## Configuration

The backend can be configured using a config.yml file. This file allows you to customize various settings such as:
- ChainQuery configurations (BlockFrost and Ogmios)
- Node (addresses, keys, mnemonics, etc.)
- Data providers for base and quote currency rates

Refer to the [example-config.yml](example-config.yml) file for an example configuration.

## Functionality

The ODV Node Operator Backend provides the following core functionality:

- **ODV Node Api Implementation**:
  - Feed value request handling
  - Aggregation Transaction signing

- **Price Data Management**:
  - Multi-source price aggregation
  - Outlier detection and filtering
  - Quote rate conversion

- **Blockchain Integration**:
  - Cardano network interaction via ChainQuery
  - Oracle NFT and Node Eligibility validations
