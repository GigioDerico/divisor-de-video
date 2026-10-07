#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Comprime um vídeo para ficar abaixo de 200MB.
Requer: FFmpeg instalado (https://ffmpeg.org/download.html)
"""

import os
import sys
import glob
import math
import subprocess
import shutil

def get_file_size_mb(filepath):
    """Retorna o tamanho do arquivo em MB."""
    return os.path.getsize(filepath) / (1024 * 1024)

def compress_video(input_path, target_mb=200):
    """Comprime o vídeo até ficar abaixo do tamanho alvo."""

    if not os.path.exists(input_path):
        print(f"❌ Arquivo não encontrado: {input_path}")
        return

    original_size = get_file_size_mb(input_path)
    print(f"📁 Arquivo original: {input_path}")
    print(f"📊 Tamanho original: {original_size:.2f} MB")

    # Se já está abaixo do alvo, não faz nada
    if original_size <= target_mb:
        print(f"✅ O arquivo já está abaixo de {target_mb}MB. Nada a fazer.")
        return

    # Verifica se o FFmpeg está instalado
    if not shutil.which("ffmpeg"):
        print("\n⚠️  FFmpeg não encontrado!")
        print("   Baixe e instale em: https://ffmpeg.org/download.html")
        print("   Ou use: brew install ffmpeg (Mac) / sudo apt install ffmpeg (Linux)")
        return

    # Gera nome do arquivo de saída
    base, ext = os.path.splitext(input_path)
    output_path = f"{base}_comprimido{ext}"

    # Calcula o bitrate de vídeo necessário (em bits por segundo)
    # Obtém a duração do vídeo
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", input_path],
            capture_output=True, text=True
        )
        duration = float(result.stdout.strip())
    except Exception:
        print("⚠️  Não foi possível obter a duração do vídeo. Usando CRF adaptativo...")
        duration = None

    if duration and duration > 0:
        # Margem de segurança: mira 5% abaixo do alvo (overhead do container
        # e imprecisão do codificador)
        alvo_mb = target_mb * 0.95

        # Calcula bitrate de vídeo para caber no alvo (deixa 128kbps para áudio)
        target_bits = (alvo_mb * 8 * 1024 * 1024) - (128 * 1024 * duration)
        video_bitrate = int(max(target_bits / duration, 100000))  # mínimo 100kbps

        print(f"⏱️  Duração: {duration:.1f} segundos")
        print(f"🎯 Bitrate de vídeo calculado: {video_bitrate // 1000} kbps")
        print(f"🚀 Comprimindo em 2 passagens (passagem 1/2)...\n")

        # 2 passagens: a 1ª analisa o vídeo, a 2ª codifica respeitando o bitrate.
        # Passagem única (-b:v sozinho) estoura o alvo em bitrates baixos.
        passlog = f"{base}_2pass"
        cmd_pass1 = [
            "ffmpeg", "-y", "-i", input_path,
            "-c:v", "libx264", "-b:v", f"{video_bitrate}",
            "-pass", "1", "-passlogfile", passlog,
            "-an", "-f", "null", os.devnull
        ]
        cmd = [
            "ffmpeg", "-y", "-i", input_path,
            "-c:v", "libx264", "-b:v", f"{video_bitrate}",
            "-pass", "2", "-passlogfile", passlog,
            "-c:a", "aac", "-b:a", "128k",
            "-movflags", "+faststart",
            output_path
        ]

        process = subprocess.run(cmd_pass1, capture_output=True, text=True)
        if process.returncode != 0:
            print(f"❌ Erro na passagem 1:\n{process.stderr}")
            return
        print("🚀 Passagem 2/2...\n")
    else:
        # Fallback: usa CRF (quanto menor, melhor qualidade)
        print("🚀 Comprimindo com CRF adaptativo...\n")
        # Começa com CRF 23 (padrão) e vai aumentando se necessário
        cmd = [
            "ffmpeg", "-y", "-i", input_path,
            "-c:v", "libx264", "-crf", "26", "-preset", "fast",
            "-c:a", "aac", "-b:a", "128k",
            "-movflags", "+faststart",
            output_path
        ]

    # Executa a compressão (passagem 2, ou CRF no fallback)
    process = subprocess.run(cmd, capture_output=True, text=True)

    # Remove arquivos temporários das 2 passagens
    if duration and duration > 0:
        for temp in glob.glob(f"{passlog}*.log*"):
            os.remove(temp)

    if process.returncode != 0:
        print(f"❌ Erro na compressão:\n{process.stderr}")
        return

    # Verifica o resultado
    new_size = get_file_size_mb(output_path)
    reduction = ((original_size - new_size) / original_size) * 100

    print(f"✅ Compressão concluída!")
    print(f"📁 Arquivo salvo: {output_path}")
    print(f"📊 Tamanho final: {new_size:.2f} MB")
    print(f"📉 Redução: {reduction:.1f}%")

    if new_size <= target_mb:
        print(f"🎉 O arquivo está abaixo de {target_mb}MB!")
    else:
        print(f"⚠️  Ainda acima de {target_mb}MB. Aumente a margem de segurança")
        print(f"   (mude 'target_mb * 0.95' para 'target_mb * 0.90') e rode de novo.")


def split_video(input_path, partes=None, target_mb=200, output_dir=None):
    """Divide o vídeo em partes sem recodificar (rápido, sem perda de qualidade).

    Se `partes` não for informado, calcula o número mínimo de partes para que
    cada uma fique abaixo de `target_mb` (assumindo bitrate ~constante).
    Se `output_dir` for informado, as partes são salvas lá em vez da pasta do
    arquivo original.
    """

    if not os.path.exists(input_path):
        print(f"❌ Arquivo não encontrado: {input_path}")
        return

    if not shutil.which("ffmpeg"):
        print("\n⚠️  FFmpeg não encontrado!")
        return

    original_size = get_file_size_mb(input_path)
    print(f"📁 Arquivo original: {input_path}")
    print(f"📊 Tamanho original: {original_size:.2f} MB")

    if partes is None:
        # Margem de segurança: mira 5% abaixo do alvo (overhead do container
        # e distribuição não perfeitamente uniforme do bitrate entre cortes)
        alvo_mb = target_mb * 0.95
        partes = max(2, math.ceil(original_size / alvo_mb))
        print(f"🧮 Partes calculadas para ficar abaixo de {target_mb}MB: {partes}")

    try:
        result = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", input_path],
            capture_output=True, text=True
        )
        duration = float(result.stdout.strip())
    except Exception:
        print("❌ Não foi possível obter a duração do vídeo.")
        return

    segment_time = duration / partes
    nome_base, ext = os.path.splitext(os.path.basename(input_path))
    if output_dir:
        pasta_destino = os.path.join(output_dir, nome_base)
        os.makedirs(pasta_destino, exist_ok=True)
        base = os.path.join(pasta_destino, nome_base)
    else:
        base = os.path.splitext(input_path)[0]
    padrao_saida = f"{base}_parte_%02d{ext}"

    print(f"⏱️  Duração: {duration:.1f} segundos → {partes} partes de ~{segment_time / 60:.1f} min")
    print(f"✂️  Dividindo (sem recodificar, é rápido)...\n")

    # -c copy não recodifica: corta no keyframe mais próximo de cada metade
    cmd = [
        "ffmpeg", "-y", "-i", input_path,
        "-c", "copy", "-map", "0",
        "-f", "segment", "-segment_time", str(segment_time),
        "-reset_timestamps", "1",
        padrao_saida
    ]
    process = subprocess.run(cmd, capture_output=True, text=True)

    if process.returncode != 0:
        print(f"❌ Erro ao dividir:\n{process.stderr}")
        return

    print("✅ Divisão concluída!")
    maior_parte = 0
    for parte in sorted(glob.glob(f"{base}_parte_*{ext}")):
        tam_parte = get_file_size_mb(parte)
        maior_parte = max(maior_parte, tam_parte)
        print(f"📁 {parte} — {tam_parte:.2f} MB")

    if maior_parte > target_mb:
        print(f"⚠️  Pelo menos uma parte ficou acima de {target_mb}MB (bitrate não é uniforme no vídeo).")
        print(f"   Rode de novo com mais partes, ex: split_video(caminho, partes={partes + 1}).")
    else:
        print(f"🎉 Todas as partes ficaram abaixo de {target_mb}MB!")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python comprimir_video.py <caminho_do_video> [dividir] [n_partes]")
        print("Exemplo: python comprimir_video.py meu_video.mp4")
        print("Exemplo: python comprimir_video.py meu_video.mp4 dividir 3")
        sys.exit(1)

    if len(sys.argv) >= 3 and sys.argv[2] == "dividir":
        partes = int(sys.argv[3]) if len(sys.argv) >= 4 else 2
        split_video(sys.argv[1], partes)
    else:
        compress_video(sys.argv[1])
