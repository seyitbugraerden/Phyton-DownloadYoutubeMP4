#!/bin/zsh
cd "${0:A:h}" || exit 1
if [[ ! -x .venv/bin/python ]]; then
  echo "Önce README.md dosyasındaki kurulumu tamamla."
  read "?Kapatmak için Enter…"
  exit 1
fi
.venv/bin/python app.py
