#!/usr/bin/env python3

# Build Script

import argparse
import gzip
import os
import pathlib
import shutil
import subprocess
import sys
import pwd
import grp


# ANSI color codes for terminal messages
GREEN = "\033[32m"
ORANGE = "\033[38;5;214m"
RED = "\033[31m"
RESET = "\033[0m"

# *** Global variables
current_error_level = 20


def main():
    args = parse_arguments()

    display_message(0, f"Building Package for {args.package_description}...")

    # Setup variables
    deb_package_path = f"{args.output}/pool/main"
    debian_package_file = f"{deb_package_path}/{args.filename}"
    stable_path = f"{args.output}/dists/stable"
    main_path = f"{stable_path}/main"
    gpg_key = args.gpg_key or os.getenv("GPG_KEY")
    binary_directories = ["binary-amd64", "binary-arm64"]

    # Create needed directories
    os.makedirs(deb_package_path, exist_ok=True)
    os.makedirs(main_path, exist_ok=True)

    for binary_directory in binary_directories:
        os.makedirs(f"{main_path}/{binary_directory}", exist_ok=True)

    if args.build:
        build_debian_package(debian_package_file)

    build_translation_file(stable_path)
    build_packages_files(main_path, binary_directories, debian_package_file)
    build_release(stable_path, gpg_key)

    if not args.install:
        display_message(0, f"Package {args.package_description} built successfully.")
        sys.exit(0)

    if not args.auto_install:
        user_input = input(
                "Do you wish to install the package [y/N]: ").strip().lower()

        if user_input != "y":
            display_message(0, f"Package {args.package_description} built successfully.")
            sys.exit(0)

    if args.copy:
        shutil.copytree(args.output_directory, args.distribution_directory)
        change_ownership_recursive(args.distribution_directory, "www-data", "www-data")

    display_message(0, f"Package {args.package_description} built successfully.")


def parse_arguments():
    """
    Parses command-line arguments.

    Returns:
        Dict: The parsed arguments.
    """
    script_path = pathlib.Path(__file__).resolve()
    parent_directory = script_path.parent.parent
    output_directory = parent_directory / "output"
    parser = argparse.ArgumentParser(description="Package build and deployment script.")

    parser.add_argument("-d", "--distribution_directory",
                        help="Specify the distribution path",
                        default="/var/www/html/distributions/debian")
    parser.add_argument("-g", "--gpg_key", help="Specify the gpg key for signing",
                        default=os.getenv("GPG_KEY"))
    parser.add_argument("-n", "--no-build", help="Don't build the package",
                        action="store_false", dest="build", default=True)
    parser.add_argument("-N", "--no-install", help="Don't install the package",
                        action="store_false", dest="install", default=True)
    parser.add_argument("-o", "--output_directory", help="Specify the output directory",
                        default=output_directory)
    parser.add_argument("-p", "--package-description",
                        help="Specify the package description",
                        default="Jump Start Website")
    parser.add_argument("-s", "--skip-copy", help="Don't copy the package",
                        action="store_false", dest="copy", default=True)
    parser.add_argument("-v", "--version",
                        help="Specify the package version", default="1.0.1")
    parser.add_argument("-y", "--yes",
                        help="Automatically install the package without asking",
                        action="store_true", dest="auto_install", default=False)

    args = parser.parse_args()

    if not args.filename:
        args.filename = f"{args.package}-{args.version}.deb"

    return args


def build_debian_package(debian_package_path):
    """
    Build the Debian package.

    Args:
        debian_package_path (str): Path to the debian package.
    """
    display_message(0, f"Building {debian_package_path}...")

    if os.path.isfile(debian_package_path):
        try:
            os.remove(debian_package_path)
            display_message(0, f"Removed existing package: {debian_package_path}")
        except Exception as e:
            display_message(get_current_error_level(),
                            f"Cannot remove existing package {debian_package_path}. {str(e)}")

    increment_error_level()

    result = run_command(f"dpkg-deb --build distribution {debian_package_path}", True, False)

    if result != 0:
        display_message(get_current_error_level(), "Build failed.")
    else:
        display_message(0, f"Package {debian_package_path} built successfully.")

    increment_error_level()


def build_translation_file(stable_path):
    """
    Build the Translation file.

    Args:
        stable_path (str): Path to the stable directory.
    """
    cwd = os.getcwd()
    translation_directory = "i18n"
    translation_filename = "Translation-en"
    translation_gz_filename = "Translation-en.gz"

    os.chdir(stable_path)
    os.makedirs(translation_directory, exist_ok=True)
    os.chdir(translation_directory)

    display_message(0, f"Creating {translation_filename}...")
    open(translation_filename, "w").close()

    if os.path.isfile(translation_filename):
        display_message(0, f"{translation_filename} built successfully.")
    else:
        display_message(get_current_error_level(), f"Cannot create {translation_filename}.")

    increment_error_level()
    display_message(0, f"GZipping {translation_filename} to {translation_gz_filename}...")
    gzip_file(translation_filename, translation_gz_filename)
    os.remove(translation_filename)
    display_message(0, f"GZipped {translation_filename} to  {translation_gz_filename} successfully.")
    os.chdir(cwd)


# noinspection PyBroadException
def build_packages_files(main_path, binary_directories, deb_file_path):
    """
    Build the Packages files.

    Args:
        main_path (str): Path to the main dir at output/dists/stable/main.
        binary_directories (list): Names of the binary package directories.
        deb_file_path (str): relative path to the Debian package.
    """
    for binary_directory in binary_directories:
        cwd = os.getcwd()
        binary_path = f"{main_path}/{binary_directory}"

        os.chdir(binary_path)

        display_message(0, f"Building Package in {binary_path}...")

        package_contents = run_command(f"dpkg-scanpackages {main_path} /dev/null", True, True)

        if not package_contents.strip():
            display_message(get_current_error_level(), "dpkg-scanpackage produced no output.")

        increment_error_level()

        output = []
        package_contents = package_contents.split("\n")

        for line in package_contents:
            if line.startswith("Filename:"):
                line = f"Filename: {deb_file_path}"

            output.append(line)

        package_file = "Packages"
        package_gz_file = "Packages.gz"

        try:
            with open(package_file, "w") as file:
                for line in output:
                    file.write(line)
        except Exception as e:
            display_message(get_current_error_level(), f"Can't write to {package_file}. Error: {e}")

        increment_error_level()

        display_message(0, f"{package_file} built successfully.")
        display_message(0, f"GZipping {package_file} to {package_gz_file}...")
        gzip_file(package_file, package_gz_file)
        display_message(0, f"{package_file} gzipped to {package_gz_file} successfully.")
        os.chdir(cwd)


def build_release(stable_path, gpg_key):
    """
    Build the Release, Release.gpg, and InRelease files.

    Args:
        stable_path (str): The path to the stable directory.
        gpg_key (str): The GnuPG key.
    """
    cwd = os.getcwd()

    os.chdir(stable_path)
    display_message(0, f"Building Release...")

    release_output = run_command("apt-ftparchive release .", True, True)

    if not release_output.strip():
        display_message(get_current_error_level(), f"apt-ftparchive produced no output.")

    increment_error_level()

    codename_exists = "Codename" in release_output
    suite_exists = "Suite" in release_output
    release_output = release_output.split("\n")

    if not suite_exists or codename_exists:
        output = []

        if not suite_exists:
            output.append("Suite: stable\n")

        if not codename_exists:
            output.append("Codename: stable\n")

        for line in release_output:
            output.append(line)

        release_output = output

    try:
        with open("Release", "w") as file:
            for line in release_output:
                file.write(line)
    except Exception as e:
        display_message(get_current_error_level(), f"Cannot write Release: {str(e)}.")

    increment_error_level()

    display_message(0, f"Created Release.")

    if not gpg_key:
        display_message(get_current_error_level(), f"No GPG key can't sign Release.")

    increment_error_level()

    display_message(0, f"Signing Release...")
    # Run GPG to sign the Release file and create InRelease
    run_command(f"gpg -u {gpg_key} --clearsign -o InRelease Release", True, False)
    run_command(f"gpg -u {gpg_key} --detach-sign -o Release.gpg Release", True, False)
    display_message(0, "Successfully signed Release file.")
    os.chdir(cwd)


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


def run_command(command, flag_error=True, capture_output=True, timeout=None, as_user=None):
    """
    Execute a shell command and return the output.

    Args:
        command (str|list): The command to run.
        capture_output (bool): Capture the output.
        flag_error (bool): Flag whether to exit with an error.
        timeout (float|None): Optional timeout for command execution.
        as_user (str|None): User to run the command as.

    Returns:
        A string or a boolean based on capture_output.
    """
    if isinstance(command, list):
        command_str = " ".join(command)
    else:
        command_str = command

    if as_user:
        command_str = f"su - {as_user} -c '{command_str}'"

    try:
        result = subprocess.run(
                command_str,
                timeout=timeout,
                shell=True,
                capture_output=True,
                text=True,
                env=os.environ
        )

        if result.returncode != 0:
            if flag_error:
                display_message(89, f"Command '{command_str}' failed with exit code {result.returncode}.")
                display_message(89, f"Error: {result.stderr}")
            return "" if capture_output else False

        return result.stdout if capture_output else True

    except subprocess.TimeoutExpired:
        return "" if capture_output else False
    except subprocess.CalledProcessError as e:
        display_message(90, f"Error: Error running {command_str}. Error: {str(e)}")
        return "" if capture_output else False


# noinspection PyTypeChecker
def gzip_file(source_filename, destination_filename):
    """
    Compresses a file using GNU Zip (gzip).
    Args:
        source_filename (str): The file to compress.
        destination_filename (str): The compress filename.
    """
    try:
        with open(source_filename, "rb") as f_in, gzip.open(destination_filename, "wb") as f_out:
            shutil.copyfileobj(f_in, f_out)
    except Exception as e:
        display_message(get_current_error_level(),
                        f"Error: Failed to compress {source_filename}. {str(e)}")
    increment_error_level()


def change_ownership_recursive(path, user, group):
    """
    Recursively change owner and group of a directory and its contents.
    Args:
        path (str): Path to the directory to change.
        user (str): The owner of the directory to change.
        group (str): The group of the directory to change.
    """
    display_message(0, f"Recursively changing owner to {user} for {path}...")

    # Get user and group IDs
    uid = pwd.getpwnam(user).pw_uid
    gid = grp.getgrnam(group).gr_gid

    # Change ownership of the root directory
    os.chown(path, uid, gid)

    # Walk through all files and subdirectories
    for root, dirs, files in os.walk(path):
        for d in dirs:
            os.chown(os.path.join(root, d), uid, gid)
        for f in files:
            os.chown(os.path.join(root, f), uid, gid)

    display_message(0, f"Recursively changed owner to {user} for {path}.")


if __name__ == "__main__":
    main()
