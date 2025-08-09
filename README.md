# 🎬 Plex DirectPlay Converter

[![Python Version](https://img.shields.io/badge/python-3.6%2B-blue.svg)](https://python.org)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![FFmpeg Required](https://img.shields.io/badge/requires-FFmpeg-red.svg)](https://ffmpeg.org)

Ein leistungsstarkes Python-Tool zur automatischen Konvertierung von Videodateien für **Apple TV 4K (3. Generation, 2022)** und **Plex Direct Play** Kompatibilität.

## ✨ Features

### 🎯 **Optimiert für Apple TV 4K Direct Play**
- **Container:** Automatische Konvertierung zu MP4
- **Video:** H.264 (libx264) mit SDR-Unterstützung
- **Audio:** AAC Stereo (2.0) für beste Kompatibilität
- **HDR zu SDR:** Intelligente Tone-Mapping für HDR-Inhalte

### 🚀 **Intelligente Verarbeitung**
- **Smart Detection:** Erkennt bereits kompatible Dateien
- **Selective Processing:** Transkodiert nur was nötig ist
  - `remux_audio`: Nur Audio zu AAC Stereo
  - `transcode_video`: Nur Video zu H.264 
  - `transcode_all`: Vollständige Konvertierung
  - `skip`: Bereits kompatible Dateien

### 📊 **Fortschrittsanzeige**
- **Real-time Progress Bar** mit visueller Anzeige
- **ETA Berechnung** für verbleibende Zeit
- **Performance Metriken** (FPS, Bitrate, Speed)
- **Zeitanzeige** (Current/Total, Elapsed)

### 🌍 **Mehrsprachige Unterstützung**
- **Sprach-Filterung:** Bestimmte Sprachen beibehalten
- **Sprach-Priorisierung:** Reihenfolge der Audio-Streams festlegen
- **Standardisierte Codes:** Automatische Normalisierung von Sprachcodes

### 🔍 **Analyse-Modi**
- **Interaktiver Modus:** Datei-Details anzeigen und Bestätigung
- **Sammelmodus:** CSV-Export aller Datei-Informationen
- **Dry-Run:** Vorschau ohne tatsächliche Konvertierung
- **Debug-Modus:** FFmpeg-Befehle anzeigen

## 📋 Voraussetzungen

### System-Anforderungen
- **Python 3.6+**
- **FFmpeg** und **FFprobe** (im PATH verfügbar)

### FFmpeg Installation

#### macOS (Homebrew)
```bash
brew install ffmpeg
```

#### Ubuntu/Debian
```bash
sudo apt update
sudo apt install ffmpeg
```

#### Windows
1. Download von [ffmpeg.org](https://ffmpeg.org/download.html)
2. FFmpeg zum System PATH hinzufügen

## 🚀 Installation

### Option 1: Direkter Download
```bash
# Skript herunterladen
curl -O https://raw.githubusercontent.com/yourusername/ffmpeg_converter/main/plex_directplay_convert.py

# Ausführbar machen (Linux/macOS)
chmod +x plex_directplay_convert.py
```

### Option 2: Repository klonen
```bash
git clone https://github.com/yourusername/ffmpeg_converter.git
cd ffmpeg_converter
```

## 📖 Verwendung

### Grundlegende Syntax
```bash
python plex_directplay_convert.py <INPUT> [OPTIONS]
```

### 📁 **Ordner verarbeiten (rekursiv)**
```bash
# Alle Videos im Ordner konvertieren
python plex_directplay_convert.py /pfad/zum/video/ordner

# Mit benutzerdefiniertem Ausgabeordner
python plex_directplay_convert.py /pfad/zum/ordner --out /ziel/ordner

# Mit Qualitätseinstellungen
python plex_directplay_convert.py /pfad/zum/ordner --crf 20 --preset fast
```

### 📄 **Einzelne Datei verarbeiten**
```bash
# Einzelne Videodatei konvertieren
python plex_directplay_convert.py /pfad/zur/datei.mkv

# Mit Ausgabeordner
python plex_directplay_convert.py /pfad/zur/datei.mkv --out /ziel/ordner
```

### 🎮 **Interaktiver Modus**
```bash
# Zeigt Details und fragt nach Bestätigung für jede Datei
python plex_directplay_convert.py /pfad/zum/ordner --interactive

# Mit Debug-Informationen (FFmpeg-Befehle)
python plex_directplay_convert.py /pfad/zum/ordner --interactive --debug
```

### 📊 **Analyse-Modus (CSV Export)**
```bash
# Analysiert alle Dateien und erstellt CSV-Report
python plex_directplay_convert.py /pfad/zum/ordner --gather analyse.csv

# Für einzelne Datei
python plex_directplay_convert.py datei.mkv --gather bericht.csv
```

### 🌍 **Sprach-Management**
```bash
# Nur bestimmte Sprachen beibehalten
python plex_directplay_convert.py /ordner --keep-languages de,en,jp

# Sprach-Reihenfolge festlegen (Deutsch zuerst, dann Englisch)
python plex_directplay_convert.py /ordner --sort-languages de,en

# Kombination beider Optionen
python plex_directplay_convert.py /ordner --keep-languages de,en,jp --sort-languages de,en
```

### 🔍 **Dry-Run Modus**
```bash
# Zeigt nur was passieren würde, ohne zu konvertieren
python plex_directplay_convert.py /pfad/zum/ordner --dry-run
```

## ⚙️ Parameter-Referenz

| Parameter | Standard | Beschreibung |
|-----------|----------|--------------|
| `--out` | In-Place | Zielordner für konvertierte Dateien |
| `--crf` | `22` | Video-Qualität (18=verlustlos, 28=komprimiert) |
| `--preset` | `medium` | Encoding-Geschwindigkeit (ultrafast...placebo) |
| `--dry-run` | - | Vorschau ohne Konvertierung |
| `--interactive` | - | Interaktiver Modus mit Bestätigung |
| `--debug` | - | Zeigt FFmpeg-Befehle |
| `--gather` | - | CSV-Analyse-Modus |
| `--keep-languages` | - | Sprachen beibehalten (de,en,jp) |
| `--sort-languages` | - | Sprach-Reihenfolge (de,en) |

## 🎬 Unterstützte Formate

### Input-Formate
- `.mkv`, `.mp4`, `.m4v`, `.mov`
- `.avi`, `.wmv`, `.flv`
- `.ts`, `.m2ts`, `.webm`

### Output-Format
- **Container:** MP4
- **Video:** H.264 (SDR)
- **Audio:** AAC Stereo (192 kbps)

## 📊 Beispiel-Output

### Interaktiver Modus
```
============================================================
📁 Datei: /Movies/Movie.mkv
📏 Größe: 8.2 GB
📦 Container: MKV
🎥 Video Codec: hevc (HDR)
🔊 Audio: dts (6ch, en), ac3 (6ch, de)
💬 Subtitles: en, de
📤 Ausgabe: /Movies/Movie.mp4
🎯 Aktion: Video zu H.264 + HDR→SDR Konvertierung + Audio zu AAC Stereo konvertieren

🔧 FFmpeg Befehl:
   ffmpeg -y -hide_banner -loglevel warning -i "/Movies/Movie.mkv" ...
============================================================
Fortfahren? (j)a / (n)ein / (a)lle / (q)uit: j
```

### Fortschrittsanzeige
```
🎯 transcode HDR→SDR: Movie.mkv -> Movie.mp4 (v:hevc a:dts,ac3)
[████████████░░░░░░░░░░░░░░░░░░] 40.2% | 0:15:20/0:38:10 | ETA: 0:22:50 | 2.1x | 45.2fps
```

### CSV-Analyse
```
Sammelmodus: Analysiere Dateien und speichere in analysis.csv
Gefunden: 156 Videodateien
Analysiere (1/156): Movie1.mkv
Analysiere (2/156): Movie2.mp4
...
Analyse gespeichert in: analysis.csv
Analysierte Dateien: 156
Direct Play kompatibel: 23/156 (14.7%)
```

## 🎯 Optimierungsstrategien

### Qualitätseinstellungen
- **Hohe Qualität:** `--crf 18` (große Dateien)
- **Ausgewogen:** `--crf 22` (Standard)
- **Kompakt:** `--crf 28` (kleine Dateien)

### Geschwindigkeitseinstellungen
- **Schnell:** `--preset ultrafast` (große Dateien)
- **Ausgewogen:** `--preset medium` (Standard)
- **Effizient:** `--preset slow` (beste Kompression)

### Batch-Verarbeitung
```bash
# Große Sammlung mit optimalen Einstellungen
python plex_directplay_convert.py /media/movies \
  --out /converted/movies \
  --crf 22 \
  --preset medium \
  --keep-languages de,en \
  --sort-languages de,en
```

## 🔧 Technische Details

### HDR zu SDR Konvertierung
Das Skript verwendet fortschrittliche Tone-Mapping-Techniken:
```bash
-vf "zscale=t=linear:npl=100,format=gbrpf32le,zscale=p=bt709,tonemap=tonemap=hable:desat=0,zscale=t=bt709:m=bt709:r=tv,format=yuv420p"
-color_primaries bt709 -color_trc bt709 -colorspace bt709
```

### Sprach-Normalisierung
Unterstützte Sprachcodes:
- **Deutsch:** `de`, `deu`, `ger`, `german`, `deutsch`
- **Englisch:** `en`, `eng`, `english`
- **Japanisch:** `jp`, `ja`, `jpn`, `japanese`
- **Französisch:** `fr`, `fra`, `fre`, `french`
- **Spanisch:** `es`, `esp`, `spa`, `spanish`
- **Italienisch:** `it`, `ita`, `italian`

## 🐛 Problembehandlung

### FFmpeg nicht gefunden
```bash
# Prüfen ob FFmpeg installiert ist
ffmpeg -version
ffprobe -version

# PATH prüfen (Linux/macOS)
which ffmpeg
which ffprobe
```

### Unvollständige Konvertierung
- Prüfe verfügbaren Speicherplatz
- Stelle sicher, dass die Eingabedatei nicht beschädigt ist
- Verwende `--debug` für detaillierte FFmpeg-Ausgabe

### Performance-Probleme
- Verwende `--preset ultrafast` für schnellere Konvertierung
- Reduziere `--crf` Wert für bessere Performance
- Schließe andere ressourcenintensive Programme

## 📄 CSV-Analyse Format

Die CSV-Ausgabe enthält folgende Spalten:

| Spalte | Beschreibung |
|--------|--------------|
| `file_path` | Vollständiger Dateipfad |
| `file_name` | Dateiname |
| `file_size_mb` | Dateigröße in MB |
| `container` | Container-Format |
| `video_codec` | Video-Codec |
| `is_hdr` | HDR-Inhalt erkannt |
| `audio_codecs` | Audio-Codecs |
| `audio_channels` | Kanal-Konfiguration |
| `direct_play_compatible` | Apple TV kompatibel |
| `action_needed` | Erforderliche Aktion |

## 📚 Erweiterte Beispiele

### Produktions-Pipeline
```bash
#!/bin/bash
# Vollautomatische Konvertierung für Plex-Server

# 1. Analyse durchführen
python plex_directplay_convert.py /media/raw --gather analysis.csv

# 2. Inkompatible Dateien konvertieren
python plex_directplay_convert.py /media/raw \
  --out /media/converted \
  --crf 20 \
  --preset medium \
  --keep-languages de,en \
  --sort-languages de,en

# 3. Ergebnisse überprüfen
python plex_directplay_convert.py /media/converted --gather final_report.csv
```

### Interaktive Qualitätskontrolle
```bash
# Einzelne Dateien mit maximaler Kontrolle
python plex_directplay_convert.py /path/to/movie.mkv \
  --interactive \
  --debug \
  --crf 18 \
  --preset slow
```

## 🤝 Beitragen

1. Fork das Repository
2. Erstelle einen Feature-Branch (`git checkout -b feature/amazing-feature`)
3. Commit deine Änderungen (`git commit -m 'Add amazing feature'`)
4. Push zum Branch (`git push origin feature/amazing-feature`)
5. Öffne eine Pull Request

## 📝 Lizenz

Dieses Projekt steht unter der MIT-Lizenz. Siehe [LICENSE](LICENSE) für Details.

## 🙏 Danksagungen

- **FFmpeg-Team** für das fantastische Multimedia-Framework
- **Plex-Community** für DirectPlay-Kompatibilitäts-Insights
- **Apple TV-Nutzer** für Feedback zur Kompatibilität

## 📞 Support

- 🐛 **Bug Reports:** [GitHub Issues](https://github.com/yourusername/ffmpeg_converter/issues)
- 💡 **Feature Requests:** [GitHub Discussions](https://github.com/yourusername/ffmpeg_converter/discussions)
- 📧 **Direkter Kontakt:** your.email@example.com

---

**⭐ Gefällt dir das Projekt? Gib uns einen Stern auf GitHub!**
