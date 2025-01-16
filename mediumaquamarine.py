import paramiko
import os
import json
from datetime import datetime

def load_ftp_config(config_file):
    try:
        with open(config_file, 'r') as file:
            return json.load(file)
    except Exception as e:
        print(f"Failed to load config file: {e}")
        return None

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
            for item in os.listdir(local_dir):
                local_path = os.path.join(local_dir, item)
                remote_path = os.path.join(remote_dir, item)
                if os.path.isfile(local_path):
                    print(f"Uploading file {local_path} to {remote_path}...")
                    sftp.put(local_path, remote_path)
                elif os.path.isdir(local_path):
                    print(f"Creating directory {remote_path}...")
                    try:
                        sftp.mkdir(remote_path)
                    except IOError:
                        print(f"Directory {remote_path} already exists.")
                    upload_dir(local_path, remote_path)

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

    except Exception as e:
        print(f"An error occurred: {e}")

    finally:
        sftp.close()
        ssh.close()

config_file = "ftp_config.json"
remote_path = "copiasdeseguridad"

transfer_folders_to_sftp(config_file, remote_path)
