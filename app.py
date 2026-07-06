import os
import json
import subprocess
from pathlib import Path

import streamlit as st

st.set_page_config(page_title="MY SHORTS", layout="wide")

st.title("MY SHORTS")
st.write("Generador de clips verticales desde YouTube")

url = st.text_input("Pega la URL de YouTube")

num_clips = st.selectbox(
    "Número de clips",
    [1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
    index=2
)

aspect_ratio = st.selectbox(
    "Formato",
    ["9:16", "1:1", "4:5", "16:9"]
)

mode = st.selectbox(
    "Modo",
    ["local", "api"]
)

if st.button("Generar clips"):
    if not url:
        st.error("Pega primero una URL de YouTube.")
    else:
        output_json = "result.json"

        command = [
            "python",
            "main.py",
            url,
            "--mode",
            mode,
            "--num-clips",
            str(num_clips),
            "--aspect-ratio",
            aspect_ratio,
            "--output-json",
            output_json
        ]

        st.write("Procesando video... esto puede tardar varios minutos.")

        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=1800
            )

            if result.returncode != 0:
                st.error("Hubo un error procesando el video.")
                st.code(result.stderr)
            else:
                st.success("Clips generados.")

                if os.path.exists(output_json):
                    with open(output_json, "r", encoding="utf-8") as f:
                        data = json.load(f)

                    st.subheader("Resultado JSON")
                    st.json(data)

                st.subheader("Videos generados")

                mp4_files = list(Path(".").rglob("*.mp4"))

                if not mp4_files:
                    st.warning("No encontré archivos .mp4 generados.")
                else:
                    for video_path in mp4_files:
                        st.write(video_path.name)
                        st.video(str(video_path))

                        with open(video_path, "rb") as file:
                            st.download_button(
                                label=f"Descargar {video_path.name}",
                                data=file,
                                file_name=video_path.name,
                                mime="video/mp4"
                            )

        except subprocess.TimeoutExpired:
            st.error("El proceso tardó demasiado y se detuvo.")
