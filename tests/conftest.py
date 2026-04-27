"""Общая настройка pytest."""

import sys
from pathlib import Path

# Добавляем корень проекта в PYTHONPATH, чтобы импорты app.* работали из тестов
sys.path.insert(0, str(Path(__file__).parent.parent))
