"""
Build script for helios-python-sdk.
Automatically generates protobuf files during installation.
"""

import os
import subprocess
import sys
from pathlib import Path

from setuptools import setup
from setuptools.command.build_py import build_py


class BuildPyWithProtos(build_py):
    """Custom build_py command that generates protobuf files first."""

    def run(self):
        """Generate protos before building Python files."""
        self.generate_protos()
        super().run()

    def generate_protos(self):
        """Generate Python protobuf files from .proto sources."""
        proto_src_dir = Path("helios-protos")
        proto_build_dir = Path("src/generated")

        # Skip if no proto files exist
        proto_files = list(proto_src_dir.glob("**/*.proto"))
        if not proto_files:
            print(f"No .proto files found in {proto_src_dir}, skipping generation")
            return

        print(f"Generating protobuf files from {proto_src_dir}...")

        # Create output directory
        proto_build_dir.mkdir(parents=True, exist_ok=True)

        try:
            # Run protoc
            subprocess.run(
                [
                    "protoc",
                    f"--plugin=protoc-gen-python_betterproto2=protoc-gen-python_betterproto2",
                    f"-I={proto_src_dir}",
                    f"--python_betterproto2_out={proto_build_dir}",
                    *[str(f) for f in proto_files],
                ],
                check=True,
            )
            print(f"✓ Protobuf files generated to {proto_build_dir}")
        except subprocess.CalledProcessError as e:
            print(f"✗ Failed to generate protobuf files: {e}", file=sys.stderr)
            print(
                "Make sure protoc is installed: apt-get install protobuf-compiler",
                file=sys.stderr,
            )
            raise
        except FileNotFoundError:
            print(
                "✗ protoc not found. Install protobuf-compiler:",
                file=sys.stderr,
            )
            print("  apt-get install protobuf-compiler  (Linux)", file=sys.stderr)
            print("  brew install protobuf              (macOS)", file=sys.stderr)
            raise


if __name__ == "__main__":
    setup(cmdclass={"build_py": BuildPyWithProtos})
