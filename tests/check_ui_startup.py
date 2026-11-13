"""Weight-free Qt startup/language checks; no participant data are used."""
from pathlib import Path
import json
import os
import sys
import tempfile

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QFontDatabase
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication
from matplotlib import style
from app import Window


def main():
    application = QApplication([])
    font = Path(r'C:\Windows\Fonts\msyh.ttc')
    if font.exists():
        QFontDatabase.addApplicationFont(str(font))
    application.setFont(QFont('Microsoft YaHei', 9))
    style.use(str(ROOT / 'assets/openscience.mplstyle'))
    qa = ROOT / 'qa'; qa.mkdir(exist_ok=True)
    checks = []
    with tempfile.TemporaryDirectory(dir=qa) as temporary:
        preferences = Path(temporary) / 'settings.local.json'
        window = Window(language='en', settings_path=preferences)
        window.show(); application.processEvents(); QTest.qWait(150)
        assert window.run_btn.text() == 'Run segmentation + MWT'; checks.append('English startup')
        assert window.case is None and window.measurement is None; checks.append('No implicit case/data loading')
        baseline = window.ref.evaluate(10, 'Female', 50, 165, 60)
        for language in ['zh', 'en']:
            selector = window.language_choice
            QTest.mouseClick(selector.buttons[selector.findData(language)], Qt.MouseButton.LeftButton)
            application.processEvents(); QTest.qWait(150)
            assert window.ui.language == language; checks.append('Mouse-event language selection ' + language)
            assert window.ref.evaluate(10, 'Female', 50, 165, 60) == baseline; checks.append('Reference values retained ' + language)
            assert json.loads(preferences.read_text(encoding='utf-8'))['language'] == language; checks.append('Preference saved ' + language)
        window.grab().save(str(qa / 'public_ui_startup.png'))
        window.close(); application.processEvents()
    result = dict(status='PASS', checks=checks, platform=os.environ.get('QT_QPA_PLATFORM'),
                  scope='Startup and empty-state bilingual interaction; no inference, clinical case or new desktop acceptance claim.')
    (qa / 'public_ui_check.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
