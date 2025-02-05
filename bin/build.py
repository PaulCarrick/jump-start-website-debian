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
from datetime import datetime, timezone
from pathlib import Path


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


def get_current_error_level():
    return current_error_level


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


def gzip_file(source_file, debian_package_file):
    """
    Compresses a file using GNU Zip (gzip).
    Args:
        source_file (str): The file to compress.
        debian_package_file (str): The compress filename.
    """
    try:
        with open(source_file, "rb") as f_in, gzip.open(debian_package_file,
                                                        "wb") as f_out:
            shutil.copyfileobj(f_in, f_out)
    except Exception as e:
        display_message(get_current_error_level(),
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
        display_message(get_current_error_level(),
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
        display_message(get_current_error_level(),
                        f"Error: Failed to compute checksum for {filename}. {str(e)}")

    increment_error_level()
    return result


def setup_variables_for_file(filename, variables):
    """
    Computes all the checksums and gets the file size for a given file.
    Args:
        filename (str): The file compute the checksum and get the size for.
        variables (dict): The dict to store the results in.
    """
    checksum_types = ["MD5Sum", "SHA1", "SHA256", "SHA512"]

    if not os.path.isfile(filename):
        display_message(get_current_error_level(),
                        f"Error: File '{filename}' not found!")
        return

    increment_error_level()

    try:
        file_size = os.path.getsize(filename)
    except Exception as e:
        display_message(get_current_error_level(),
                        f"Error: Cannot get file size of {filename}. {str(e)}")
        return

    increment_error_level()

    file_path = Path(filename)
    basename = file_path.name

    variables[basename] = {"checksums": {}, "file_size": file_size}

    for checksum_type in checksum_types:
        checksum = compute_checksum(filename, checksum_type)

        if checksum:
            variables[basename]["checksums"][checksum_type] = checksum


def setup_variables_for_files(file_names, variables):
    """
    Computes all the checksums and gets file size for a set of files.
    Args:
        file_names (list[str]): The files to compute the checksums and get the sizes for.
        variables (dict): The dict to store the results in.
    """
    for file in file_names:
        setup_variables_for_file(file, variables)


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
                    display_message(get_current_error_level(),
                                    f"Error processing line: {line.strip()} -> {e}")
    except FileNotFoundError:
        display_message(get_current_error_level(),
                        f"Error: Template file '{template_filename}' not found!")

    increment_error_level(2)


def parse_arguments():
    """
    Parses command-line arguments.

    Returns:
        Dict: The parsed arguments.
    """
    script_path = pathlib.Path(__file__).resolve()
    parent_directory = script_path.parent.parent
    template_directory = parent_directory / "templates"
    output_directory = parent_directory / "output"
    parser = argparse.ArgumentParser(
            description="Package build and deployment script.")

    parser.add_argument("-d", "--dir",
                        help="Specify the distribution directory",
                        default="/var/www/html/distributions/debian")
    parser.add_argument("-f", "--filename", help="Specify the package filename")
    parser.add_argument("-g", "--gpg_key", help="Specify the gpg key for signing",
                        default=os.getenv("GPG_KEY"))
    parser.add_argument("-n", "--no-build", help="Don't build the package",
                        action="store_false", dest="build", default=True)
    parser.add_argument("-N", "--no-install", help="Don't install the package",
                        action="store_false", dest="install", default=True)
    parser.add_argument("-o", "--output", help="Specify the output directory",
                        default=output_directory)
    parser.add_argument("-p", "--package",
                        help="Specify the package name",
                        default="jump-start-website")
    parser.add_argument("-P", "--package-description",
                        help="Specify the package description",
                        default="Jump Start Website")
    parser.add_argument("-s", "--skip-copy", help="Don't copy the package",
                        action="store_false", dest="copy", default=True)
    parser.add_argument("-t", "--templates",
                        help="Specify the templates directory",
                        default=template_directory)
    parser.add_argument("-v", "--version",
                        help="Specify the package version", default="1.0.0")
    parser.add_argument("-y", "--yes",
                        help="Automatically install the package without asking",
                        action="store_true", dest="auto_install", default=False)

    args = parser.parse_args()

    if not args.filename:
        args.filename = f"{args.package}-{args.version}.deb"

    return args


def build_debian_package(debian_package_file):
    """
    Build the Debian package.

    Args:
        debian_package_file (str): Path to the output file.
    """
    display_message(0,
                    f"Building {debian_package_file}...")

    if os.path.isfile(debian_package_file):
        try:
            os.remove(debian_package_file)
            display_message(0, f"Removed existing package: {debian_package_file}")
        except Exception as e:
            display_message(get_current_error_level(),
                            f"Cannot remove existing package {debian_package_file}. {str(e)}")

    increment_error_level()

    result = subprocess.run(["dpkg-deb",
                             "--build",
                             "distribution",
                             debian_package_file
                             ],
                            capture_output=True,
                            text=True)

    if result.returncode != 0:
        display_message(get_current_error_level(),
                        f"Build failed: {result.stderr}")
    else:
        display_message(0,
                        f"Package {debian_package_file} built successfully.")

    increment_error_level()


def build_package_file(packages_template, packages_file, packages_gz_file, debian_package_file,
                       variables):
    """
    Build the Packages files.

    Args:
        packages_template (str): Path to the Packages template file.
        packages_file (str): Path to the Packages file.
        packages_gz_file (str): Path to the Packages.gz file.
        debian_package_file (str): Path to the Debian package file.
        variables (dict): The dict to store the file information in.
    """
    display_message(0,
                    f"Building {packages_file}...")
    setup_variables_for_file(debian_package_file, variables)
    process_template(packages_template, packages_file, variables)

    if os.path.isfile(packages_file):
        display_message(0,
                        f"{packages_file} built successfully.")
        display_message(0,
                        f"Building {packages_gz_file}...")
        gzip_file(packages_file, packages_gz_file)
        display_message(0,
                        f"{packages_gz_file} built successfully.")
    else:
        display_message(get_current_error_level(), f"Could not create {packages_file}!")

    increment_error_level()


def build_translation_file(translation_file, translation_gz_file):
    """
    Build the Translation file.

    Args:
        translation_file (str): Path to the Translation file.
        translation_gz_file (str): Path to the Translation.gz file.
    """
    display_message(0,
                    f"Creating {translation_gz_file}...")
    open(translation_file, "w").close()

    if os.path.isfile(translation_file):
        display_message(0,
                        f"{translation_file} built successfully.")
        display_message(0,
                        f"Building {translation_gz_file}...")
        gzip_file(translation_file, translation_gz_file)
        os.remove(translation_file)
        display_message(0,
                        f"{translation_gz_file} built successfully.")
    else:
        display_message(get_current_error_level(), f"Could not create {translation_gz_file}!")

    increment_error_level()


def build_release_file(release_template, release_file, inrelease_file, files,
                       gpg_key, variables):
    """
    Build the Release and InRelease files.

    Args:
        release_template (str): Path to the Release template file.
        release_file (str): Path to the Release file.
        inrelease_file (str): Path to the InRelease file.
        files (list[str]): The files in the release.
        gpg_key (str): The GnuPG key.
        variables (dict): The dict to store the file information in.
    """
    display_message(0,
                    f"Building {release_file}...")
    setup_variables_for_files(files, variables)
    process_template(release_template, release_file, variables)
    increment_error_level()
    display_message(0,
                    f"{release_file} built successfully.")

    if not gpg_key:
        display_message(get_current_error_level(),
                        f"No GPG key can't sign {release_file}.")

    try:
        display_message(0,
                        f"Signing {release_file}...")
        # Run GPG to sign the Release file and create InRelease
        subprocess.run(["gpg", "--default-key", gpg_key, "--clearsign", "-o",
                        inrelease_file, release_file],
                       check=True)
        display_message(0,
                        f"Successfully signed {release_file} into {inrelease_file}")
    except subprocess.CalledProcessError as e:
        display_message(get_current_error_level(),
                        f"Error signing Release file: {e}")

    increment_error_level()


def copy_files(source_dir, destination_dir, debian_package, packages,
               packages_gz, release, inrelease):
    """
    Copy the files to the distribution directory.

    This function requires sudo access to process the files because it copies the filed into the website.
    It's best to run this as a normal user and enter the sudo password (if needed).
    You could run the entrie script as sudo but that will affect the files created in the output directory.

    Args:
        source_dir (str): Path to the source directory (the output directory).
        destination_dir (str): Path to the destination directory (the distribution directory).
        debian_package (str): Path to the Debian package.
        packages (str): Path to the Packages file.
        packages_gz (str): Path to the Packages.gz file.
        release (str): Path to the Release file.
        inrelease (str): Path to the InRelease file.
    """
    display_message(0,
                    f"Copying files in {source_dir} to {destination_dir}...")

    result = subprocess.run(["sudo",
                             "cp",
                             "-r",
                             debian_package,
                             packages,
                             packages_gz,
                             release,
                             inrelease,
                             f"{source_dir}/i18n",
                             destination_dir
                             ],
                            capture_output=True,
                            text=True)

    if result.returncode != 0:
        display_message(get_current_error_level(),
                        f"Copy failed: {result.stderr}")
    else:
        display_message(0,
                        f"Copied files from {source_dir} to {destination_dir} built successfully.")

    increment_error_level()
    display_message(0, f"Changing ownership files in of {destination_dir} to www-data...")

    # Change permissions of debian file
    result = subprocess.run(["sudo",
                             "chmod",
                             "0444",
                             f"{destination_dir}/{debian_package}"
                             ],
                            capture_output=True,
                            text=True)

    if result.returncode != 0:
        display_message(get_current_error_level(),
                        f"Change permissions failed: {result.stderr}")
    else:
        display_message(0,
                        f"Changed permissions of {debian_package} to 0444.")

    increment_error_level()

    # Change ownership of files to www-data
    result = subprocess.run(["sudo",
                             "chown",
                             "-R",
                             "www-data:www-data",
                             destination_dir
                             ],
                            capture_output=True,
                            text=True)

    if result.returncode != 0:
        display_message(get_current_error_level(),
                        f"Change ownership failed: {result.stderr}")
    else:
        display_message(0,
                        f"Changed ownership in {destination_dir} to www-data.")

    increment_error_level()

    if result.returncode != 0:
        display_message(get_current_error_level(),
                        f"Change ownership failed: {result.stderr}")
    else:
        display_message(0,
                        f"Changed ownership in {destination_dir} to www-data.")

    increment_error_level()


def main():
    args = parse_arguments()

    display_message(0, f"Building Package for {args.package_description}...")

    packages_template = f"{args.templates}/Packages"
    packages_file = f"{args.output}/Packages"
    packages_gz_file = f"{args.output}/Packages.gz"
    release_template = f"{args.templates}/Release"
    release_file = f"{args.output}/Release"
    inrelease_file = f"{args.output}/InRelease"
    translation_file = f"{args.output}/i18n/Translation-en"
    translation_gz_file = f"{args.output}/i18n/Translation-en.gz"
    gpg_key = args.gpg_key or os.getenv("GPG_KEY")
    current_time = datetime.now(timezone.utc)
    build_date = current_time.strftime("%a, %d %b %Y %H:%M:%S %z")
    debian_package_file = args.output / args.filename

    variables = {
            "build_date":          build_date,
            "package_description": args.package_description,
            "package_name":        args.package,
            "version":             args.version,
            "filename":            args.filename,
    }

    if args.build:
        build_debian_package(debian_package_file)

    build_package_file(packages_template, packages_file, packages_gz_file, debian_package_file,
                       variables)
    build_translation_file(translation_file, translation_gz_file)
    build_release_file(release_template, release_file, inrelease_file,
                       [packages_file, packages_gz_file, translation_gz_file],
                       gpg_key, variables)

    if not args.install:
        display_message(0, f"Package {args.package_description} built successfully.")
        sys.exit(0)

    if not args.auto_install:
        user_input = input(
                "Do you wish to install the package [y/N]: ").strip().lower()

        if user_input != "y":
            display_message(0,
                            f"Package {args.package_description} built successfully.")
            sys.exit(0)

    if args.copy:
        copy_files(args.output, args.dir, debian_package_file, packages_file,
                   packages_gz_file, release_file, inrelease_file)

    display_message(0,
                    f"Package {args.package_description} built successfully.")


if __name__ == "__main__":
    main()
