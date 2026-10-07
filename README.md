# Divisor de Vídeo

Interface web local para dividir vídeos grandes em partes menores que um
tamanho máximo escolhido por você (ex: para enviar por WhatsApp, e-mail ou
qualquer serviço com limite de upload).

A divisão é feita com `ffmpeg -c copy`, ou seja, **sem recodificar** — rápido
e sem perda de qualidade.

## Como funciona

1. Coloque os vídeos na pasta `videos/`.
2. Rode o servidor e abra a interface no navegador.
3. Escolha o tamanho máximo por parte (em MB) e clique em **Dividir**.
4. O número de partes é calculado automaticamente para que cada uma fique
   abaixo do limite informado.
5. As partes geradas ficam em `divididos/<nome_do_vídeo>/`.

## Requisitos

- Python 3
- [FFmpeg](https://ffmpeg.org/download.html) instalado e disponível no PATH

Instalação do FFmpeg:

```bash
# macOS
brew install ffmpeg

# Ubuntu/Debian
sudo apt install ffmpeg
```

## Uso

```bash
python3 server.py
```

Abre automaticamente `http://localhost:8000` no navegador.

## Formatos suportados

`.mp4`, `.mov`, `.mkv`, `.avi`, `.webm`, `.m4v`

## Uso via linha de comando (opcional)

```bash
python3 comprimir_video.py meu_video.mp4 dividir
```

Sem informar o número de partes, o script calcula automaticamente quantas
partes são necessárias para ficar abaixo de 200MB cada (padrão).

## Licença

MIT — veja [LICENSE](LICENSE).
