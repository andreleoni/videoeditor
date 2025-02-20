import whisper
import ffmpeg
import numpy as np
import cv2
import subprocess
import logging

logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

def extract_audio(video_path, audio_path):
    # Extrai o áudio do vídeo automaticamente.
    try:
        subprocess.run(["ffmpeg", "-i", video_path, "-q:a", "0", "-map", "a", audio_path, "-y"], check=True)
        logging.info(f"Áudio extraído com sucesso: {audio_path}")

    except subprocess.CalledProcessError as e:
        logging.error(f"Erro ao extrair áudio: {e}")

def transcribe_audio(audio_path):
    try:
        model = whisper.load_model("small")  # Modelo balanceado entre precisão e velocidade
        result = model.transcribe(audio_path)
        logging.info("Transcrição realizada com sucesso")

        return result["segments"]
    except Exception as e:
        logging.error(f"Erro ao transcrever áudio: {e}")
        return []

def detect_silences(audio_path, threshold=-40, min_silence_duration=0.5):
    # Detecta silêncios com FFmpeg.
    cmd = [
        "ffmpeg", "-i", audio_path, "-af",
        f"silencedetect=noise={threshold}dB:d={min_silence_duration}", "-f", "null", "-"
    ]
    try:
        result = subprocess.run(cmd, stderr=subprocess.PIPE, text=True, check=True)
        silences = []
        for line in result.stderr.split("\n"):
            if "silence_start" in line:
                silences.append(float(line.split(" ")[-1]))
        logging.info("Silêncios detectados com sucesso")
        return silences
    except subprocess.CalledProcessError as e:
        logging.error(f"Erro ao detectar silêncios: {e}")
        return []

def generate_cuts(transcription, silences):
    # Gera cortes automáticos baseados em pausas e frases de efeito.
    cuts = []
    for segment in transcription:
        start, end, text = segment['start'], segment['end'], segment['text']
        if any(s for s in silences if start <= s <= end):
            cuts.append((start, end))
    logging.info(f"Cortes gerados: {cuts}")
    return cuts

def edit_video(video_path, cuts, output_path):
    # Aplica cortes ao vídeo usando FFmpeg.
    if not cuts:
        logging.warning("Nenhum corte detectado. O vídeo original será mantido.")
        return

    filter_complex = ""
    maps = []

    for i, (start, end) in enumerate(cuts):
        filter_complex += (
            f"[0:v]trim=start={start}:end={end},setpts=PTS-STARTPTS[v{i}];"
            f"[0:a]atrim=start={start}:end={end},asetpts=PTS-STARTPTS[a{i}];"
        )
        maps.append(f"[v{i}][a{i}]")

    # Concatenando os segmentos
    filter_complex += f"{''.join(maps)}concat=n={len(cuts)}:v=1:a=1[outv][outa]"

    cmd = [
        "ffmpeg", "-i", video_path, "-filter_complex", filter_complex,
        "-map", "[outv]", "-map", "[outa]", output_path
    ]

    try:
        logging.info(f"Rodando FFmpeg: {' '.join(cmd)}")
        subprocess.run(cmd, check=True)
        logging.info(f"Vídeo editado com sucesso: {output_path}")
    except subprocess.CalledProcessError as e:
        logging.error(f"Erro ao editar vídeo: {e}")

if __name__ == "__main__":
    video_file = "input/input.mp4"
    audio_file = "input/input.wav"
    output_file = "output/output.mp4"

    logging.info("Iniciando edição de vídeo...")

    # Extrai áudio automaticamente
    extract_audio(video_file, audio_file)

    transcription = transcribe_audio(audio_file)
    silences = detect_silences(audio_file)
    cuts = generate_cuts(transcription, silences)
    edit_video(video_file, cuts, output_file)