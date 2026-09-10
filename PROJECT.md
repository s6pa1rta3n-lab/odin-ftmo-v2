# Project: FTMO Live Asymmetric Swing Trade Execution

## Architecture
- **Environment**: Remote GCP VM `matt-berserker` (`us-central1-a`, project `project-45c3b27c-b597-4704-a50`).
- **Runtime**: `/usr/bin/python3` (Python 3.9.2, `metaapi-cloud-sdk` v29.1.1).
- **Credentials**: `/home/solveetcoagula/odin_ftmo/config_us100.json`.
- **Broker Interface**: MetaApi Cloud SDK RPC connection to FTMO MT5 account `511338298` on `FTMO-Server`.
- **Risk Constraint**: Strictly hardcoded volume = `0.01` micro-lot for zero-risk tracking.

## Feature Inventory
| # | Feature | Description | Milestone | Source | Status |
|---|---------|-------------|-----------|--------|--------|
| 1 | Market Scan & Setup Thesis | Scan global markets (Crypto, Forex, Metals, Indices) and formulate high-probability asymmetric swing thesis | M1 | Survey | DONE |
| 2 | VM Environment & Config Integration | Connect to `matt-berserker`, parse `/home/solveetcoagula/odin_ftmo/config_us100.json`, connect to MetaApi RPC | M1 | Survey | DONE |
| 3 | Standalone Execution Script | Create `/home/solveetcoagula/odin_ftmo/execute_swing_trade.py` with hardcoded 0.01 micro-lot, safety assertions, SL/TP rounding, and execution receipt output | M1 | Implementation | DONE |
| 4 | Live Trade Dispatch & Verification | Execute script on VM, place 0.01 order, assert broker `10009` code, confirm `orderId`/`positionId` in live terminal state | M1 | Implementation & Verification | DONE |

## Milestones
| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| 1 | Swing Trade Execution & Verification | Formulate thesis, deploy standalone 0.01 lot execution script on VM, execute live order, verify broker order ID | None | DONE |

## Executed Setup Summary
- **Asset**: Spot Gold (`XAUUSD`)
- **Direction**: `BUY` (Long)
- **Broker Ticket ID**: `288956364` (Deal ID: `270495393`)
- **Volume**: `0.01` micro-lot (Zero-risk tracking trade)
- **Open Price**: `4438.72`
- **Stop Loss**: `4395.00` (Risk: 43.72 pts = $0.44 USD / 0.045% account equity)
- **Take Profit**: `4670.00` (Reward: 231.28 pts = $2.31 USD / 0.239% account equity)
- **Realized R:R Ratio**: `1:5.29`
- **Status**: Live, Verified Active on FTMO MT5 Terminal

## Interface Contracts
### VM ↔ MetaApi RPC
- **Input**: `symbol: str`, `order_type: str`, `volume: float = 0.01`, `entry_price: float`, `sl: float`, `tp: float`, `comment: str`
- **Output**: Order receipt JSON with `orderId`, `numericCode`, `stringCode`, `openPrice`, `timestamp`
- **Error Handling**: Exception raising on invalid stops, market closed, or non-10009 response codes.

## Code Layout
- Remote VM: `/home/solveetcoagula/odin_ftmo/execute_swing_trade.py` (Main execution script)
- Remote VM: `/home/solveetcoagula/odin_ftmo/execution_receipt.json` (Execution confirmation artifact)
- Remote VM: `/home/solveetcoagula/odin_ftmo/test_guardrails.py` (Guardrail test suite)
- Remote VM: `/home/solveetcoagula/odin_ftmo/config_us100.json` (MetaApi credentials source)
