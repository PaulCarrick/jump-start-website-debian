#!/usr/bin/env python3

# Build Script

import argparse
import gzip
import hashlib
import os
import pathlib
import shutil
import subprocess
import sys

# ANSI color codes for terminal messages
GREEN = "\033[32m"
ORANGE = "\033[38;5;214m"
RED = "\033[31m"
RESET = "\033[0m"

# *** Global variables

# current_error_level contains the current error level so that each error
# produces a unique exit code that can be traced back to the code.
# This prevents having to change each error result as the code is changed.
# It starts as 20 because display error considers any error level above 19
# as a fatal error. It subtracts 19 so that the error exit starts at 1.
current_error_level = 20


def display_message(error_level, message):
    """
    Displays a message to the console with a given error level
     and optionally exit with a non-zero exit code if the error level
     is above 19.

    Args:
        error_level (int): The amount to increment the current_error_level.
        message (str): The message to display.

    error_level contains the current error level.
     display_message considers any error level above 19 as a fatal error.
     It subtracts 19 so that the error exit starts at 1.
    0-9 is not an error and displays in green.
    10-19 is a warning and displays in orange.
    > 19 is an error and display in red  then exits with an exit code
     of error_level - 19 (starts at 1 for 20).
    """
    if error_level < 10:
        print(f"{GREEN}{message}{RESET}")
    elif error_level < 20:
        print(f"{ORANGE}{message}{RESET}")
    else:
        print(f"{RED}{message}{RESET}", file=sys.stderr)
        sys.exit(error_level - 19)


def increment_error_level(increment=1):
    """
    Increments current_error_level level by given increment.

    Args:
        increment (int=1): The amount to increment the current_error_level.

    current_error_level contains the current error level so that each error
    produces a unique exit code that can be traced back to the code.
    This prevents having to change each error result as the code is changed.
    It starts as 20 because display error considers any error level above 19
    as a fatal error. It subtracts 19 so that the error exit starts at 1.
    """
    global current_error_level

    current_error_level += increment
    return current_error_level


def gzip_file(source_file, output_file):
    """
    Compresses a file using GNU Zip (gzip).
    Args:
        source_file (str): The file to compress.
        output_file (str): The compress filename.
    """
    try:
        with open(source_file, "rb") as f_in, gzip.open(output_file,
                                                        "wb") as f_out:
            shutil.copyfileobj(f_in, f_out)
    except Exception as e:
        display_message(current_error_level,
                        f"Error: Failed to compress {source_file}. {str(e)}")
    increment_error_level()


def compute_checksum(filename, checksum_type):
    """
    Computes the checksum for a given file.
    Args:
        filename (str): The file compute the checksum for.
        checksum_type (str): The type of checksum to compute.
            "MD5Sum"
            "SHA1"
            "SHA256"
            "SHA512"
    Returns:
        str: The checksum for the filename.
    """
    result = None
    hash_func_map = {
            "MD5Sum": hashlib.md5,
            "SHA1":   hashlib.sha1,
            "SHA256": hashlib.sha256,
            "SHA512": hashlib.sha512,
    }
    hash_func = hash_func_map.get(checksum_type)

    if not hash_func:
        display_message(current_error_level,
                        f"Error: Unknown checksum type '{checksum_type}'!")
        return None

    increment_error_level()

    try:
        with open(filename, "rb") as f:
            file_hash = hash_func()
            while chunk := f.read(8192):
                file_hash.update(chunk)

        result = file_hash.hexdigest()
    except Exception as e:
        display_message(current_error_level,
                        f"Error: Failed to compute checksum for {filename}. {str(e)}")

    increment_error_level()
    return result


def setup_variables_for_file(file, variables):
    """
    Computes all the checksums and gets file size for a given file.
    Args:
        file (str): The file compute the checksum and get the size for.
        variables (dict): The dict to store the results in.
    Returns:
        str: The checksum for the filename.
    """
    checksum_types = ["MD5Sum", "SHA1", "SHA256", "SHA512"]

    if not os.path.isfile(file):
        display_message(current_error_level, f"Error: File '{file}' not found!")
        return

    increment_error_level()

    try:
        file_size = os.path.getsize(file)
    except Exception as e:
        display_message(current_error_level,
                        f"Error: Cannot get file size of {file}. {str(e)}")
        return

    increment_error_level()

    variables[file] = {"checksums": {}, "file_size": file_size}

    for checksum_type in checksum_types:
        checksum = compute_checksum(file, checksum_type)
        if checksum:
            variables[file]["checksums"][checksum_type] = checksum


def process_template(template_filename, output_filename, variables):
    """
    Reads a template file, replaces placeholders using eval(),
    and writes the processed content to an output file.

    Args:
        template_filename (str): Path to the template file.
        output_filename (str): Path to the output file.
        variables (dict): Dictionary containing replacement variables.
    """
    try:
        with open(template_filename, "r") as infile, open(output_filename,
                                                          "w") as outfile:
            for line in infile:
                try:
                    processed_line = eval(f'f"""{line.strip()}"""', {},
                                          {"variables": variables})
                    outfile.write(processed_line + "\n")
                except Exception as e:
                    display_message(current_error_level,
                                    f"Error processing line: {line.strip()} -> {e}")
    except FileNotFoundError:
        display_message(current_error_level,
                        f"Error: Template file '{template_filename}' not found!")

    increment_error_level(2)


def parse_arguments():
    """
    Parses command-line arguments.

    Returns:
        Dict: The parsed arguments.
    """
    script_path = pathlib.Path(__file__).resolve()
    parent_directory = script_path.parent
    template_directory = parent_directory / "templates"
    output_directory = parent_directory / "output"
    parser = argparse.ArgumentParser(
            description="Package build and deployment script.")

    parser.add_argument("-p", "--package", required=True,
                        help="Specify the package name",
                        default="jump-start-website")
    parser.add_argument("-v", "--version", required=True,
                        help="Specify the package version", default="1.0.0")
    parser.add_argument("-f", "--filename", help="Specify the package filename")
    parser.add_argument("-d", "--dir",
                        help="Specify the distribution directory",
                        default="/var/www/html/distributions/debian")
    parser.add_argument("-o", "--output", help="Specify the output directory",
                        default=output_directory)
    parser.add_argument("-n", "--no-build", help="Don't build the package",
                        action="store_false", dest="build", default=True)
    parser.add_argument("-N", "--no-install", help="Don't install the package",
                        action="store_false", dest="install", default=True)
    parser.add_argument("-s", "--skip-copy", help="Don't copy the package",
                        action="store_false", dest="copy", default=True)
    parser.add_argument("-t", "--templates",
                        help="Specify the templates directory",
                        default=template_directory)
    parser.add_argument("-y", "--yes",
                        help="Automatically install the package without asking",
                        action="store_true", dest="auto_install", default=False)

    args = parser.parse_args()

    if not args.filename:
        args.filename = f"{args.package}-{args.version}.deb"

    return args


def main():
    args = parse_arguments()
    variables = {}

    if args.build:
        if os.path.isfile(args.package):
            try:
                os.remove(args.package)
                display_message(0, f"Removed existing package: {args.package}")
            except Exception as e:
                display_message(current_error_level,
                                f"Cannot remove existing package {args.package}. {str(e)}")

        increment_error_level()
        display_message(0, f"Building: {args.package}")

        result = subprocess.run(["dpkg-deb", "--build", "distribution"],
                                capture_output=True, text=True)

        if result.returncode != 0:
            display_message(current_error_level,
                            f"Build failed: {result.stderr}")

        increment_error_level()
        os.rename("distribution", args.package)

    process_template(f"{args.templates}/Packages",
                     f"{args.output}/Packages",
                     variables)

    if os.path.isfile(f"{args.output}/Packages"):
        gzip_file(f"{args.output}/Packages", f"{args.output}/Packages.gz")
    else:
        display_message(current_error_level, "Could not create Packages!")

    increment_error_level()

    process_template(f"{args.templates}/Release",
                     f"{args.output}/Release",
                     variables)

    if os.path.isfile(f"{args.output}/Release"):
        gzip_file(f"{args.output}/Release", f"{args.output}/Packages.gz")
    else:
        display_message(current_error_level, "Could not create Release!")

    increment_error_level()

    if not args.install:
        sys.exit(0)

    if not args.auto_install:
        user_input = input(
                "Do you wish to install the package [y/N]: ").strip().lower()
        if user_input != "y":
            sys.exit(0)

    if args.copy:
        try:
            shutil.copy(args.package, args.dir)
            display_message(0, f"Package {args.package} copied to {args.dir}")
        except Exception as e:
            display_message(current_error_level,
                            f"Cannot copy {args.package} to {args.dir}. {str(e)}")

    increment_error_level()


if __name__ == "__main__":
    main()
