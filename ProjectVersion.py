#!/usr/bin/env python

# --------------------------------------------------------------------------------------------------
#
# Imports.
#
# --------------------------------------------------------------------------------------------------
import argparse
import os
import sys
from dataclasses import dataclass
from typing import List


# --------------------------------------------------------------------------------------------------
#
# Global variables.
#
# --------------------------------------------------------------------------------------------------
@dataclass
class Version:
    """
    Class to represent a version.
    """

    def __init__(self, version: str):
        version_parts = version.split(".")
        if len(version_parts) == 0:
            raise ValueError("Version string is empty!")

        self.major = 0
        self.minor = 0
        self.patch = 0
        self.dev = 0

        if len(version_parts) >= 1:
            self.major = int(version_parts[0])

        if len(version_parts) >= 2:
            self.minor = int(version_parts[1])

        if len(version_parts) >= 3:
            self.patch = int(version_parts[2])

        if len(version_parts) == 4:
            dev_part = version_parts[3]
            if dev_part.startswith("dev"):
                self.dev = int(dev_part.replace("dev", ""))
            else:
                raise ValueError("Development version must be in the format 'devN'")

    def __str__(self) -> str:
        version = f"{self.major}.{self.minor}.{self.patch}"

        if self.dev > 0:
            version += f".dev{self.dev}"

        return version

    def increment(self, version_part: str):
        """
        Increment the specified version part.
        """

        if version_part == "MAJOR":
            self.major += 1
            self.minor = 0
            self.patch = 0
            self.dev = 0
        elif version_part == "MINOR":
            self.minor += 1
            self.patch = 0
            self.dev = 0
        elif version_part == "PATCH":
            self.patch += 1
            self.dev = 0
        elif version_part == "DEV":
            self.dev += 1
        else:
            raise ValueError(f"Unknown version part: {version_part}!")


# --------------------------------------------------------------------------------------------------
#
# Class definition.
#
# --------------------------------------------------------------------------------------------------
class VersionFileIO:
    """
    Class to manage the project version.
    """

    def __init__(self):
        """
        Initialize the ProjectVersion class.
        """
        self.__current_working_directory = os.getcwd()
        self.__version_filepath = os.path.join(
            self.__current_working_directory, "setup.cfg"
        )

    def increment_and_write(self, version_part: str):
        """
        Increment the specified version part.
        """
        if version_part == "NONE":
            sys.exit(0)

        version = Version(self.read())
        version.increment(version_part)

        version_file_lines: List[str] = []
        with open(
            file=self.__version_filepath, mode="r", encoding="utf-8"
        ) as version_file:
            version_file_lines = version_file.readlines()

        for line_index, line in enumerate(version_file_lines):
            if line.startswith("version = "):
                version_file_lines[line_index] = f"version = {str(version)}\n"

        with open(
            file=self.__version_filepath, mode="w", encoding="utf-8"
        ) as version_file:
            version_file.writelines(version_file_lines)

    def read(self) -> str:
        """
        Get the current project version.
        """
        version_file_lines: List[str] = []
        with open(
            file=self.__version_filepath, mode="r", encoding="utf-8"
        ) as version_file:
            version_file_lines = version_file.readlines()

        version = ""

        for _, line in enumerate(version_file_lines):
            if line.startswith("version = "):
                version = line.replace("version = ", "").strip()
                break

        return version


# --------------------------------------------------------------------------------------------------
#
# Entry point.
#
# --------------------------------------------------------------------------------------------------
if __name__ == "__main__":
    parser = argparse.ArgumentParser()

    parser.add_argument(
        dest="action",
        type=str,
        nargs="?",
        choices=[
            "NONE",
            "INCREMENT_VERSION",
            "GET_VERSION",
        ],
        default="NONE",
        const="NONE",
    )

    parser.add_argument(
        dest="version_part",
        type=str,
        nargs="?",
        choices=[
            "NONE",
            "MAJOR",
            "MINOR",
            "PATCH",
            "DEV",
        ],
        default="NONE",
        const="NONE",
    )

    args = parser.parse_args()

    if args.action == "NONE":
        sys.exit(0)

    elif args.action == "INCREMENT_VERSION":
        VersionFileIO().increment_and_write(args.version_part)

    elif args.action == "GET_VERSION":
        print(VersionFileIO().read())
