"""In-place Qt translation bindings: no widget rebuild and no data-key changes."""
import json
from pathlib import Path
from PyQt6.QtCore import QLibraryInfo,QTranslator,pyqtSignal
from PyQt6.QtWidgets import (QApplication,QLabel,QPushButton,QCheckBox,QGroupBox,
                            QLineEdit,QDoubleSpinBox,QComboBox,QTabWidget,QWidget,QHBoxLayout,QRadioButton,QButtonGroup)
from core.common import APP_ROOT,write_json
from core.i18n import Translator,LANGUAGES

class LanguageSelector(QWidget):
    """Two explicit, keyboard-accessible choices; no transient popup window."""
    currentIndexChanged=pyqtSignal(int)
    def __init__(self,parent=None):
        super().__init__(parent);self.buttons=[];self.values=[];self.group=QButtonGroup(self)
        self.row=QHBoxLayout(self);self.row.setContentsMargins(4,0,4,0);self.row.setSpacing(10)
        self.group.idToggled.connect(lambda index,checked:self.currentIndexChanged.emit(index) if checked else None)
    def addItem(self,text,value):
        button=QRadioButton(text,self);self.group.addButton(button,len(self.buttons));self.buttons.append(button);self.values.append(value);self.row.addWidget(button)
    def findData(self,value):return self.values.index(value) if value in self.values else -1
    def currentData(self):
        index=self.group.checkedId();return self.values[index] if index>=0 else None
    def setCurrentIndex(self,index):
        if 0<=index<len(self.buttons):self.buttons[index].setChecked(True)

def preferred_language(path=None):
    p=Path(path or APP_ROOT/'ui_settings.local.json')
    try:
        if p.stat().st_size>32000:return 'zh'
        value=json.loads(p.read_text(encoding='utf-8')).get('language','zh')
        return value if value in LANGUAGES else 'zh'
    except (OSError,ValueError,AttributeError):return 'zh'

class LocalizedUI(Translator):
    def __init__(self,language):
        super().__init__(language);self.bindings={};self.combos=[];self.tabs=[];self.qt_translator=None

    def bind(self,widget,setter,source):
        self.bindings[(widget,setter)]=source
        getattr(widget,setter)(self.message(source))

    def set_text(self,widget,source):self.bind(widget,'setText',source)
    def set_format(self,widget,source):self.bind(widget,'setFormat',source)
    def source(self,widget,setter='setText'):return self.bindings.get((widget,setter),'')

    def attach(self,root,exclude=()):
        for widget in root.findChildren(QLabel)+root.findChildren(QPushButton)+root.findChildren(QCheckBox):
            if widget not in exclude:self.bind(widget,'setText',widget.text())
        for widget in root.findChildren(QGroupBox):self.bind(widget,'setTitle',widget.title())
        for widget in root.findChildren(QLineEdit):
            if widget.placeholderText():self.bind(widget,'setPlaceholderText',widget.placeholderText())
        for widget in root.findChildren(QDoubleSpinBox):
            if widget.suffix():self.bind(widget,'setSuffix',widget.suffix())
        for widget in root.findChildren(QComboBox):
            if widget not in exclude:self.combos.append((widget,[widget.itemText(i) for i in range(widget.count())]))
        for widget in root.findChildren(QTabWidget):self.tabs.append((widget,[widget.tabText(i) for i in range(widget.count())]))
        self.refresh()

    def refresh(self):
        for (widget,setter),source in self.bindings.items():getattr(widget,setter)(self.message(source))
        for widget,items in self.combos:
            blocked=widget.blockSignals(True)
            for i,source in enumerate(items):widget.setItemText(i,self.message(source))
            widget.blockSignals(blocked)
        for widget,items in self.tabs:
            for i,source in enumerate(items):widget.setTabText(i,self.message(source))

    def set_language(self,language):
        if language not in LANGUAGES:raise ValueError('Unsupported UI language: '+str(language))
        self.language=language
        app=QApplication.instance()
        if self.qt_translator is not None:
            app.removeTranslator(self.qt_translator);self.qt_translator.deleteLater()
        self.qt_translator=None
        if language=='zh':
            translator=QTranslator(app)
            if translator.load('qtbase_zh_CN',QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath)):
                app.installTranslator(translator);self.qt_translator=translator
        self.refresh()

def save_language(language,path=None):
    p=Path(path or APP_ROOT/'ui_settings.local.json');data={}
    try:
        if p.exists() and p.stat().st_size<32000:
            previous=json.loads(p.read_text(encoding='utf-8'))
            if isinstance(previous,dict):data=previous
    except (OSError,ValueError):pass
    data['language']=language;write_json(p,data)
