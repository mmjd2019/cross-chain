#!/bin/bash
# Issuer ACA-Py - HTTP 传输模式
# 用于与 Holder 进行 HTTP 通信

docker run -d  --rm \
 --network host \
 --name issuer-acapy \
 -p 8080:8080 \
 -p 8000:8000 \
 -v ~/go/src/github.com/hyperledger/Indy/aca-py-wallet-issuer:/home/aries/.acapy_agent/wallet \
 bcgovimages/aries-cloudagent:py3.12_1.2.0 \
 start \
 --wallet-type askar \
 --wallet-storage-type sqlite \
 --seed 000000000000000000000000000Agent \
 --wallet-key welldone \
 --wallet-name issuerWallet \
 --genesis-url http://10.2.0.9/genesis \
 --inbound-transport http 0.0.0.0 8000 \
 --outbound-transport http \
 --endpoint http://10.2.0.9:8000 \
 --admin 0.0.0.0 8080 \
 --admin-insecure-mode \
 --connections-invite \
 --auto-provision \
 --auto-accept-requests \
 --auto-respond-credential-request \
 --auto-respond-presentation-request \
 --preserve-exchange-records \
 --label Issuer.Agent
