# Cross-Chain Verifiable Credential System

> Trustless cross-chain credential transfer for commodity cross-border trade — issue on one chain, verify on another.

![Hyperledger Besu](https://img.shields.io/badge/blockchain-Hyperledger%20Besu-blue)
![Hyperledger Indy](https://img.shields.io/badge/identity-Hyperledger%20Indy-purple)
![ACA-Py](https://img.shields.io/badge/agent-ACA--Py%201.2.0-green)
![Solidity](https://img.shields.io/badge/solidity-0.5.16-orange)
![Python](https://img.shields.io/badge/python-3.8+-yellow)

---

## What It Does

This system enables **cross-chain Verifiable Credentials (VCs)** for commodity trade scenarios:

1. **Issue** a credential on Chain A (e.g. a quality inspection certificate) via Hyperledger Indy/Aries
2. **Transfer** the credential metadata across chains through an Oracle relay
3. **Verify** the credential on Chain B using zero-knowledge proofs — without revealing unnecessary data

### Supported Credential Types

| VC Type | Purpose | Attributes |
|---------|---------|-----------|
| InspectionReport | Quality inspection certificate | 7 |
| InsuranceContract | Cargo insurance proof | 10 |
| CertificateOfOrigin | Origin certificate | 9 |
| BillOfLadingCertificate | Electronic bill of lading | 10 |

---

## Architecture

```
                         Web Frontend (:3000)
                    ┌────────────────────────────┐
                    │  Monitor │ Issue │ Transfer │
                    │  Verify  │ Contracts │ Config│
                    └──────────────┬─────────────┘
                                   │
              ┌────────────────────┼────────────────────┐
              ▼                    ▼                    ▼
     ┌────────────────┐  ┌─────────────────┐  ┌───────────────┐
     │ Issuance Oracle │  │ Transfer Oracle │  │ VP Verification│
     │    (:6000)      │  │  (background)   │  │  Oracle (:7003)│
     └───────┬────────┘  └────────┬────────┘  └───────┬───────┘
             │                    │                   │
             ▼                    ▼                   ▼
   ┌──────────────────┐   ┌─────────────────────────────────┐
   │  Identity Layer   │   │        Smart Contract Layer      │
   │  Indy + ACA-Py   │   │                                   │
   │  (3 agents)       │   │  Chain A (:8545)    Chain B (:8555)│
   │                   │   │  ┌─────────────┐  ┌────────────┐│
   │  Issuer  :8080    │   │  │ DIDVerifier  │  │DIDVerifier ││
   │  Holder  :8081    │   │  │ ContractMgr  │  │            ││
   │  Verifier:8082    │   │  │ Bridge       │  │ Bridge     ││
   │                   │   │  │ 4x VCManager │  │            ││
   └──────────────────┘   │  └─────────────┘  └────────────┘│
                          └─────────────────────────────────┘
                                    Besu (IBFT 2.0)
                                  4 nodes per chain
```

### Deployed Contracts

| Chain | Contract | Address | Role |
|-------|----------|---------|------|
| A | `DIDVerifier` | `0x3696...64D2` | DID identity verification |
| A | `ContractManager` | `0xCe48...be2b` | Contract registry & permissions |
| A | `VCCrossChainBridgeSimple` | `0xBE2f...2763` | Cross-chain bridge core |
| A | `InspectionReportVCManager` | `0xf557...a7B` | Inspection report VC metadata |
| A | `InsuranceContractVCManager` | `0xC1e2...aa5` | Insurance VC metadata |
| A | `CertificateOfOriginVCManager` | `0x8499...D7C` | Origin VC metadata |
| A | `BillOfLadingVCManager` | `0xA9a4...701` | Bill of lading VC metadata |
| B | `DIDVerifier` | `0x234c...7C3a` | DID identity verification |
| B | `VCCrossChainBridgeSimple` | `0x0B3c...ac6` | Receives cross-chain VC data |

---

## Getting Started

### Prerequisites

- [Docker](https://docs.docker.com/get-docker/) & Docker Compose
- Python 3.8+
- [VON Network](https://github.com/bcgov/von-network) for Hyperledger Indy

### Install Python Dependencies

```bash
pip3 install flask==2.3.3 flask-cors flask-socketio==5.3.6 python-socketio==5.8.0 \
  eventlet==0.33.3 web3==6.11.1 eth-account requests==2.31.0 aiohttp==3.8.5 \
  py-solc-x==2.0.4 PyNaCl base58
```

### Start Services

Start in dependency order:

```bash
# 1. Besu blockchains (Chain A + Chain B, 4-node clusters each)
#    Refer to docker-compose configs in the project

# 2. VON Network (Indy ledger)
cd von-network && ./manage start <YOUR_IP> WEB_SERVER_HOST_PORT=80

# 3. ACA-Py agents (Issuer / Holder / Verifier)
./project_notes/start_all_acapy.sh

# 4. VC Issuance Oracle
cd VcIssureOracle && python3 vc_issuance_oracle.py          # :6000

# 5. VC Transfer Oracle
cd oracle && python3 vc_transfer_oracle.py \
  --config ../config/cross_chain_oracle_config.json

# 6. VP Verification Oracle
cd oracle && python3 predicate_flask_app.py                  # :7003

# 7. Web Application
cd webapp && python3 enhanced_app.py                         # :3000
```

Open http://localhost:3000 to access the dashboard.

### Stop Services

```bash
./project_notes/stop_acapy.sh   # Stop ACA-Py containers
# Ctrl+C for Oracle & Web services
```

---

## Quick Demo

Issue a credential, transfer it cross-chain, and verify — all in three commands:

```bash
# 1. Issue a VC on Chain A
curl -X POST http://localhost:6000/issue-vc \
  -H "Content-Type: application/json" \
  -d '{
    "vc_type": "InspectionReport",
    "metadata": {"vcName": "Quality Inspection Report"},
    "attributes": {
      "exporter": "Global Trading Co.",
      "contractName": "2024-TRADE-001",
      "productName": "Copper Concentrate",
      "productQuantity": "1000",
      "productBatch": "",
      "inspectionPassed": "true",
      "Date": "2026-04-25"
    }
  }'

# 2. Transfer the VC to Chain B
curl -X POST http://localhost:3000/api/crosschain/transfer \
  -H "Content-Type: application/json" \
  -d '{
    "vc_hash": "<vc_hash_from_step_1>",
    "vc_type": "InspectionReport",
    "target_chain": "chain_b",
    "vc_manager_type": "InspectionReport"
  }'

# 3. Verify on Chain B with ZKP
curl -X POST http://localhost:7003/api/verify-default \
  -H "Content-Type: application/json" \
  -d '{"vc_type": "InspectionReport", "vc_hash": "<vc_hash_from_step_1>"}'
```

---

## Services & Ports

| Port | Service | Description |
|------|---------|-------------|
| 3000 | Web Frontend | Dashboard, issuance, transfer, verification UI |
| 6000 | VC Issuance Oracle | Issues VCs via ACA-Py AIP 2.0, writes to Chain A |
| 7003 | VP Verification Oracle | ZKP-based credential verification |
| — | VC Transfer Oracle | Background process relaying VCSent events cross-chain |
| 8545 | Besu Chain A | Issuance chain (4 IBFT nodes) |
| 8555 | Besu Chain B | Verification chain (4 IBFT nodes) |
| 80 | VON Network | Indy ledger web server |
| 8080/8081/8082 | ACA-Py Admin | Issuer / Holder / Verifier admin APIs |
| 8000/8001/8002 | ACA-Py Endpoint | DIDComm endpoints |

---

## API Overview

### VC Issuance Oracle (`:6000`)

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/issue-vc` | Issue a VC |
| `GET` | `/health` | Health check |
| `GET` | `/vc-status/<vc_hash>` | VC processing status |
| `GET` | `/credentials` | Holder credentials (paginated, filterable) |
| `GET` | `/credentials/count` | Total credential count |

### VP Verification Oracle (`:7003`)

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/verify` | Verify with custom predicates |
| `POST` | `/api/verify-default` | Verify with default strategy |
| `GET` | `/api/vc-types` | Supported VC types |
| `GET` | `/api/vc-types/<type>/info` | VC type config (Schema, CredDef, contract) |
| `GET` | `/api/vc-types/<type>/predicate-policy` | Predicate policy |
| `GET` | `/api/predicate-policies` | All predicate policies |
| `GET` | `/api/health` | Health check |

### Web Application (`:3000`)

**Pages**: `/` (dashboard) · `/vc-issuance` · `/vc-crosschain-transfer` · `/vp-verification` · `/contract-viewer` · `/config-viewer`

Key API groups:

| Group | Prefix | Key Endpoints |
|-------|--------|--------------|
| System Status | `/api/status` | Chain status, block numbers, service health |
| VC Issuance | `/api/vc-issuance/*` | Issue, history, holder VCs, connection status |
| Cross-Chain Transfer | `/api/crosschain/*` | Transfer, VC hashes/metadata, bridge records |
| VP Verification | `/api/vp-verification/*` | Validate, UUIDs, holder credentials by type |
| Contract Viewer | `/api/contract-viewer/*` | Contract details, summary, refresh |
| Config Viewer | `/api/config-viewer/*` | List/read config files |

**WebSocket**: `status_update` event — server pushes system status to connected clients.

---

## How Cross-Chain Transfer Works

```
 Chain A (Issuance)                          Chain B (Verification)
 ┌─────────────────┐    Oracle Relay     ┌──────────────────────┐
 │ 1. Issue VC via  │                    │ 4. Write VC metadata │
 │    ACA-Py AIP2.0 │                    │    to Bridge contract│
 │ 2. Store VC Hash │   ┌───────────┐   │ 5. VP Verification:  │
 │    in VCManager  │──▶│  Transfer  │──▶│    ZKP proof request │
 │ 3. Bridge emits  │   │  Oracle    │   │    UUID matching     │
 │    VCSent event  │   └───────────┘   │    Predicate checks  │
 └─────────────────┘                    └──────────────────────┘
```

The Transfer Oracle is a background process that:
- Polls `VCSent` events on Chain A
- Reads VC metadata (12 fields) from the Bridge `sendList`
- Signs and submits transactions to Chain B's `completeCrossChainTransfer`
- Maintains deduplication cache and persistent state for crash recovery

---

## Project Structure

```
cross-chain-new/
├── infrastructure/          # DID generation, address mapping, on-chain registration
├── Authentication/          # Schema & CredDef creation scripts
├── contracts/kept/          # Solidity contracts, ABIs, deploy scripts
│   ├── *.sol               # 7 smart contracts
│   ├── contract_abis/      # Contract ABIs
│   └── build/              # Compiled output
├── VcIssureOracle/         # VC Issuance Oracle (:6000)
│   ├── vc_issuance_oracle.py
│   └── vc_issuance_config.json
├── oracle/                  # Transfer Oracle + VP Verification Oracle
│   ├── vc_transfer_oracle.py        # Cross-chain relay
│   ├── predicate_flask_app.py       # ZKP verification (:7003)
│   ├── vp_predicate_oracle_service.py
│   ├── blockchain_client.py
│   ├── acapy_client.py
│   └── connection_manager.py
├── webapp/                  # Web frontend (:3000)
│   ├── enhanced_app.py     # Main Flask app
│   ├── templates/          # HTML templates
│   └── static/             # CSS/JS
├── config/                  # All configuration files
│   ├── blockchain_config.json
│   ├── cross_chain_oracle_config.json
│   ├── deployed_contracts_config.json
│   ├── did_address_map.json
│   └── address.json
└── project_notes/           # Startup scripts & docs
    ├── start_all_acapy.sh
    └── stop_acapy.sh
```

---

## Configuration

| File | Location | What It Configures |
|------|----------|-------------------|
| `blockchain_config.json` | `config/` | Chain RPC URLs, chain IDs, gas settings |
| `cross_chain_oracle_config.json` | `config/` | Oracle accounts, contract addresses, polling interval, state path |
| `vc_issuance_config.json` | `VcIssureOracle/` | ACA-Py endpoints, Schema/CredDef IDs, contract addresses, oracle key |
| `vp_predicate_config.json` | `oracle/` | Predicate strategies, VC type attributes, blockchain connection |
| `deployed_contracts_config.json` | `config/` | All deployed contract addresses |
| `did_address_map.json` | `config/` | DID ↔ blockchain address mappings (29 entries) |

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Blockchain | Hyperledger Besu, IBFT 2.0 consensus |
| Smart Contracts | Solidity 0.5.16 |
| Identity | Hyperledger Indy (VON Network) |
| Agent | ACA-Py 1.2.0 (AIP 2.0, askar wallet) |
| Backend | Python 3.8+, Flask, Web3.py 6.11.1 |
| Frontend | Flask-SocketIO, HTML5/CSS3 |
| Infrastructure | Docker, Docker Compose |

---

## License

This project is licensed under the Apache-2.0 License — see the [LICENSE](LICENSE) file for details.

## Acknowledgements

- [Hyperledger Besu](https://besu.hyperledger.org/) — Enterprise Ethereum client
- [ACA-Py](https://github.com/hyperledger/aries-cloudagent-python) — Verifiable credential agent
- [Web3.py](https://web3py.readthedocs.io/) — Ethereum Python library
- [Flask](https://flask.palletsprojects.com/) — Web framework

## Contact

- Project: [https://github.com/mmjd2019/cross-chain](https://github.com/mmjd2019/cross-chain)
- Issues: [Issue Tracker](https://github.com/mmjd2019/cross-chain/issues)
- Email: ggg1234567@163.com



---

⭐ If this project helps you, please give us a star!
