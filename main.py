import os
import sys
import re
import json
import shutil
import threading
import subprocess
import zipfile
import requests
import customtkinter as ctk


# --- RUTA PRINCIPAL DE APPDATA ---
# Guardará config, steamcmd y carpetas temporales en: C:\Users\Nombre\AppData\Roaming\SteamForge
APP_DATA_DIR = os.path.join(os.getenv("APPDATA", os.path.expanduser("~")), "SteamForge")
os.makedirs(APP_DATA_DIR, exist_ok=True)

CONFIG_FILE = os.path.join(APP_DATA_DIR, "config.json")
DEFAULT_DOWNLOAD_DIR = os.path.join(os.path.expanduser("~"), "Downloads", "SteamForge_Mods")


# --- PARCHE DE RUTAS PARA PYINSTALLER (--onefile) ---
def resource_path(relative_path):
    """Obtiene la ruta absoluta para recursos, funciona en dev y para PyInstaller"""
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)


# Configuración de apariencia
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

# Diccionario de Traducciones
TRANSLATIONS = {
    "English": {
        "title": "SteamForge",
        "dest_label": "Destination Directory:",
        "dest_placeholder": "Click 📁 to set a permanent destination folder...",
        "url_placeholder": "Paste Steam Workshop URL here...",
        "btn_download": "Download",
        "activity_log": "Activity Log:",
        "btn_open_folder": "Open Destination Folder",
        "select_folder_title": "Select Destination Folder",
        "log_folder_set": "[✔] New destination set: ",
        "log_no_url": "[-] Please enter a valid Steam Workshop URL.",
        "log_no_folder": "[!] No destination directory set. Please choose where to save mods...",
        "log_cancel_folder": "[-] Download canceled: Destination folder is required.",
        "log_steamcmd_attempt": "[+] [Source 1/2] Attempting native download via SteamCMD...",
        "log_steamcmd_install": "[!] Installing internal SteamCMD engine...",
        "log_ggntw_attempt": "[+] [Source 2/2] Requesting file via GGNTW Engine...",
        "log_parsing_id": "[+] Querying Workshop ID: ",
        "log_invalid_url": "[-] Invalid Steam Workshop URL.",
        "log_steam_err": "[-] Failed to fetch metadata from Steam.",
        "log_private_err": "[-] Item does not exist or is set to private.",
        "log_mod_found": "[✔] Mod Found: ",
        "log_steamcmd_failed": "[-] SteamCMD rejected request or returned empty directory.",
        "log_success": "\n[✔] DOWNLOAD & INSTALLATION COMPLETE!",
        "log_saved_in": "    Saved directly to: ",
        "log_fail_all": "\n[-] Failed to download mod across all available sources.",
        "log_unexpected_err": "[-] Unexpected error: ",
    },
    "Español": {
        "title": "SteamForge",
        "dest_label": "Carpeta de destino fija:",
        "dest_placeholder": "Haz clic en 📁 para fijar una carpeta...",
        "url_placeholder": "Pega la URL del mod de Steam Workshop...",
        "btn_download": "Descargar",
        "activity_log": "Registro de estado:",
        "btn_open_folder": "Abrir Carpeta de Destino",
        "select_folder_title": "Seleccionar carpeta de destino",
        "log_folder_set": "[✔] Nueva carpeta fija establecida: ",
        "log_no_url": "[-] Introduce una URL válida de Steam Workshop.",
        "log_no_folder": "[!] No hay carpeta fija elegida. Por favor, selecciona dónde guardar los mods...",
        "log_cancel_folder": "[-] Descarga cancelada: Se requiere una carpeta de destino.",
        "log_steamcmd_attempt": "[+] [Fuente 1/2] Probando descarga nativa con SteamCMD...",
        "log_steamcmd_install": "[!] Instalando motor SteamCMD interno...",
        "log_ggntw_attempt": "[+] [Fuente 2/2] Solicitando archivo vía GGNTW Engine...",
        "log_parsing_id": "[+] Consultando ID de Workshop: ",
        "log_invalid_url": "[-] URL no válida de Steam Workshop.",
        "log_steam_err": "[-] No se pudo obtener información de Steam.",
        "log_private_err": "[-] El artículo no existe o es privado.",
        "log_mod_found": "[✔] Mod localizado: ",
        "log_steamcmd_failed": "[-] SteamCMD rechazó la petición o no devolvió archivos.",
        "log_success": "\n[✔] ¡DESCARGA E INSTALACIÓN COMPLETADAS!",
        "log_saved_in": "    Guardado directamente en: ",
        "log_fail_all": "\n[-] No se pudo descargar el mod por ninguna de las fuentes disponibles.",
        "log_unexpected_err": "[-] Error inesperado: ",
    },
}


class SteamForgeApp(ctk.CTk):

    def __init__(self):
        super().__init__()

        self.title("SteamForge - Workshop Downloader")
        self.geometry("660x610")
        self.resizable(False, False)

        self.ultimo_archivo_descargado = None
        self.current_app_id = None

        # Cargar configuración guardada
        self.target_folder, self.current_lang = self.cargar_configuracion()

        self.crear_widgets()

    def cargar_configuracion(self):
        """Carga la carpeta y el idioma guardados desde AppData."""
        folder = ""
        lang = "English"
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    folder = data.get("target_folder", "")
                    lang = data.get("language", "English")
            except Exception:
                pass
        return folder, lang

    def guardar_configuracion(self):
        """Guarda la configuración actual en AppData."""
        try:
            data = {
                "target_folder": self.target_folder,
                "language": self.current_lang,
            }
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4)
        except Exception as e:
            self.log(f"[-] Error saving settings: {e}")

    def t(self, key):
        """Devuelve el texto traducido según el idioma actual."""
        return TRANSLATIONS.get(
            self.current_lang, TRANSLATIONS["English"]
        ).get(key, key)

    def crear_widgets(self):
        # Header (Título + Desplegable de Idioma)
        self.frame_top = ctk.CTkFrame(self, fg_color="transparent")
        self.frame_top.pack(fill="x", padx=20, pady=(15, 5))

        self.lbl_title = ctk.CTkLabel(
            self.frame_top,
            text=self.t("title"),
            font=ctk.CTkFont(size=22, weight="bold"),
        )
        self.lbl_title.pack(side="left")

        self.option_lang = ctk.CTkOptionMenu(
            self.frame_top,
            values=["English", "Español"],
            width=100,
            command=self.cambiar_idioma,
        )
        self.option_lang.set(self.current_lang)
        self.option_lang.pack(side="right")

        # --- SECCIÓN: CARPETA DE DESTINO ---
        self.frame_folder = ctk.CTkFrame(self)
        self.frame_folder.pack(fill="x", padx=20, pady=5)

        self.lbl_folder_title = ctk.CTkLabel(
            self.frame_folder,
            text=self.t("dest_label"),
            font=ctk.CTkFont(size=11, weight="bold"),
        )
        self.lbl_folder_title.pack(anchor="w", padx=10, pady=(5, 0))

        self.entry_folder = ctk.CTkEntry(
            self.frame_folder,
            placeholder_text=self.t("dest_placeholder"),
            width=540,
        )
        if self.target_folder:
            self.entry_folder.insert(0, self.target_folder)
        self.entry_folder.pack(side="left", padx=(10, 5), pady=(2, 10))

        self.btn_select_folder = ctk.CTkButton(
            self.frame_folder,
            text="📁",
            width=40,
            fg_color="#3B82F6",
            hover_color="#2563EB",
            command=self.seleccionar_carpeta_destino,
        )
        self.btn_select_folder.pack(side="right", padx=(5, 10), pady=(2, 10))

        # --- SECCIÓN: ENTRADA DE URL Y BOTÓN ---
        self.frame_input = ctk.CTkFrame(self)
        self.frame_input.pack(fill="x", padx=20, pady=10)

        self.entry_url = ctk.CTkEntry(
            self.frame_input,
            placeholder_text=self.t("url_placeholder"),
            width=460,
        )
        self.entry_url.pack(side="left", padx=(10, 5), pady=10)

        self.btn_download = ctk.CTkButton(
            self.frame_input,
            text=self.t("btn_download"),
            width=120,
            command=self.iniciar_descarga_thread,
        )
        self.btn_download.pack(side="right", padx=(5, 10), pady=10)

        # Barra de progreso
        self.progress_bar = ctk.CTkProgressBar(self, width=620)
        self.progress_bar.pack(pady=10)
        self.progress_bar.set(0)

        # Registro / Log visual
        self.lbl_log = ctk.CTkLabel(
            self, text=self.t("activity_log"), font=ctk.CTkFont(size=12)
        )
        self.lbl_log.pack(anchor="w", padx=20, pady=(5, 2))

        self.txt_log = ctk.CTkTextbox(self, width=620, height=220)
        self.txt_log.pack(padx=20, pady=5)
        self.txt_log.configure(state="disabled")

        # Botón para abrir la carpeta actual
        self.frame_buttons = ctk.CTkFrame(self, fg_color="transparent")
        self.frame_buttons.pack(fill="x", padx=20, pady=10)

        self.btn_open_downloads = ctk.CTkButton(
            self.frame_buttons,
            text=self.t("btn_open_folder"),
            fg_color="#10B981",
            hover_color="#059669",
            command=self.abrir_carpeta_actual,
        )
        self.btn_open_downloads.pack(side="left", expand=True, padx=5)

    def cambiar_idioma(self, nuevo_idioma):
        self.current_lang = nuevo_idioma
        self.guardar_configuracion()

        self.lbl_title.configure(text=self.t("title"))
        self.lbl_folder_title.configure(text=self.t("dest_label"))
        self.entry_folder.configure(
            placeholder_text=self.t("dest_placeholder")
        )
        self.entry_url.configure(placeholder_text=self.t("url_placeholder"))
        self.btn_download.configure(text=self.t("btn_download"))
        self.lbl_log.configure(text=self.t("activity_log"))
        self.btn_open_downloads.configure(text=self.t("btn_open_folder"))

    def log(self, mensaje):
        self.txt_log.configure(state="normal")
        self.txt_log.insert("end", mensaje + "\n")
        self.txt_log.see("end")
        self.txt_log.configure(state="disabled")

    def seleccionar_carpeta_destino(self):
        carpeta = ctk.filedialog.askdirectory(
            title=self.t("select_folder_title")
        )
        if carpeta:
            self.entry_folder.delete(0, "end")
            self.entry_folder.insert(0, carpeta)
            self.target_folder = carpeta
            self.guardar_configuracion()
            self.log(self.t("log_folder_set") + carpeta)

    def abrir_carpeta_actual(self):
        ruta = self.entry_folder.get().strip() or DEFAULT_DOWNLOAD_DIR
        if not os.path.exists(ruta):
            os.makedirs(ruta, exist_ok=True)
        subprocess.Popen(f'explorer "{os.path.abspath(ruta)}"')

    def iniciar_descarga_thread(self):
        url = self.entry_url.get().strip()
        if not url:
            self.log(self.t("log_no_url"))
            return

        if not self.target_folder and not self.entry_folder.get().strip():
            self.log(self.t("log_no_folder"))
            carpeta = ctk.filedialog.askdirectory(
                title=self.t("select_folder_title")
            )
            if carpeta:
                self.entry_folder.delete(0, "end")
                self.entry_folder.insert(0, carpeta)
                self.target_folder = carpeta
                self.guardar_configuracion()
            else:
                self.log(self.t("log_cancel_folder"))
                return

        self.btn_download.configure(state="disabled")
        self.btn_select_folder.configure(state="disabled")
        self.progress_bar.set(0.1)

        threading.Thread(
            target=self.procesar_descarga, args=(url,), daemon=True
        ).start()

    # --- FUENTE 1: STEAMCMD (Ubicado en AppData) ---
    def intentar_steamcmd(self, publishedfileid, titulo_mod, temp_dir):
        self.log(self.t("log_steamcmd_attempt"))
        steamcmd_dir = os.path.join(APP_DATA_DIR, "steamcmd")
        steamcmd_exe = os.path.join(steamcmd_dir, "steamcmd.exe")

        if not os.path.exists(steamcmd_exe):
            self.log(self.t("log_steamcmd_install"))
            os.makedirs(steamcmd_dir, exist_ok=True)
            res_zip = requests.get(
                "https://steamcdn-a.akamaihd.net/client/installer/steamcmd.zip"
            )
            zip_path = os.path.join(steamcmd_dir, "steamcmd.zip")

            with open(zip_path, "wb") as f:
                f.write(res_zip.content)

            with zipfile.ZipFile(zip_path, "r") as zip_ref:
                zip_ref.extractall(steamcmd_dir)
            os.remove(zip_path)

        comando = [
            steamcmd_exe,
            "+login",
            "anonymous",
            "+workshop_download_item",
            str(self.current_app_id),
            str(publishedfileid),
            "+quit",
        ]

        subprocess.run(
            comando, capture_output=True, text=True, creationflags=0x08000000
        )

        ruta_interna = os.path.join(
            steamcmd_dir,
            "steamapps",
            "workshop",
            "content",
            str(self.current_app_id),
            str(publishedfileid),
        )

        if os.path.exists(ruta_interna) and os.listdir(ruta_interna):
            nombre_limpio = re.sub(r'[\\/*?:"<>|]', "", titulo_mod)
            ruta_destino = os.path.join(temp_dir, nombre_limpio)

            if os.path.exists(ruta_destino):
                shutil.rmtree(ruta_destino)

            shutil.copytree(ruta_interna, ruta_destino)
            return ruta_destino

        return None

    # --- FUENTE 2: GGNTW ENGINE ---
    def resolver_url_cdn(self, page_url):
        try:
            res = requests.get(page_url, timeout=10)
            if res.status_code == 200:
                match = re.search(
                    r'href=["\'](https?://[^"\']+\.(?:zip|bin|rar|7z)[^"\']*)["\']',
                    res.text,
                    re.IGNORECASE,
                ) or re.search(
                    r'window\.location\.href\s*=\s*["\']([^"\']+)["\']',
                    res.text,
                    re.IGNORECASE,
                )
                if match and match.group(1):
                    return match.group(1)
        except Exception:
            pass
        return page_url

    def intentar_ggntw(self, publishedfileid, titulo_mod, temp_dir):
        self.log(self.t("log_ggntw_attempt"))
        url_api = "https://api.ggntw.com/steam.request"
        payload = {
            "url": f"https://steamcommunity.com/sharedfiles/filedetails/?id={publishedfileid}"
        }
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "insomnia/2023.5.8",
        }

        try:
            res = requests.post(
                url_api, json=payload, headers=headers, timeout=15
            )
            if res.status_code == 200 and res.json().get("url"):
                download_url = res.json()["url"]

                if not re.search(
                    r"\.(zip|rar|bin|7z|gz)(\?.*)?$",
                    download_url,
                    re.IGNORECASE,
                ):
                    download_url = self.resolver_url_cdn(download_url)

                nombre_limpio = re.sub(r'[\\/*?:"<>|]', "", titulo_mod)
                ruta_paquete = os.path.join(temp_dir, f"{nombre_limpio}.zip")

                res_file = requests.get(download_url, stream=True, timeout=120)
                if res_file.status_code == 200:
                    with open(ruta_paquete, "wb") as f:
                        for chunk in res_file.iter_content(chunk_size=8192):
                            if chunk:
                                f.write(chunk)

                    ruta_final = os.path.join(temp_dir, nombre_limpio)
                    try:
                        if zipfile.is_zipfile(ruta_paquete):
                            if os.path.exists(ruta_final):
                                shutil.rmtree(ruta_final)
                            with zipfile.ZipFile(ruta_paquete, "r") as zip_ref:
                                zip_ref.extractall(ruta_final)
                            os.remove(ruta_paquete)
                        else:
                            ruta_final = ruta_paquete
                    except Exception:
                        ruta_final = ruta_paquete

                    return ruta_final
        except Exception:
            pass
        return None

    def procesar_descarga(self, url):
        try:
            match = re.search(r"id=(\d+)", url)
            if not match:
                self.log(self.t("log_invalid_url"))
                self.restablecer_ui()
                return

            publishedfileid = match.group(1)
            self.log(self.t("log_parsing_id") + publishedfileid)

            steam_api_url = "https://api.steampowered.com/ISteamRemoteStorage/GetPublishedFileDetails/v1/"
            res = requests.post(
                steam_api_url,
                data={
                    "itemcount": 1,
                    "publishedfileids[0]": publishedfileid,
                },
                timeout=10,
            )

            if res.status_code != 200 or not res.json().get(
                "response", {}
            ).get("publishedfiledetails"):
                self.log(self.t("log_steam_err"))
                self.restablecer_ui()
                return

            details = res.json()["response"]["publishedfiledetails"][0]
            if details.get("result") != 1:
                self.log(self.t("log_private_err"))
                self.restablecer_ui()
                return

            titulo_mod = details.get("title", f"Workshop_{publishedfileid}")
            self.current_app_id = details.get("consumer_app_id")

            self.log(self.t("log_mod_found") + titulo_mod)
            self.progress_bar.set(0.3)

            carpeta_destino_final = (
                self.entry_folder.get().strip() or DEFAULT_DOWNLOAD_DIR
            )

            # Archivos temporales guardados en AppData
            temp_dir = os.path.join(APP_DATA_DIR, "temp_download")
            os.makedirs(temp_dir, exist_ok=True)

            ruta_temp = self.intentar_steamcmd(
                publishedfileid, titulo_mod, temp_dir
            )

            if not ruta_temp:
                self.log(self.t("log_steamcmd_failed"))
                self.progress_bar.set(0.6)
                ruta_temp = self.intentar_ggntw(
                    publishedfileid, titulo_mod, temp_dir
                )

            if ruta_temp and os.path.exists(ruta_temp):
                nombre_item = os.path.basename(ruta_temp)
                destino_definitivo = os.path.join(
                    carpeta_destino_final, nombre_item
                )

                if not os.path.exists(carpeta_destino_final):
                    os.makedirs(carpeta_destino_final, exist_ok=True)

                if os.path.isdir(ruta_temp):
                    if os.path.exists(destino_definitivo):
                        shutil.rmtree(destino_definitivo)
                    shutil.move(ruta_temp, destino_definitivo)
                else:
                    shutil.move(ruta_temp, destino_definitivo)

                if os.path.exists(temp_dir):
                    shutil.rmtree(temp_dir, ignore_errors=True)

                self.progress_bar.set(1.0)
                self.log(self.t("log_success"))
                self.log(
                    self.t("log_saved_in")
                    + os.path.abspath(destino_definitivo)
                )
            else:
                self.log(self.t("log_fail_all"))

        except Exception as e:
            self.log(self.t("log_unexpected_err") + str(e))

        self.restablecer_ui()

    def restablecer_ui(self):
        self.btn_download.configure(state="normal")
        self.btn_select_folder.configure(state="normal")


if __name__ == "__main__":
    app = SteamForgeApp()
    app.mainloop()