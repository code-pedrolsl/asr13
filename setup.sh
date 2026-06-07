#!/bin/bash
# Roda uma vez em cada máquina após clonar o repositório

pip install grpcio grpcio-tools

# Gera os arquivos gRPC a partir dos .proto
python3 -m grpc_tools.protoc -I proto --python_out=. --grpc_python_out=. proto/scoreboard.proto
python3 -m grpc_tools.protoc -I proto --python_out=. --grpc_python_out=. proto/coordinator.proto

# Copia para as subpastas que precisam importar
cp scoreboard_pb2*.py   server/
cp scoreboard_pb2*.py   coordinator/
cp scoreboard_pb2*.py   client/
cp scoreboard_pb2*.py   tests/

cp coordinator_pb2*.py  coordinator/
cp coordinator_pb2*.py  client/
cp coordinator_pb2*.py  tests/

echo "Setup concluído!"
