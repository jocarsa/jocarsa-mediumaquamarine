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

def transfer_folder_to_sftp(config_file, local_folder, remote_path):
    config = load_ftp_config(config_file)
    if not config:
        print("Invalid configuration. Aborting.")
        return

    hostname = config.get("hostname")
    port = config.get("port", 22)
    username = config.get("username")
    password = config.get("password")

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

        # Recursively upload the folder
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

        print(f"Transferring folder {local_folder} to {remote_timestamped_path}...")
        upload_dir(local_folder, remote_timestamped_path)
        print("Transfer complete.")

    except Exception as e:
        print(f"An error occurred: {e}")

    finally:
        sftp.close()
        ssh.close()

config_file = "ftp_config.json"
local_folder = "/var/www/html/jocarsa-lightsalmon"
remote_path = "copiasdeseguridad"

transfer_folder_to_sftp(config_file, local_folder, remote_path)
