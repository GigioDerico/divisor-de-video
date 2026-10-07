#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Servidor local com interface web para comprimir vídeos.
Rode: python3 server.py  e abra http://localhost:8000
"""

import os
import io
import html
import time
import threading
import contextlib
import webbrowser
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs, quote

from comprimir_video import split_video, get_file_size_mb

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
VIDEOS_DIR = os.path.join(BASE_DIR, "videos")
DIVIDIDOS_DIR = os.path.join(BASE_DIR, "divididos")
PORT = 8000

EXTENSOES = {".mp4", ".mov", ".mkv", ".avi", ".webm", ".m4v"}

# Tarefas em andamento: nome -> {"inicio": timestamp, "acao": "comprimir"|"dividir",
#                                "saida": caminho|None, "log": str|None}
JOBS = {}
JOBS_LOCK = threading.Lock()

PAGE = """<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Comprimir Vídeo</title>
<style>
  body { font-family: -apple-system, sans-serif; max-width: 720px; margin: 40px auto; padding: 0 16px; background: #f5f5f7; color: #1d1d1f; }
  h1 { font-size: 24px; }
  .card { background: #fff; border-radius: 12px; padding: 16px 20px; margin: 12px 0; box-shadow: 0 1px 3px rgba(0,0,0,.08); display: flex; align-items: center; justify-content: space-between; gap: 12px; }
  .nome { word-break: break-all; }
  .tam { color: #6e6e73; font-size: 14px; white-space: nowrap; }
  .acoes { display: flex; gap: 8px; align-items: center; }
  input[type=number] { width: 70px; border: 1px solid #d2d2d7; border-radius: 8px; padding: 7px 8px; font-size: 14px; }
  button { background: #0071e3; color: #fff; border: 0; border-radius: 8px; padding: 8px 16px; font-size: 14px; cursor: pointer; white-space: nowrap; }
  button:hover { background: #0077ed; }
  button.secundario { background: #34c759; }
  button.secundario:hover { background: #30d158; }
  button:disabled { background: #d2d2d7; color: #8e8e93; cursor: not-allowed; }
  .aviso { color: #34c759; font-size: 14px; font-weight: 600; white-space: nowrap; }
  pre { background: #1d1d1f; color: #d2d2d7; padding: 16px; border-radius: 12px; white-space: pre-wrap; word-break: break-all; }
  a.voltar { color: #0071e3; text-decoration: none; }
  .vazio { color: #6e6e73; }
</style>
</head>
<body>
{conteudo}
</body>
</html>"""


def listar_videos(pasta):
    if not os.path.isdir(pasta):
        return []
    arquivos = []
    for nome in sorted(os.listdir(pasta)):
        caminho = os.path.join(pasta, nome)
        if os.path.isfile(caminho) and os.path.splitext(nome)[1].lower() in EXTENSOES:
            arquivos.append((nome, get_file_size_mb(caminho)))
    return arquivos


def pagina_lista():
    videos = listar_videos(VIDEOS_DIR)
    itens = ""
    for nome, tam in videos:
        nome_html = html.escape(nome)
        nome_base = os.path.splitext(nome)[0]
        ja_dividido = bool(listar_videos(os.path.join(DIVIDIDOS_DIR, nome_base)))
        with JOBS_LOCK:
            em_andamento = nome in JOBS
        if em_andamento:
            acao = f'<a class="voltar" href="/status?arquivo={quote(nome)}">⏳ Processando...</a>'
        elif ja_dividido:
            acao = f"""
          <span class="acoes">
          <span class="aviso">✅ Já dividido</span>
          <button type="button" class="secundario" disabled>Dividir</button>
          </span>"""
        else:
            acao = f"""
          <span class="acoes">
          <form method="POST" action="/dividir">
            <input type="hidden" name="arquivo" value="{nome_html}">
            <input type="number" name="tamanho_mb" value="200" min="1" step="1" title="Tamanho máximo por parte (MB)">
            <button type="submit" class="secundario">Dividir</button>
          </form>
          </span>"""
        itens += f"""
        <div class="card">
          <span class="nome">{nome_html}<br><span class="tam">{tam:.1f} MB</span></span>
          {acao}
        </div>"""
    if not itens:
        itens = '<p class="vazio">Nenhum vídeo na pasta <code>videos/</code>. Coloque arquivos .mp4, .mov, .mkv, .avi, .webm ou .m4v lá e recarregue a página.</p>'

    conteudo = f"""
    <h1>🎬 Dividir Vídeo</h1>
    <p class="vazio">Pasta: <code>{html.escape(VIDEOS_DIR)}</code> — informe o tamanho máximo por parte (MB) e dividir calcula quantas partes são necessárias, sem recodificar</p>
    <p><a class="voltar" href="/divididos">📂 Ver partes já divididas →</a></p>
    {itens}"""
    return PAGE.replace("{conteudo}", conteudo)


def listar_pastas_divididas():
    if not os.path.isdir(DIVIDIDOS_DIR):
        return []
    pastas = []
    for nome in sorted(os.listdir(DIVIDIDOS_DIR)):
        caminho = os.path.join(DIVIDIDOS_DIR, nome)
        if os.path.isdir(caminho):
            pastas.append((nome, listar_videos(caminho)))
    return pastas


def pagina_divididos():
    pastas = listar_pastas_divididas()
    itens = ""
    for nome_video, partes in pastas:
        linhas = "".join(
            f"""
        <div class="card">
          <span class="nome">{html.escape(parte)}<br><span class="tam">{tam:.1f} MB</span></span>
        </div>"""
            for parte, tam in partes
        )
        itens += f"""
        <h3>{html.escape(nome_video)}</h3>
        {linhas}"""
    if not itens:
        itens = '<p class="vazio">Nenhuma parte gerada ainda.</p>'

    conteudo = f"""
    <h1>📂 Vídeos Divididos</h1>
    <p class="vazio">Pasta: <code>{html.escape(DIVIDIDOS_DIR)}</code> — cada vídeo tem sua própria subpasta</p>
    <p><a class="voltar" href="/">← Voltar</a></p>
    {itens}"""
    return PAGE.replace("{conteudo}", conteudo)


def pagina_resultado(nome, log):
    conteudo = f"""
    <h1>🎬 Resultado</h1>
    <p><strong>{html.escape(nome)}</strong></p>
    <pre>{html.escape(log)}</pre>
    <p><a class="voltar" href="/">← Voltar</a></p>"""
    return PAGE.replace("{conteudo}", conteudo)


def pagina_progresso(nome, job):
    decorrido = int(time.time() - job["inicio"])
    minutos, segundos = divmod(decorrido, 60)
    titulo = "✂️ Dividindo..."
    dica = "A divisão não recodifica o vídeo e costuma levar menos de um minuto."
    tam = "processando..."
    conteudo = f"""
    <meta http-equiv="refresh" content="5">
    <h1>{titulo}</h1>
    <p><strong>{html.escape(nome)}</strong></p>
    <div class="card">
      <span class="nome">Tempo decorrido: {minutos}min {segundos:02d}s<br>
      <span class="tam">{tam}</span></span>
    </div>
    <p class="vazio">A página atualiza sozinha a cada 5 segundos. {dica}</p>"""
    return PAGE.replace("{conteudo}", conteudo)


def _executar_em_fundo(nome, caminho, target_mb):
    buffer = io.StringIO()
    try:
        with contextlib.redirect_stdout(buffer):
            split_video(caminho, target_mb=target_mb, output_dir=DIVIDIDOS_DIR)
    except Exception as e:
        print(f"❌ Erro inesperado: {e}", file=buffer)
    with JOBS_LOCK:
        JOBS[nome]["log"] = buffer.getvalue()


class Handler(BaseHTTPRequestHandler):
    def _enviar(self, corpo, status=200):
        dados = corpo.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(dados)))
        self.end_headers()
        self.wfile.write(dados)

    def _redirecionar(self, destino):
        self.send_response(303)
        self.send_header("Location", destino)
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        rota = parsed.path
        if rota == "/":
            self._enviar(pagina_lista())
        elif rota == "/divididos":
            self._enviar(pagina_divididos())
        elif rota == "/status":
            nome = os.path.basename(parse_qs(parsed.query).get("arquivo", [""])[0])
            with JOBS_LOCK:
                job = JOBS.get(nome)
            if job is None:
                self._redirecionar("/")
            elif job["log"] is None:
                self._enviar(pagina_progresso(nome, job))
            else:
                with JOBS_LOCK:
                    JOBS.pop(nome, None)
                self._enviar(pagina_resultado(nome, job["log"]))
        else:
            self._enviar("<p>Não encontrado. <a href='/'>Voltar</a></p>", 404)

    def do_POST(self):
        rota = urlparse(self.path).path
        if rota != "/dividir":
            self._enviar("<p>Não encontrado. <a href='/'>Voltar</a></p>", 404)
            return

        tamanho = int(self.headers.get("Content-Length", 0))
        corpo = self.rfile.read(tamanho).decode("utf-8")
        campos = parse_qs(corpo)
        nome = campos.get("arquivo", [""])[0]

        # Segurança: só nome de arquivo, sem caminho
        nome = os.path.basename(nome)
        caminho = os.path.join(VIDEOS_DIR, nome)

        if not nome or not os.path.isfile(caminho):
            self._enviar(pagina_resultado(nome or "(vazio)", "❌ Arquivo não encontrado."))
            return

        try:
            target_mb = max(1, int(float(campos.get("tamanho_mb", ["200"])[0])))
        except (ValueError, TypeError):
            target_mb = 200

        with JOBS_LOCK:
            if nome in JOBS:
                ja_rodando = True
            else:
                ja_rodando = False
                JOBS[nome] = {"inicio": time.time(), "acao": "dividir", "saida": None, "log": None}

        if not ja_rodando:
            threading.Thread(target=_executar_em_fundo, args=(nome, caminho, target_mb), daemon=True).start()

        self._redirecionar(f"/status?arquivo={quote(nome)}")

    def log_message(self, formato, *args):
        pass  # silencia log de acesso


if __name__ == "__main__":
    os.makedirs(VIDEOS_DIR, exist_ok=True)
    os.makedirs(DIVIDIDOS_DIR, exist_ok=True)
    servidor = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    url = f"http://localhost:{PORT}"
    print(f"🚀 Servidor rodando em {url}")
    print(f"📁 Pasta de vídeos: {VIDEOS_DIR}")
    print("   Ctrl+C para parar.")
    webbrowser.open(url)
    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        print("\n👋 Servidor encerrado.")
