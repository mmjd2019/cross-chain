#!/bin/bash
# Holder ACA-Py - 纯 HTTP 传输模式
# 用于与 Verifier 进行 HTTP 通信

docker run -d --rm \
 --network host \
 --name holder-acapy \
 -p 8081:8081 \
 -p 8001:8001 \
 -v ~/go/src/github.com/hyperledger/Indy/aca-py-wallet-holder:/home/aries/.acapy_agent/wallet \
 bcgovimages/aries-cloudagent:py3.12_1.2.0 \
 start \
 --wallet-type askar \
 --wallet-storage-type sqlite \
 --seed 000000000000000000000000001Agent \
 --wallet-key welldone \
 --wallet-name holderWallet \
 --genesis-url http://10.2.0.9/genesis \
 --inbound-transport http 0.0.0.0 8001 \
 --outbound-transport http \
 --endpoint http://10.2.0.9:8001 \
 --admin 0.0.0.0 8081 \
 --admin-insecure-mode \
 --connections-invite \
 --auto-provision \
 --auto-respond-credential-offer \
 --auto-respond-presentation-request \
 --auto-accept-invites \
 --auto-accept-requests \
 --preserve-exchange-records \
 --label Holder.Agent
