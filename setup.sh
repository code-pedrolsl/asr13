#!/bin/bash
pip install grpcio grpcio-tools

python3 -m grpc_tools.protoc -I proto --python_out=. --grpc_python_out=. proto/scoreboard.proto
python3 -m grpc_tools.protoc -I proto --python_out=. --grpc_python_out=. proto/coordinator.proto

cp scoreboard_pb2*.py   server/
cp scoreboard_pb2*.py   coordinator/
cp scoreboard_pb2*.py   client/
cp scoreboard_pb2*.py   tests/

cp coordinator_pb2*.py  coordinator/
cp coordinator_pb2*.py  client/
cp coordinator_pb2*.py  tests/

echo "Setup concluído!"
