#!/bin/bash
# Verifier ACA-Py - HTTP 传输模式
# 用于与 Holder 进行 HTTP 通信

docker run -d --rm \
 --network host \
 --name verifier-acapy \
 -p 8082:8082 \
 -p 8002:8002 \
 -v ~/go/src/github.com/hyperledger/Indy/aca-py-wallet-verifier:/home/aries/.acapy_agent/wallet \
 bcgovimages/aries-cloudagent:py3.12_1.2.0 \
 start \
 --wallet-type askar \
 --wallet-storage-type sqlite \
 --seed 000000000000000000000000010Agent \
 --wallet-key welldone \
 --wallet-name verifierWallet \
 --genesis-url http://10.2.0.9/genesis \
 --inbound-transport http 0.0.0.0 8002 \
 --outbound-transport http \
 --endpoint http://10.2.0.9:8002 \
 --admin 0.0.0.0 8082 \
 --admin-insecure-mode \
 --connections-invite \
 --auto-provision \
 --auto-accept-requests \
 --auto-verify-presentation \
 --label Verifier.Agent
