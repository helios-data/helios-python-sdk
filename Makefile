.PHONY: build deps run clean proto test

# Variables
PROTO_SOURCE_DIR=helios-protos
PROTO_BUILD_DIR=generated

# Find all .proto files in the proto directory and subdirectories
PROTO_SRC := $(shell find $(PROTO_SOURCE_DIR) -name "*.proto")

MKDIR = mkdir -p $(1)
RM = rm -rf
SEPARATOR = /

# Commands
proto:
	$(call MKDIR,$(PROTO_BUILD_DIR))

	protoc \
	--plugin=protoc-gen-python_betterproto=.venv/bin/protoc-gen-python_betterproto \
	-I=$(PROTO_SOURCE_DIR) \
	--python_betterproto_out=$(PROTO_BUILD_DIR) \
	$(PROTO_SRC)
