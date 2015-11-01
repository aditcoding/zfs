#!/bin/bash

# This is where you have cloned out the https://github.com/grpc/grpc repository
# And built gRPC Python.
# ADJUST THIS PATH TO WHERE YOUR ACTUAL LOCATION IS
GRPC_ROOT=~/Projects/grpcPython/grpc

$GRPC_ROOT/python2.7_virtual_environment/bin/python zfs_server.py

