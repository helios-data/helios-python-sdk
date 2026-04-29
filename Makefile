.PHONY: build deps run clean proto test

# Variables
PROTO_SOURCE_DIR=helios-protos
PROTO_BUILD_DIR=src/helios/generated

# Find all .proto files in the proto directory and subdirectories
PROTO_SRC := $(shell find $(PROTO_SOURCE_DIR) -name "*.proto")
BETTER_PROTO_PLUGIN=$(shell find .venv -name protoc-gen-python_betterproto2\*)

MKDIR = mkdir -p $(1)
RM = rm -rf $(1)
SEPARATOR = /

# Commands
clean-protos:
	$(call RM,$(PROTO_BUILD_DIR))

protos:
	$(call MKDIR,$(PROTO_BUILD_DIR))

	protoc \
	--plugin=protoc-gen-python_betterproto2=$(BETTER_PROTO_PLUGIN) \
	-I=$(PROTO_SOURCE_DIR) \
	--python_betterproto2_out=$(PROTO_BUILD_DIR) \
	$(PROTO_SRC)
