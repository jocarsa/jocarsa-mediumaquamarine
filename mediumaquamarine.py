import paramiko
import os
import json
from datetime import datetime
import sys

PROGRESS_FILE = "progress.txt"
LOG_FILE = "backup_log.json"  # (Optional) log file for backup details

# List of folder names to exclude from the backup process
EXCLUDE_FOLDERS = [".git", "myphp","node_modules"]

def load_ftp_config(config_file):
    try:
        with open(config_file, 'r') as file:
            return json.load(file)
    except Exception as e:
        print(f"Failed to load config file: {e}")
        return None

def count_files_in_dir(local_dir):
    count = 0
    for root, dirs, files in os.walk(local_dir):
        # Filter out excluded directories
        dirs[:] = [d for d in dirs if d not in EXCLUDE_FOLDERS]
        count += len(files)
    return count

def update_progress(uploaded, total):
    percentage = (uploaded / total) * 100 if total else 100
    with open(PROGRESS_FILE, "w") as pf:
        pf.write(str(percentage))
    return percentage

def transfer_folders_to_sftp(config_file, remote_path):
    config = load_ftp_config(config_file)
    if not config:
        print("Invalid configuration. Aborting.")
        return

    hostname = config.get("hostname")
    port = config.get("port", 22)
    username = config.get("username")
    password = config.get("password")
    local_folders = config.get("folders", [])

    # Calculate total number of files to upload (for progress)
    total_files = 0
    for folder in local_folders:
        total_files += count_files_in_dir(folder)
    uploaded_files = 0

    try:
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        print(f"Connecting to {hostname}:{port}...")
        ssh.connect(hostname, port=port, username=username, password=password)
        print("Connection established.")

        sftp = ssh.open_sftp()

        # Create a timestamped folder in the remote path
        timestamp = datetime.now().strftime("%Y-%m-%d-%H-%M-%S")
        remote_timestamped_path = os.path.join(remote_path, timestamp)
        print(f"Creating remote directory: {remote_timestamped_path}...")
        try:
            sftp.mkdir(remote_path)
        except IOError:
            print(f"Remote base path '{remote_path}' already exists.")

        sftp.mkdir(remote_timestamped_path)
        print("Remote timestamped directory created.")

        # Recursively upload each folder
        def upload_dir(local_dir, remote_dir):
            nonlocal uploaded_files
            for item in os.listdir(local_dir):
                # Exclude folders that are in the exclusion list
                if item in EXCLUDE_FOLDERS:
                    print(f"Skipping excluded folder: {item}")
                    continue

                local_path = os.path.join(local_dir, item)
                remote_item_path = os.path.join(remote_dir, item)
                if os.path.isfile(local_path):
                    print(f"Uploading file {local_path} to {remote_item_path}...")
                    sftp.put(local_path, remote_item_path)
                    uploaded_files += 1
                    update_progress(uploaded_files, total_files)
                elif os.path.isdir(local_path):
                    print(f"Creating directory {remote_item_path}...")
                    try:
                        sftp.mkdir(remote_item_path)
                    except IOError:
                        print(f"Directory {remote_item_path} already exists.")
                    upload_dir(local_path, remote_item_path)

        # For each folder, create a subfolder and start uploading
        for local_folder in local_folders:
            folder_name = os.path.basename(os.path.normpath(local_folder))
            remote_folder_path = os.path.join(remote_timestamped_path, folder_name)
            print(f"Creating subfolder for {folder_name}: {remote_folder_path}...")
            try:
                sftp.mkdir(remote_folder_path)
            except IOError:
                print(f"Subfolder {remote_folder_path} already exists.")

            print(f"Transferring contents of {local_folder} to {remote_folder_path}...")
            upload_dir(local_folder, remote_folder_path)

        print("Transfer complete.")
        # Optionally log backup details (to be later read by PHP)
        backup_record = {
            "timestamp": timestamp,
            "total_files": total_files,
            "uploaded_files": uploaded_files,
            "remote_path": remote_timestamped_path
        }
        with open(LOG_FILE, "a") as lf:
            lf.write(json.dumps(backup_record) + "\n")

    except Exception as e:
        print(f"An error occurred: {e}")

    finally:
        try:
            sftp.close()
            ssh.close()
        except Exception:
            pass

if __name__ == "__main__":
    config_file = "ftp_config.json"
    remote_path = "copiasdeseguridad"
    transfer_folders_to_sftp(config_file, remote_path)

