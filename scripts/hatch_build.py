import os
import sys
import subprocess
from pathlib import Path
from hatchling.builders.hooks.plugin.interface import BuildHookInterface

class CustomBuildHook(BuildHookInterface):
    def initialize(self, version, build_data):
        project_root = Path(self.root)
        proto_source_dir = project_root / "helios-protos"
        proto_build_dir = project_root / "src" / "helios" / "generated"

        proto_build_dir.mkdir(parents=True, exist_ok=True)

        proto_files = [str(p) for p in proto_source_dir.rglob("*.proto")]
        if not proto_files:
            print(f"!!! Warning: No proto files found in {proto_source_dir}")
            return

        # locate the plugin in the current environment
        python_bin_dir = Path(sys.executable).parent
        
        plugin_candidates = list(python_bin_dir.glob("protoc-gen-python_betterproto2*"))
        
        if not plugin_candidates:
            raise RuntimeError(
                f"Could not find 'protoc-gen-python_betterproto2' in {python_bin_dir}. "
                "Ensure 'betterproto2-compiler' is in build-system.requires."
            )
        
        plugin_path = plugin_candidates[0]

        command = [
            sys.executable, "-m", "grpc_tools.protoc",
            f"--plugin=protoc-gen-python_betterproto2={plugin_path}",
            f"-I={proto_source_dir}",
            f"--python_betterproto2_out={proto_build_dir}",
            *proto_files
        ]

        print(f"--- Running Protobuf Generation ---")
        result = subprocess.run(command, capture_output=True, text=True)

        if result.returncode != 0:
            print("STDOUT:", result.stdout)
            print("STDERR:", result.stderr)
            raise RuntimeError(f"Protoc failed (exit {result.returncode})")
        
        print(f"--- Successfully generated {len(proto_files)} files ---")