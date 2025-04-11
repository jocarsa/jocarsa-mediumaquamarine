import paramiko
import os
import json
from datetime import datetime
import sys
import time
import subprocess

PROGRESS_FILE = "progress.txt"
LOG_FILE = "backup_log.json"  # (Opcional) archivo de log para detalles del respaldo

# Lista de carpetas a excluir del proceso de respaldo
EXCLUDE_FOLDERS = [".git", "myphp", "node_modules", "josevicentecarratala.com"]

def load_ftp_config(config_file):
    try:
        with open(config_file, 'r') as file:
            return json.load(file)
    except Exception as e:
        print(f"Error al cargar el archivo de configuración: {e}")
        return None

def load_db_config(config_file):
    try:
        with open(config_file, 'r') as file:
            return json.load(file)
    except Exception as e:
        print(f"Error al cargar el archivo de configuración de la base de datos: {e}")
        return None

def count_files_in_dir(local_dir):
    count = 0
    for root, dirs, files in os.walk(local_dir):
        # Excluir carpetas indicadas
        dirs[:] = [d for d in dirs if d not in EXCLUDE_FOLDERS]
        count += len(files)
    return count

def format_time(seconds):
    """Convierte segundos en formato hh:mm:ss."""
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    return f"{h:02}:{m:02}:{s:02}"

def clear_screen():
    """Limpia la pantalla y reposiciona el cursor en la esquina superior izquierda."""
    sys.stdout.write("\033[2J\033[H")
    sys.stdout.flush()

def dump_mysql_databases(db_config, output_dir):
    try:
        os.makedirs(output_dir, exist_ok=True)
        host = db_config.get("host")
        port = db_config.get("port")
        user = db_config.get("user")
        password = db_config.get("password")
        databases = db_config.get("databases", [])

        for db in databases:
            dump_command = [
                "mysqldump",
                "--host", host,
                "--port", str(port),
                "--user", user,
                "--password", password,
                "--databases", db,
                "--events", "--routines", "--triggers",
                "--result-file", os.path.join(output_dir, f"{db}.sql")
            ]
            subprocess.run(dump_command, check=True)
            print(f"Dumped database {db} to {output_dir}/{db}.sql")
    except Exception as e:
        print(f"Error dumping MySQL databases: {e}")

def transfer_folders_to_sftp(config_file, remote_path, db_config_file):
    config = load_ftp_config(config_file)
    if not config:
        print("Configuración inválida. Abortando.")
        return

    hostname = config.get("hostname")
    port = config.get("port", 22)
    username = config.get("username")
    password = config.get("password")
    local_folders = config.get("folders", [])

    # Dump MySQL databases
    db_config = load_db_config(db_config_file)
    if db_config:
        mysql_dump_dir = "mysql"
        dump_mysql_databases(db_config, mysql_dump_dir)
        local_folders.append(mysql_dump_dir)

    # Calcular el número total de archivos a subir (para seguimiento de progreso)
    total_files = 0
    for folder in local_folders:
        total_files += count_files_in_dir(folder)
    uploaded_files = 0

    try:
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(hostname, port=port, username=username, password=password)
        print("Conexión establecida.")

        sftp = ssh.open_sftp()

        # Crear un directorio remoto con marca de tiempo
        timestamp = datetime.now().strftime("%Y-%m-%d-%H-%M-%S")
        remote_timestamped_path = os.path.join(remote_path, timestamp)
        print(f"Creando directorio remoto: {remote_timestamped_path}...")
        try:
            sftp.mkdir(remote_path)
        except IOError:
            print(f"El directorio base remoto '{remote_path}' ya existe.")
        sftp.mkdir(remote_timestamped_path)
        print("Directorio remoto con marca de tiempo creado.")

        # Registrar el tiempo de inicio
        start_time = time.time()

        # Animación de “dos contenedores” (uno lleno a la izquierda y otro vacío a la derecha)
        # y un "pipe" por donde viajan los "paquetes".
        # Mantendremos un índice de cuadro para animar el "pipe".
        pipe_index = 0
        pipe_length = 12  # longitud del "pipe"

        def update_progress(uploaded, total):
            nonlocal pipe_index

            elapsed_time = time.time() - start_time
            avg_time = elapsed_time / uploaded if uploaded > 0 else 0
            remaining_files = total - uploaded
            est_remaining_time = avg_time * remaining_files if uploaded > 0 else 0

            elapsed_str = format_time(elapsed_time)
            remaining_str = format_time(est_remaining_time)
            percentage = (uploaded / total) * 100 if total else 100

            # Progreso en barra tradicional
            progress_bar_length = 50
            filled_length = int(progress_bar_length * uploaded // total) if total > 0 else progress_bar_length
            bar = '█' * filled_length + '-' * (progress_bar_length - filled_length)

            # Mensaje de bienvenida
            welcome_line1 = "\033[38;5;79mjocarsa | mediumaquamarine\033[0m"
            welcome_line2 = "Programa de copia de seguridad"
            welcome_line3 = "(c) 2025 JOCARSA"
            welcome_line4 = "\033[92mComenzando copia de seguridad...\033[0m"

            # Líneas de progreso estándar
            line1 = f"\033[92mArchivo: {uploaded} de {total}\033[0m"
            line2 = f"\033[94mPorcentaje: {percentage:.2f}%\033[0m"
            line3 = f"\033[96m[{bar}]\033[0m"
            line4 = f"\033[93mTiempo transcurrido: {elapsed_str}\033[0m"
            line5 = f"\033[91mTiempo estimado restante: {remaining_str}\033[0m"

            # Construir animación de contenedores y pipe
            # Contenedor izquierdo (siempre lleno de 10/10)
            left_container = "██████████"

            # Contenedor derecho (se llena 1/10 cada 10%)
            filled_right = int(percentage // 10)
            right_container = "█" * filled_right + "." * (10 - filled_right)

            # Actualizar pipe_index para la animación
            pipe_index = (pipe_index + 1) % pipe_length

            # Construir la animación del “pipe” con un solo “o” que se mueve
            pipe_chars = ["-"] * pipe_length
            pipe_chars[pipe_index] = "o"
            pipe_str = "".join(pipe_chars)

            # Estructura: [left_container] |pipe| [right_container]
            # Ejemplo: [██████████] --o------ [██........]
            containers_line = f"[{left_container}] {pipe_str} [{right_container}]"

            # Limpiar la pantalla y reimprimir toda la información
            clear_screen()
            sys.stdout.write(f"{welcome_line1}\n{welcome_line2}\n{welcome_line3}\n{welcome_line4}\n\n")
            sys.stdout.write(f"{line1}\n{line2}\n{line3}\n{line4}\n{line5}\n\n")
            sys.stdout.write(f"{containers_line}\n")
            sys.stdout.flush()

            # Guardar el porcentaje en un archivo de progreso
            with open(PROGRESS_FILE, "w") as pf:
                pf.write(str(percentage))

            return percentage

        def upload_dir(local_dir, remote_dir):
            nonlocal uploaded_files
            for item in os.listdir(local_dir):
                if item in EXCLUDE_FOLDERS:
                    print(f"Saltando la carpeta excluida: {item}")
                    continue

                local_path = os.path.join(local_dir, item)
                remote_item_path = os.path.join(remote_dir, item)
                if os.path.isfile(local_path):
                    sftp.put(local_path, remote_item_path)
                    uploaded_files += 1
                    update_progress(uploaded_files, total_files)
                elif os.path.isdir(local_path):
                    try:
                        sftp.mkdir(remote_item_path)
                    except IOError:
                        pass
                    upload_dir(local_path, remote_item_path)

        # Subir cada carpeta local
        for local_folder in local_folders:
            folder_name = os.path.basename(os.path.normpath(local_folder))
            remote_folder_path = os.path.join(remote_timestamped_path, folder_name)
            print(f"Creando subcarpeta para {folder_name}: {remote_folder_path}...")
            try:
                sftp.mkdir(remote_folder_path)
            except IOError:
                print(f"La subcarpeta {remote_folder_path} ya existe.")
            print(f"Transfiriendo el contenido de {local_folder} a {remote_folder_path}...")
            upload_dir(local_folder, remote_folder_path)

        clear_screen()
        print("Transferencia completada.\n")

        # Registrar los detalles del respaldo (opcional)
        backup_record = {
            "timestamp": timestamp,
            "total_files": total_files,
            "uploaded_files": uploaded_files,
            "remote_path": remote_timestamped_path
        }
        with open(LOG_FILE, "a") as lf:
            lf.write(json.dumps(backup_record) + "\n")

    except Exception as e:
        print(f"\nOcurrió un error: {e}")

    finally:
        try:
            sftp.close()
            ssh.close()
        except Exception:
            pass

if __name__ == "__main__":
    config_file = "ftp_config.json"
    db_config_file = "db_config.json"
    remote_path = "copiasdeseguridad"
    transfer_folders_to_sftp(config_file, remote_path, db_config_file)

