#!/usr/bin/env python3
"""Interactive local CineSAX segmentation → study MWT → frozen reference UI."""
from pathlib import Path
import argparse
import csv
import json
import os
import sys
import traceback
import numpy as np

from PyQt6.QtCore import Qt,QThread,pyqtSignal,QTimer,QUrl
from PyQt6.QtGui import QFont,QFontDatabase,QDesktopServices
from PyQt6.QtWidgets import (QApplication,QMainWindow,QWidget,QVBoxLayout,QHBoxLayout,QGridLayout,QFormLayout,
    QLabel,QLineEdit,QPushButton,QComboBox,QDoubleSpinBox,QSpinBox,QCheckBox,QGroupBox,QFileDialog,QMessageBox,
    QProgressBar,QTextEdit,QScrollArea,QSplitter,QTabWidget,QTableWidget,QTableWidgetItem,QHeaderView,QSlider,QDialog,QDialogButtonBox)

import matplotlib
matplotlib.use('QtAgg')
from matplotlib.figure import Figure
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.transforms import Affine2D
from matplotlib.colors import ListedColormap
from matplotlib import style
from matplotlib.font_manager import FontProperties

from core.common import APP_ROOT,VERSION,Cancelled,make_run,write_json,clean
from core.images import load_case,InputAmbiguity
from core.importers import selection_paths
from core.measurement import measure_case,detect_rvip
from core.reference import ReferenceModel
from core.reports import export_analysis,export_segmentation_only,read_project
from vendor import study_engine as study
from ui_localization import LocalizedUI,LanguageSelector,preferred_language,save_language

QSS='''
QMainWindow,QWidget#root{background:#f4f7fb;color:#1e293b}
QGroupBox{font-weight:bold;border:1px solid #d5deeb;border-radius:8px;margin-top:13px;padding-top:14px;background:white}
QGroupBox::title{subcontrol-origin:margin;left:12px;padding:0 4px;color:#335077}
QLineEdit,QComboBox,QSpinBox,QDoubleSpinBox{background:white;border:1px solid #cbd5e1;border-radius:5px;padding:5px;min-height:22px}
QPushButton{background:#e7eef8;color:#25436a;border:1px solid #cbd8eb;border-radius:6px;padding:6px 10px;min-height:23px}
QPushButton:hover{background:#d5e4f6} QPushButton:disabled{color:#94a3b8;background:#edf1f6}
QPushButton#primary{background:#2a78d6;color:white;font-weight:bold;border:0;padding:10px}
QPushButton#primary:hover{background:#2066b8} QPushButton#cancel{color:#b53d42;background:#fff0f0}
QTabWidget::pane{border:1px solid #d9e2ef;background:white;border-radius:6px}
QTabBar::tab{background:#e8eef7;padding:8px 18px;margin-right:3px}QTabBar::tab:selected{background:white;color:#256abf;font-weight:bold}
QProgressBar{border:1px solid #d7e0ec;border-radius:5px;background:white;text-align:center;min-height:17px}
QProgressBar::chunk{background:#1baf7a;border-radius:4px}QTextEdit{border:1px solid #d9e2ef;background:#fbfcfe}
QLabel#card{background:white;border:1px solid #d5deeb;border-radius:8px;padding:9px;min-height:57px}
QTableWidget{gridline-color:#e4eaf2;border:0;background:white;selection-background-color:#dcecff;color:#253448}
'''

class Worker(QThread):
    progress=pyqtSignal(int,int,str)
    message=pyqtSignal(str)
    succeeded=pyqtSignal(object)
    failed=pyqtSignal(str,bool)
    needs_input=pyqtSignal(object)
    def __init__(self,fn,parent=None):super().__init__(parent);self.fn=fn;self.cancelled=False
    def run(self):
        try:self.succeeded.emit(self.fn(self))
        except Cancelled as e:self.failed.emit(str(e),True)
        except InputAmbiguity as e:self.needs_input.emit(e)
        except Exception:self.failed.emit(traceback.format_exc(),False)

class ImageCanvas(FigureCanvasQTAgg):
    point_selected=pyqtSignal(float,float)
    moved=pyqtSignal(float,float)
    zoomed=pyqtSignal(float)
    def __init__(self,translator):
        self.tr=translator
        font=Path(r'C:\Windows\Fonts\msyh.ttc')
        self.font=FontProperties(fname=str(font)) if font.exists() else FontProperties(family=['Microsoft YaHei','Noto Sans CJK SC','DejaVu Sans'])
        self.fig=Figure(figsize=(10,4.3),facecolor='white')
        self.axes=self.fig.subplots(1,3);self.fig.subplots_adjust(left=.015,right=.99,top=.84,bottom=.08,wspace=.06)
        super().__init__(self.fig);self.setMinimumHeight(275);self.M=None;self.drag=None;self.editing=False
        self.mpl_connect('button_press_event',self.press);self.mpl_connect('button_release_event',self.release)
        self.mpl_connect('motion_notify_event',self.motion);self.mpl_connect('scroll_event',self.scroll)
        self.empty()
    def _font(self,size,weight='normal'):
        font=self.font.copy();font.set_size(size);font.set_weight(weight);return font
    def empty(self,message='Load one CineSAX series'):
        for a,t in zip(self.axes,['Original cine','Segmentation','Thickness sampling']):
            a.clear();a.set_title(self.tr(t),fontproperties=self._font(11,'bold'));a.set_facecolor('#f1f5fa');a.set_xticks([]);a.set_yticks([])
            a.text(.5,.5,self.tr(message),ha='center',va='center',transform=a.transAxes,color='#8291a6',fontproperties=self._font(10))
        self.draw_idle()
    def press(self,e):
        if e.inaxes not in self.axes or e.xdata is None:return
        if self.editing and self.M is not None:
            rc=np.linalg.inv(self.M)@np.array([e.xdata,e.ydata,1.]);self.point_selected.emit(float(rc[0]),float(rc[1]));return
        if e.button==1:self.drag=(e.x,e.y)
    def motion(self,e):
        if self.drag and e.inaxes in self.axes:
            dx=e.x-self.drag[0];dy=e.y-self.drag[1];self.drag=(e.x,e.y)
            ax=e.inaxes;fov=ax.get_xlim()[1]-ax.get_xlim()[0];self.moved.emit(-dx/ax.bbox.width*fov,dy/ax.bbox.height*fov)
    def release(self,e):self.drag=None
    def scroll(self,e):
        if e.inaxes in self.axes:self.zoomed.emit(.85 if e.button=='up' else 1/.85)
    def show_plane(self,p,mask,td,view,ed_frame):
        h,w=p.image.shape;sr,sc=p.spacing
        center=np.asarray(view.get('center_rc',[(h-1)/2,(w-1)/2]),float)
        B=np.array([[0,sc,-center[1]*sc],[sr,0,-center[0]*sr],[0,0,1.]])
        theta=np.deg2rad(view['rotation']);R=np.array([[np.cos(theta),-np.sin(theta),0],[np.sin(theta),np.cos(theta),0],[0,0,1]])
        F=np.diag([-1 if view['flip_h'] else 1,-1 if view['flip_v'] else 1,1]);self.M=F@R@B
        swap=np.array([[0,1,0],[1,0,0],[0,0,1.]])
        imtransform=Affine2D(self.M@swap)
        fov=view['fov'];px,py=view['pan_x'],view['pan_y']
        ww=max(view['ww'],1e-6);vmin=view['wl']-ww/2;vmax=view['wl']+ww/2
        cmap=ListedColormap([(0,0,0,0),(0.92,.29,.28,.28),(.16,.47,.84,.24),(.11,.69,.48,.25)])
        def coords(a):return np.asarray(a)@self.M[:2,:2].T+self.M[:2,2]
        for i,(ax,title) in enumerate(zip(self.axes,['Original cine','Segmentation','Thickness sampling'])):
            ax.clear();ax.set_title(self.tr(title),pad=9,fontproperties=self._font(11,'bold'))
            background=i<2 or view['thickness_background'];ax.set_facecolor('black' if background else 'white')
            if background:ax.imshow(p.image,cmap='gray',vmin=vmin,vmax=vmax,origin='upper',transform=imtransform+ax.transData,interpolation='nearest')
            if i==1 and mask is not None and view['show_fill']:ax.imshow(mask,cmap=cmap,vmin=0,vmax=3,origin='upper',transform=imtransform+ax.transData,interpolation='nearest')
            if i>=1 and td is not None:
                for key,color in [('endo_smooth_full','#2a78d6'),('epi_smooth_full','#1baf7a')]:
                    c=coords(td[key]);ax.plot(np.r_[c[:,0],c[0,0]],np.r_[c[:,1],c[0,1]],color=color,lw=1.2)
                if i==2:
                    a,b=coords(td['endo_pts']),coords(td['epi_pts']);ids=np.unique(np.linspace(0,len(a)-1,view['rays']).astype(int))
                    for j in ids:ax.plot([a[j,0],b[j,0]],[a[j,1],b[j,1]],c='#929da8',lw=.65,ls='--')
                    j=int(td['max_idx']);ax.plot([a[j,0],b[j,0]],[a[j,1],b[j,1]],c='#e34948',lw=2.2)
                    ax.text(.02,.03,self.tr('Slice max: {value} mm',value=f"{td['max_thickness']:.2f}"),transform=ax.transAxes,color='white' if background else '#263444',fontproperties=self._font(9),
                            bbox=dict(fc='black' if background else 'white',alpha=.7,ec='none'))
                if 'rvip' in td and view['show_points']:
                    points=coords(td['rvip']);ax.scatter(points[:,0],points[:,1],s=25,c=['#eda100','#eb6834'],edgecolors='white',linewidths=.5)
            elif i==1 and mask is not None:
                from skimage.measure import find_contours
                for region,col in [(mask==2,'#2a78d6'),(np.isin(mask,[1,2]),'#1baf7a')]:
                    for c in find_contours(region.astype(float),.5):
                        q=coords(c);ax.plot(q[:,0],q[:,1],c=col,lw=1)
            ax.set_xlim(px-fov/2,px+fov/2);ax.set_ylim(py+fov/2,py-fov/2);ax.set_aspect('equal');ax.set_xticks([]);ax.set_yticks([])
            if i==0:
                color='white';x=px-fov*.42;y=py+fov*.40
                ax.plot([x,x+10],[y,y],c=color,lw=2);ax.text(x,y-fov*.025,'10 mm',color=color,fontsize=8)
        self.draw_idle()

class Window(QMainWindow):
    def __init__(self,language=None,settings_path=None):
        super().__init__();self.setWindowTitle('LVWT CineSAX Workbench · '+VERSION)
        self.settings_path=settings_path;self.ui=LocalizedUI(language or preferred_language(settings_path));self.log_entries=[]
        self.case=None;self.measurement=None;self.reference_result=None;self.worker=None;self.pending_project=None
        self.ref=ReferenceModel();self.manual_rvip={};self.point_mode=None;self.pending_points={};self.ed_override=None;self.last_run=None
        self.demographic_source=None
        self.selected_inputs=[];self.selection_display=None;self.input_organization='auto'
        self.view=dict(rotation=0,flip_h=False,flip_v=False,fov=160.,pan_x=0.,pan_y=0.,wl=500.,ww=1000.,rays=24,show_fill=True,show_points=True,thickness_background=False)
        self._build();self.setStyleSheet(QSS);self._sync_cards();self.resize(1480,920);self.setMinimumSize(1060,700)
        self.ui.attach(self,exclude=[self.language_choice,*[item[0] for item in self.cards.values()]])
        self._retranslate()
        self.language_choice.currentIndexChanged.connect(self.change_language)
        self.input.textChanged.connect(self._input_changed);self.masks.textChanged.connect(self._input_changed);self.use_json.toggled.connect(self._mask_changed)
        self.play_timer=QTimer(self);self.play_timer.timeout.connect(self._next_frame)
        self.setAcceptDrops(True)
    def _build(self):
        root=QWidget();root.setObjectName('root');layout=QVBoxLayout(root);layout.setContentsMargins(14,10,14,10);layout.setSpacing(9)
        header=QHBoxLayout();title=QLabel('LVWT  /  CineSAX Research Workbench');title.setStyleSheet('font-size:19px;font-weight:700;color:#173b68');header.addWidget(title)
        header.addStretch();header.addWidget(QLabel('语言 / Language'))
        self.language_choice=LanguageSelector();self.language_choice.setObjectName('languageChoice');self.language_choice.addItem('中文','zh');self.language_choice.addItem('English','en');self.language_choice.setCurrentIndex(self.language_choice.findData(self.ui.language));header.addWidget(self.language_choice)
        self.status=QLabel('READY · 研究原型');self.status.setStyleSheet('color:#24785d;font-weight:bold');header.addWidget(self.status);layout.addLayout(header)
        self.stages=QLabel('01 载入图像   →   02 自动分割   →   03 ED / MWT   →   04 人口学参照');self.stages.setStyleSheet('color:#6c7f98;padding:4px');layout.addWidget(self.stages)
        split=QSplitter();sidebar=QWidget();left=QVBoxLayout(sidebar);left.setContentsMargins(0,0,8,0)
        self.input=QLineEdit();self.input.setPlaceholderText('选择或拖入DICOM / NIfTI（支持多选）')
        self.masks=QLineEdit();self.masks.setPlaceholderText('可选：独立ROI文件夹')
        self.output=QLineEdit(str(APP_ROOT/'outputs'))
        self.weights=QLineEdit(str(APP_ROOT/'weights/Multi-20260908.pth'))
        group=QGroupBox('输入与输出');g=QVBoxLayout(group)
        for label,edit,mode in [('图像输入',self.input,'input'),('已有ROI目录（可选）',self.masks,'masks'),('输出目录',self.output,'output'),('分割权重',self.weights,'weights')]:
            edit.setAcceptDrops(False)
            g.addWidget(QLabel(label));row=QHBoxLayout();row.addWidget(edit);btn=QPushButton('…');btn.setMaximumWidth(34);btn.clicked.connect(lambda checked=False,m=mode:self._browse(m));row.addWidget(btn)
            if mode=='input':
                btn.setText('文件');btn.setMaximumWidth(64)
                self.choose_files_btn=btn;folder=QPushButton('文件夹');folder.clicked.connect(self.choose_input_folder);row.addWidget(folder);self.choose_folder_btn=folder
            g.addLayout(row)
            if mode=='input':
                self.input_summary=QLabel('可拖入单张、多张单帧或多层多帧影像。');self.input_summary.setWordWrap(True);self.input_summary.setStyleSheet('color:#657992;font-size:9pt');g.addWidget(self.input_summary)
        row=QHBoxLayout();self.load_btn=QPushButton('载入病例');self.load_btn.clicked.connect(self.load_input);row.addWidget(self.load_btn)
        self.open_project_btn=QPushButton('打开项目');self.open_project_btn.clicked.connect(self.open_project);row.addWidget(self.open_project_btn)
        self.input_list_btn=QPushButton('输入清单');self.input_list_btn.clicked.connect(self.show_input_list);row.addWidget(self.input_list_btn);g.addLayout(row);left.addWidget(group);input_group=group
        group=QGroupBox('分割设置');f=QFormLayout(group);self.device=QComboBox();self.device.addItem('自动（优先CUDA）','auto');self.device.addItem('CUDA GPU','cuda');self.device.addItem('CPU','cpu');f.addRow('计算设备',self.device)
        self.pp=[]
        for text in ['连通域约束','LV腔包含约束','间隙填充']:
            b=QCheckBox(text);b.setChecked(True);f.addRow(b);self.pp.append(b)
        self.mask_mode=QComboBox();self.mask_mode.addItem('已有ROI','existing');self.mask_mode.addItem('后处理预测','post');self.mask_mode.addItem('原始预测','raw');self.mask_mode.currentIndexChanged.connect(self._mask_changed);f.addRow('测量来源',self.mask_mode)
        self.use_json=QCheckBox('已有ROI优先使用配对JSON插入点');self.use_json.setChecked(True);f.addRow(self.use_json);left.addWidget(group);seg_group=group
        group=QGroupBox('人口学输入');f=QFormLayout(group);self.sex=QComboBox();self.sex.addItem('请选择',None);self.sex.addItem('男','Male');self.sex.addItem('女','Female')
        self.age=QDoubleSpinBox();self.age.setRange(0,120);self.age.setDecimals(1);self.age.setSuffix(' 岁')
        self.height_input=QDoubleSpinBox();self.height_input.setRange(0,250);self.height_input.setDecimals(1);self.height_input.setSuffix(' cm')
        self.weight=QDoubleSpinBox();self.weight.setRange(0,400);self.weight.setDecimals(1);self.weight.setSuffix(' kg')
        for label,w in [('模型性别',self.sex),('年龄',self.age),('身高',self.height_input),('体重',self.weight)]:f.addRow(label,w)
        self.sex.currentIndexChanged.connect(self.update_reference)
        for w in [self.age,self.height_input,self.weight]:w.valueChanged.connect(self.update_reference)
        self.demo_info=QLabel('BSA —  ·  BMI —');self.demo_info.setWordWrap(True);f.addRow(self.demo_info);left.addWidget(group);demo_group=group
        self.run_btn=QPushButton('运行分割 + MWT');self.run_btn.setObjectName('primary');self.run_btn.clicked.connect(self.run_pipeline)
        self.measure_btn=QPushButton('使用当前ROI计算厚度');self.measure_btn.clicked.connect(self.measure_current)
        row=QHBoxLayout();self.export_btn=QPushButton('保存项目 / 报告');self.export_btn.clicked.connect(self.export_result);row.addWidget(self.export_btn)
        self.cancel_btn=QPushButton('取消');self.cancel_btn.setObjectName('cancel');self.cancel_btn.setEnabled(False);self.cancel_btn.clicked.connect(self.cancel);row.addWidget(self.cancel_btn);actions=row;actions.insertWidget(0,self.run_btn);actions.insertWidget(1,self.measure_btn)
        for g0 in [input_group,seg_group,demo_group]:left.removeWidget(g0)
        self.side_tabs=QTabWidget();tab_input=QWidget();ti=QVBoxLayout(tab_input);ti.setContentsMargins(4,3,4,3);ti.addWidget(input_group);ti.addWidget(seg_group);ti.addStretch()
        tab_demo=QWidget();td=QVBoxLayout(tab_demo);td.setContentsMargins(4,3,4,3);td.addWidget(demo_group)
        hint=QLabel('参考结果\n\nμ：相同年龄、性别和BSA的预期正常MWT。\n\nUL：冻结模型的正常上参考限。\n\nZ：(实测MWT − μ) / 性别特异残差SD。\n\n改变人口学输入会立即更新参照值，不需要重新分割。');hint.setWordWrap(True);hint.setStyleSheet('color:#6a7f99;padding:10px');td.addWidget(hint);td.addStretch()
        self.side_tabs.addTab(tab_input,'病例 / 分割');self.side_tabs.addTab(tab_demo,'人口学参照');left.addWidget(self.side_tabs,1)
        note=QLabel('输出保存在独立run目录。超限状态不是HCM诊断。');note.setWordWrap(True);note.setStyleSheet('color:#7b8798;font-size:9pt');left.addWidget(note)
        scroll=QScrollArea();scroll.setWidgetResizable(True);scroll.setWidget(sidebar);scroll.setMinimumWidth(295);scroll.setMaximumWidth(390);split.addWidget(scroll)
        right=QWidget();r=QVBoxLayout(right);r.setContentsMargins(5,0,0,0);r.setSpacing(8)
        cardrow=QHBoxLayout();self.cards={}
        for key,name in [('mwt','实测 MWT'),('mu','预期正常 μ'),('ul','正常上限 UL'),('z','标准化 Z')]:
            c=QLabel();c.setObjectName('card');c.setTextFormat(Qt.TextFormat.RichText);self.cards[key]=(c,name);cardrow.addWidget(c)
        r.addLayout(cardrow);self.result_note=QLabel('载入影像后，可运行分割或使用已有ROI。');self.result_note.setWordWrap(True);self.result_note.setStyleSheet('color:#657992;padding:3px');r.addWidget(self.result_note)
        self.tabs=QTabWidget();imtab=QWidget();im=QVBoxLayout(imtab);im.setContentsMargins(5,5,5,5)
        self.selection_label=QLabel('当前层面 / 时相：—');self.selection_label.setAlignment(Qt.AlignmentFlag.AlignCenter);self.selection_label.setStyleSheet('color:#647f9e;font-size:9pt');im.addWidget(self.selection_label)
        self.canvas=ImageCanvas(self.ui);im.addWidget(self.canvas,1)
        self.canvas.moved.connect(self._pan);self.canvas.zoomed.connect(self._zoom);self.canvas.point_selected.connect(self._point)
        for typ in ['slice','frame']:
            row=QHBoxLayout();lab=QLabel('层面' if typ=='slice' else '时相');lab.setMinimumWidth(45);row.addWidget(lab)
            sl=QSlider(Qt.Orientation.Horizontal);sl.setRange(0,0);value=QLabel('—');value.setMinimumWidth(130);row.addWidget(sl,1);row.addWidget(value);im.addLayout(row)
            setattr(self,typ+'_slider',sl);setattr(self,typ+'_label',value);sl.valueChanged.connect(self.redraw)
        row=QHBoxLayout()
        for title,fn in [('定位最大层',self.goto_max),('设当前为ED',self.set_ed),('自动ED',self.reset_ed),('播放/暂停',self.play)]:
            b=QPushButton(title);b.clicked.connect(fn);row.addWidget(b)
        im.addLayout(row)
        viewbox=QGroupBox('视图（不改变测量）');vl=QGridLayout(viewbox)
        self.fov=QDoubleSpinBox();self.fov.setRange(25,500);self.fov.setValue(160);self.fov.setSuffix(' mm');self.fov.valueChanged.connect(lambda v:self._view_changed('fov',v))
        self.wl=QDoubleSpinBox();self.wl.setRange(-100000,100000);self.wl.setValue(500);self.wl.valueChanged.connect(lambda v:self._view_changed('wl',v))
        self.ww=QDoubleSpinBox();self.ww.setRange(.1,200000);self.ww.setValue(1000);self.ww.valueChanged.connect(lambda v:self._view_changed('ww',v))
        self.rotation=QComboBox();[self.rotation.addItem(str(v)+'°',v) for v in [0,90,180,270]];self.rotation.currentIndexChanged.connect(lambda:self._view_changed('rotation',self.rotation.currentData()))
        for i,(name,w) in enumerate([('FOV',self.fov),('窗位',self.wl),('窗宽',self.ww),('旋转',self.rotation)]):vl.addWidget(QLabel(name),0,2*i);vl.addWidget(w,0,2*i+1)
        self.flip_h=QCheckBox('左右翻转');self.flip_v=QCheckBox('上下翻转');self.fill=QCheckBox('标签填充');self.fill.setChecked(True);self.bg=QCheckBox('厚度叠图')
        for i,(w,key) in enumerate([(self.flip_h,'flip_h'),(self.flip_v,'flip_v'),(self.fill,'show_fill'),(self.bg,'thickness_background')]):w.toggled.connect(lambda b,k=key:self._view_changed(k,b));vl.addWidget(w,1,i*2,1,2)
        center=QPushButton('居中左室');center.clicked.connect(self.center_lv);fit=QPushButton('适配全图');fit.clicked.connect(self.fit_image);vl.addWidget(center,2,0,1,4);vl.addWidget(fit,2,4,1,4)
        im.addWidget(viewbox);self.tabs.addTab(imtab,'影像与测量')
        tabletab=QWidget();tl=QVBoxLayout(tabletab);self.table=QTableWidget(0,5);self.table.setHorizontalHeaderLabels(['层面','ED帧','最大厚度 mm','RVIP来源','状态']);self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents);self.table.horizontalHeader().setStretchLastSection(True);self.table.cellClicked.connect(self.table_select);tl.addWidget(self.table)
        row=QHBoxLayout()
        for title,mode in [('标记前插入点','anterior'),('标记后插入点','posterior')]:
            b=QPushButton(title);b.clicked.connect(lambda checked=False,m=mode:self.set_point_mode(m));row.addWidget(b)
        b=QPushButton('清除手动插入点');b.clicked.connect(self.clear_points);row.addWidget(b);tl.addLayout(row);self.tabs.addTab(tabletab,'层面数据 / 插入点')
        self.log=QTextEdit();self.log.setReadOnly(True);self.log.setAcceptDrops(False);self.log.viewport().setAcceptDrops(False);self.tabs.addTab(self.log,'运行记录');r.addWidget(self.tabs,1)
        self.coverage=QLabel('有效层面 / ED / 像素间距将在载入后显示。');self.coverage.setWordWrap(True);self.coverage.setStyleSheet('color:#657992;font-size:9pt');r.addWidget(self.coverage)
        split.addWidget(right);split.setStretchFactor(1,1);layout.addWidget(split,1)
        layout.addLayout(actions);self.progress=QProgressBar();self.progress.setValue(0);layout.addWidget(self.progress);self.setCentralWidget(root)
        self.locks=[self.language_choice,self.input,self.choose_files_btn,self.choose_folder_btn,self.input_list_btn,self.masks,self.output,self.weights,self.device,self.load_btn,self.open_project_btn,self.run_btn,self.measure_btn,self.export_btn,self.mask_mode,self.use_json,self.age,self.sex,self.height_input,self.weight,*self.pp]
    def change_language(self,*args):
        # Apply after the input event so Qt finishes updating the selection first.
        QTimer.singleShot(0,self._apply_language_choice)
    def _apply_language_choice(self):
        if self.language_choice.currentData()==self.ui.language:return
        self.ui.language=self.language_choice.currentData();self._retranslate()
        try:save_language(self.ui.language,self.settings_path)
        except OSError as error:self.logmsg('语言偏好未能保存：'+str(error))
    def _retranslate(self):
        self.ui.set_language(self.ui.language)
        self._refresh_input_display()
        self.table.setHorizontalHeaderLabels([self.ui(x) for x in ['层面','ED帧','最大厚度 mm','RVIP来源','状态']])
        self._sync_cards()
        if self.measurement:self._table()
        if self.case and self._input_matches():self.redraw()
        else:self.canvas.empty()
        if self.point_mode:self.ui.set_text(self.result_note,'请在影像上点击'+('前' if self.point_mode=='anterior' else '后')+'RV插入点；之后重新计算。')
        self.log.setPlainText('\n'.join(self.ui.message(s) for s in self.log_entries))
        self.log.verticalScrollBar().setValue(self.log.verticalScrollBar().maximum())
    def current_inputs(self):
        if self.selected_inputs and self.input.text()==self.selection_display:return list(self.selected_inputs)
        text=self.input.text().strip().strip('"')
        return selection_paths([text]) if text else []
    def _refresh_input_display(self):
        if self.selected_inputs and self.input.text()==self.selection_display:
            self.selection_display=self.selected_inputs[0] if len(self.selected_inputs)==1 else self.ui('已选择{count}个文件/目录',count=len(self.selected_inputs))
            blocked=self.input.blockSignals(True);self.input.setText(self.selection_display);self.input.blockSignals(blocked)
    def select_inputs(self,paths,auto_load=True):
        if self.worker:return
        selected=selection_paths(paths)
        if not selected:return
        if self.case and selected!=(self.case.source_paths or [self.case.source]) and self.masks.text().strip():
            if str(Path(self.masks.text().strip()).resolve())==self.case.metadata.get('mask_folder'):self.masks.clear()
        self.pending_project=None;self.selected_inputs=selected;self.input_organization='auto'
        self.selection_display=selected[0] if len(selected)==1 else self.ui('已选择{count}个文件/目录',count=len(selected))
        blocked=self.input.blockSignals(True);self.input.setText(self.selection_display);self.input.blockSignals(blocked)
        self._input_changed()
        self.ui.set_text(self.input_summary,f'已选择{len(selected)}个文件/目录；载入后显示层面和时相。')
        if auto_load:self.load_input()
    def choose_input_folder(self):
        if self.worker:return
        path=QFileDialog.getExistingDirectory(self,self.ui('单病例目录'),options=QFileDialog.Option.DontUseNativeDialog|QFileDialog.Option.ShowDirsOnly)
        if path:self.select_inputs([path])
    def _drop_paths(self,event):
        if self.worker or not event.mimeData().hasUrls():return []
        urls=event.mimeData().urls()
        if not urls or any(not u.isLocalFile() for u in urls):return []
        return [u.toLocalFile() for u in urls]
    def dragEnterEvent(self,event):
        if self._drop_paths(event):event.acceptProposedAction()
        else:event.ignore()
    def dragMoveEvent(self,event):self.dragEnterEvent(event)
    def dropEvent(self,event):
        paths=self._drop_paths(event)
        if not paths:event.ignore();return
        event.acceptProposedAction();self.select_inputs(paths)
    def show_input_list(self):
        paths=self.current_inputs()
        if not paths:return
        dialog=QDialog(self);dialog.setWindowTitle(self.ui('输入文件与序列'));layout=QVBoxLayout(dialog)
        text=QTextEdit();text.setReadOnly(True);text.setAcceptDrops(False)
        organization=self.case.metadata.get('organization',{}) if self._input_matches() else {}
        listing=self.ui('输入组织：{method}',method=organization.get('method','auto'))+'\n\n'+'\n'.join(paths)
        if organization.get('files'):listing+='\n\n'+self.ui('实际读取文件')+'\n'+'\n'.join(organization['files'])
        text.setPlainText(listing);layout.addWidget(text);buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Close);buttons.rejected.connect(dialog.reject);layout.addWidget(buttons);dialog.resize(760,440);dialog.exec()
    def _ask_organization(self,error):
        box=QMessageBox(self);box.setWindowTitle(self.ui('确认层面与时相组织'));box.setText(self.ui.message(str(error)))
        box.setInformativeText(self.ui('将采用你确认的组织方式，原始像素和物理坐标不变。'))
        labels={'position_order':'同位置按文件/帧序配对','file_slices':'按文件续接层面','file_time':'按文件续接时间块'}
        buttons={box.addButton(self.ui(labels[key]),QMessageBox.ButtonRole.AcceptRole):key for key in error.options}
        box.addButton(self.ui('取消'),QMessageBox.ButtonRole.RejectRole);box.exec();return buttons.get(box.clickedButton())
    def _resolve_input(self,error):
        self.ui.set_text(self.status,'WAIT · 待确认序列组织');self.logmsg(str(error));choice=self._ask_organization(error)
        if choice:
            self.input_organization=choice;self._retry_import=True
            if self.worker is None:self._retry_import=False;QTimer.singleShot(0,self.load_input)
        else:self.ui.set_text(self.status,'CANCELLED');self.ui.set_text(self.input_summary,'输入尚未组织；可重新选择文件或再次载入。')
    def notice(self,title,message,warning=False):
        method=QMessageBox.warning if warning else QMessageBox.information
        return method(self,self.ui.message(title),self.ui.message(message))
    def _browse(self,mode):
        if self.worker:return
        if mode=='weights':p,_=QFileDialog.getOpenFileName(self,self.ui('选择分割权重'),str(APP_ROOT/'weights'),'PyTorch (*.pth *.pt)',options=QFileDialog.Option.DontUseNativeDialog)
        elif mode=='input':
            files,_=QFileDialog.getOpenFileNames(self,self.ui('选择DICOM / NIfTI文件（可多选）'),'','DICOM / NIfTI (*.dcm *.DCM *.ima *.IMA *.nii *.NII *.nii.gz *.NII.GZ);;All files (*)',options=QFileDialog.Option.DontUseNativeDialog)
            if files:self.select_inputs(files)
            return
        else:p=QFileDialog.getExistingDirectory(self,self.ui('选择目录'),options=QFileDialog.Option.DontUseNativeDialog|QFileDialog.Option.ShowDirsOnly)
        if p:getattr(self,mode if mode!='weights' else 'weights').setText(p)
    def logmsg(self,s):
        self.log_entries.append(s);self.log.setPlainText('\n'.join(self.ui.message(item) for item in self.log_entries));self.log.verticalScrollBar().setValue(self.log.verticalScrollBar().maximum())
    def _busy(self,on):
        for w in self.locks:w.setEnabled(not on)
        self.cancel_btn.setEnabled(on)
        if on:self.ui.set_text(self.status,'RUNNING · 后台处理中')
        elif self.ui.source(self.status).startswith('RUNNING'):self.ui.set_text(self.status,'READY · 研究原型')
    def _start(self,fn):
        if self.worker:return
        self.play_timer.stop();self.point_mode=None;self.canvas.editing=False;self._busy(True);self.progress.setValue(0)
        w=Worker(fn,self);self.worker=w;w.progress.connect(self._progress);w.message.connect(self.logmsg);w.succeeded.connect(self._accept);w.failed.connect(self._error)
        w.needs_input.connect(self._resolve_input)
        w.finished.connect(lambda:self._finished(w));w.start()
    def _progress(self,n,total,stage):self.progress.setRange(0,max(total,1));self.progress.setValue(n);self.ui.set_format(self.progress,f'{stage}  %v / %m  (%p%)')
    def _finished(self,w):
        if self.worker is w:self.worker=None;self._busy(False)
        w.deleteLater()
        if getattr(self,'_retry_import',False):self._retry_import=False;QTimer.singleShot(0,self.load_input)
    def _error(self,message,cancelled):
        self.logmsg(message);self.ui.set_text(self.status,'CANCELLED' if cancelled else 'ERROR · 请查看日志')
        if self.last_run:write_json(Path(self.last_run)/'task_status.json',dict(status='cancelled' if cancelled else 'failed',message=message))
        if not cancelled:self.notice('处理未完成',message[-2500:],warning=True)
    def _clear_results(self):
        self.measurement=None;self.reference_result=None;self.table.setRowCount(0);self.ui.set_text(self.result_note,'当前输入尚无有效分析结果。');self.result_note.setStyleSheet('color:#657992;padding:3px');self._sync_cards()
    def _input_matches(self):
        return self.case is not None and self.current_inputs()==(self.case.source_paths or [self.case.source]) and (str(Path(self.masks.text().strip()).resolve()) if self.masks.text().strip() else None)==self.case.metadata.get('mask_folder')
    def _input_changed(self):
        if self.selected_inputs and self.input.text()!=self.selection_display:
            self.selected_inputs=[];self.selection_display=None;self.input_organization='auto'
        if self.case and not self._input_matches():
            self._clear_results();self.canvas.empty();self.ui.set_text(self.selection_label,'输入已变化，请重新载入病例。');self.ui.set_text(self.coverage,'等待重新载入当前输入。');self.ui.set_text(self.status,'RELOAD · 输入已变化')
    def load_input(self):
        if self.worker:return
        paths=self.current_inputs();mask=self.masks.text().strip() or None
        if not paths:return
        if self.demographic_source and paths!=self.demographic_source and not self.pending_project:self.set_demographics({})
        self._clear_results();self.case=None;self.manual_rvip={};self.pending_points={};self.ed_override=None;self.last_run=None;self.canvas.empty();self.ui.set_text(self.selection_label,'正在载入…');self.ui.set_text(self.coverage,'正在核对层面 / 时相 / 物理间距。')
        mode=self.input_organization
        self._start(lambda w:('load',load_case(paths,mask,progress=w.progress.emit,cancel=lambda:w.cancelled,organization=mode)))
    def _accept(self,payload):
        kind=payload[0]
        if kind=='load':
            self.case=payload[1];self.logmsg(f'已载入{len(self.case.planes)}个平面 / {len(self.case.slices)}层 / {len(self.case.frames)}帧。')
            self.demographic_source=self.case.source_paths or [self.case.source]
            layout=self.case.metadata.get('organization',{})
            self.ui.set_text(self.input_summary,f"{layout.get('file_count',1)}文件 → {len(self.case.slices)}层 × {len(self.case.frames)}帧（{len(self.case.planes)}平面）")
            for note in self.case.metadata.get('input_warnings',[]):self.logmsg(note)
            for sl,values in [(self.slice_slider,self.case.slices),(self.frame_slider,self.case.frames)]:sl.blockSignals(True);sl.setRange(0,len(values)-1);sl.setValue(0);sl.blockSignals(False)
            mode='existing' if any('existing' in p.masks for p in self.case.planes) else 'post';self.mask_mode.blockSignals(True);self.mask_mode.setCurrentIndex(self.mask_mode.findData(mode));self.mask_mode.blockSignals(False)
            im=self.case.planes[0].image;lo,hi=np.percentile(im,[1,99]);self.view.pop('center_rc',None);self.view.update(pan_x=0.,pan_y=0.)
            self.wl.setValue(float((lo+hi)/2));self.ww.setValue(float(max(hi-lo,1)))
            if self.pending_project:
                d=self.pending_project;self.pending_project=None;self.set_demographics(d.get('demographics',{}));self.ed_override=d.get('ed_override');self.view.update(d.get('view',{}));self.case.notes=d.get('input_notes',self.case.notes)
                self.manual_rvip={(int(x['slice']),int(x['frame'])):x['points'] for x in d.get('manual_rvip',[])}
                self.case.metadata['segmentation']=d.get('segmentation')
                self.fov.blockSignals(True);self.fov.setValue(self.view['fov']);self.fov.blockSignals(False)
                self.wl.blockSignals(True);self.wl.setValue(self.view['wl']);self.wl.blockSignals(False)
                self.ww.blockSignals(True);self.ww.setValue(self.view['ww']);self.ww.blockSignals(False)
                self.rotation.blockSignals(True);self.rotation.setCurrentIndex(self.rotation.findData(self.view['rotation']));self.rotation.blockSignals(False)
                for control,key in [(self.flip_h,'flip_h'),(self.flip_v,'flip_v'),(self.fill,'show_fill'),(self.bg,'thickness_background')]:control.blockSignals(True);control.setChecked(self.view[key]);control.blockSignals(False)
                if d.get('analysis_status')!='segmentation_only':QTimer.singleShot(200,self.measure_current)
            self.ui.set_text(self.result_note,'已载入。请选择分割运行，或使用已有ROI计算厚度。');self.redraw()
        elif kind=='measure':
            self.case,self.measurement,self.last_run=payload[1:];self.update_reference();self._table();self.goto_max()
            self.logmsg(f'完成：MWT={self.measurement.mwt_mm:.2f} mm，ED帧{self.measurement.ed_frame}，测量{len(self.measurement.slices)}层。')
            device='existing ROI' if self.measurement.mask_mode=='existing' else (self.case.metadata.get('segmentation') or {}).get('device','CPU');self.ui.set_text(self.status,'DONE · '+device.upper())
            if self.reference_result:self.side_tabs.setCurrentIndex(1)
            self.canvas.fig.savefig(Path(self.last_run)/'review.png',dpi=180,facecolor='white')
        elif kind=='segmented':
            self.case,self.last_run,reason=payload[1:];self._clear_results();self.ui.set_text(self.status,'SEGMENTED · 自动分割完成')
            self.ui.set_text(self.result_note,'自动分割完成，厚度结果不可用：'+reason);self.logmsg('自动分割完成，厚度结果不可用：'+reason);self.redraw()
            self.canvas.fig.savefig(Path(self.last_run)/'review.png',dpi=180,facecolor='white')
        elif kind=='export':
            self.progress.setRange(0,1);self.progress.setValue(1);self.ui.set_format(self.progress,'项目 / 报告已保存')
            device='existing ROI' if self.measurement.mask_mode=='existing' else (self.case.metadata.get('segmentation') or {}).get('device','CPU');self.ui.set_text(self.status,'DONE · '+device.upper())
            self.canvas.fig.savefig(Path(self.last_run)/'review.png',dpi=180,facecolor='white')
            self.logmsg('项目和报告已更新：'+str(payload[1]));QDesktopServices.openUrl(QUrl.fromLocalFile(self.last_run))
    def _inputs_ok(self):
        if self.case is None:self.notice('尚未载入','请先载入单病例序列。');return False
        if not self._input_matches():self.notice('输入已变化','图像或ROI目录已变化，请重新载入当前输入。');return False
        return True
    def run_pipeline(self):
        if not self._inputs_ok():return
        checkpoint=self.weights.text();device=self.device.currentData();steps={f'step{i+1}':b.isChecked() for i,b in enumerate(self.pp)}
        case=self.case
        try:run=make_run(self.output.text(),case.source_paths or [case.source])
        except (ValueError,OSError) as e:self.notice('输出目录',str(e),warning=True);return
        demo=self.demographics();view=dict(self.view);manual=dict(self.manual_rvip)
        self._clear_results();self.last_run=str(run);self.ed_override=None
        mode='post' if any(steps.values()) else 'raw';self.mask_mode.blockSignals(True);self.mask_mode.setCurrentIndex(self.mask_mode.findData(mode));self.mask_mode.blockSignals(False)
        def task(w):
            from core.segmentation import segment_case
            case.metadata['segmentation_state']='running';w.message.emit('载入指定权重并运行CorSeg预处理/预测…')
            segment_case(case,run,checkpoint,device,steps,w.progress.emit,lambda:w.cancelled)
            case.metadata['segmentation_state']='complete'
            try:result=measure_case(case,mode,manual_rvip=manual,use_json=False,cancel=lambda:w.cancelled,progress=w.progress.emit)
            except ValueError as error:
                if w.cancelled:raise Cancelled('自动分割已取消；已完成文件保留在当前run目录。')
                export_segmentation_only(case,str(error),demo,run,mode,view,self.ui.language)
                w.progress.emit(1,1,'自动分割完成')
                return 'segmented',case,str(run),str(error)
            self._export_in_worker(case,result,run,demo,view,manual,w)
            return 'measure',case,result,str(run)
        self._start(task)
    def measure_current(self):
        if not self._inputs_ok():return
        case=self.case;mode=self.mask_mode.currentData();ed=self.ed_override;manual=dict(self.manual_rvip);use_json=self.use_json.isChecked()
        if mode in ['raw','post'] and case.metadata.get('segmentation_state')!='complete':self.notice('分割未完成','请完成分割，或选择已有ROI。');return
        try:run=make_run(self.output.text(),case.source_paths or [case.source])
        except (ValueError,OSError) as e:self.notice('输出目录',str(e),warning=True);return
        demo=self.demographics();view=dict(self.view);self._clear_results();self.last_run=str(run)
        def task(w):
            result=measure_case(case,mode,ed,manual_rvip=manual,use_json=use_json,cancel=lambda:w.cancelled,progress=w.progress.emit)
            self._export_in_worker(case,result,run,demo,view,manual,w)
            return 'measure',case,result,str(run)
        self._start(task)
    def _export_in_worker(self,case,result,run,demo,view,manual,worker):
        try:reference=self.ref.evaluate(result.mwt_mm,**demo)
        except ValueError:reference=None
        worker.progress.emit(0,1,'保存项目/结果')
        export_analysis(case,result,reference,demo,run,view,manual,cancel=lambda:worker.cancelled,language=self.ui.language)
        worker.progress.emit(1,1,'保存项目/结果')
    def demographics(self):return dict(sex=self.sex.currentData(),age=self.age.value(),height=self.height_input.value(),weight=self.weight.value())
    def set_demographics(self,d):
        self.sex.setCurrentIndex(max(0,self.sex.findData(d.get('sex'))))
        for name,control in [('age',self.age),('height',self.height_input),('weight',self.weight)]:control.setValue(float(d.get(name,0)))
    def update_reference(self,*args):
        self.reference_result=None;self.ui.set_text(self.demo_info,'BSA —  ·  BMI —');d=self.demographics()
        try:
            if self.measurement:self.reference_result=self.ref.evaluate(self.measurement.mwt_mm,**d)
            elif d['sex'] and d['age']>=18 and d['height']>=50 and d['weight']>=10:
                temp=self.ref.evaluate(10.,**d);self.ui.set_text(self.demo_info,f"BSA {temp['bsa_m2']:.3f} m² · BMI {temp['bmi']:.1f}")
        except ValueError as e:
            if self.measurement:self.ui.set_text(self.result_note,str(e))
        self._sync_cards()
    def _sync_cards(self):
        values={'mwt':f'{self.measurement.mwt_mm:.2f} <small>mm</small>' if self.measurement else '—','mu':'—','ul':'—','z':'—'}
        if self.reference_result:
            q=self.reference_result;values.update(mu=f"{q['expected_mwt_mm']:.2f} <small>mm</small>",ul=f"{q['upper_limit_mm']:.2f} <small>mm</small>",z=f"{q['z_score']:+.2f}")
            self.ui.set_text(self.demo_info,f"BSA {q['bsa_m2']:.3f} m² · BMI {q['bmi']:.1f}")
            flags=list(dict.fromkeys(self.measurement.flags+q['support_flags']+[x for x in self.case.notes if 'unknown' in x.lower()]+self.case.metadata.get('input_warnings',[])))
            flag_text='；'.join(flags[:3])+(f'（另有{len(flags)-3}条见报告）' if len(flags)>3 else '')
            self.ui.set_text(self.result_note,('超过人口学参考上限' if q['above_limit'] else '未超过人口学参考上限')+'  |  '+(flag_text if flags else f"当前支持单元n={q['support_cell_n']}；仍需核对覆盖与轮廓。"))
            self.result_note.setStyleSheet('color:#a3661a;padding:3px' if flags else 'color:#24785d;padding:3px')
        for k,(label,title) in self.cards.items():label.setText(f'<span style="color:#6d8099;font-size:10pt">{self.ui(title)}</span><br><span style="font-size:22pt;font-weight:700;color:#1d446f">{values[k]}</span>')
    def current_plane(self):
        if not self.case:return None
        return self.case.by_key((self.case.slices[self.slice_slider.value()],self.case.frames[self.frame_slider.value()]))
    def redraw(self,*args):
        if not self.case or not self._input_matches():return
        p=self.current_plane();self.slice_label.setText(f'{self.slice_slider.value()+1}/{len(self.case.slices)} (ID {self.case.slices[self.slice_slider.value()]})');self.frame_label.setText(f'{self.frame_slider.value()+1}/{len(self.case.frames)} (ID {self.case.frames[self.frame_slider.value()]})')
        if p is None:self.canvas.empty('No image for this slice / frame');self.ui.set_text(self.selection_label,'当前层面 / 时相没有对应图像。');self.ui.set_text(self.coverage,'该层/时相缺少影像，未补帧。');return
        self.ui.set_text(self.selection_label,f'当前层面 ID {p.slice}  |  时相 ID {p.frame}'+('  ·  分析ED' if self.measurement and p.frame==self.measurement.ed_frame else '  ·  预览'))
        mask=p.masks.get(self.mask_mode.currentData());td=self.measurement.slices.get(p.key) if self.measurement else None
        if td is None and mask is not None:
            try:
                pair=self.manual_rvip.get(p.key)
                if pair is None:pair=detect_rvip(mask)
                if pair is not None:
                    a,b,c=study.extract_smooth_contours(mask)
                    if a is not None:td=study.compute_thickness_midline_normal(a,b,c,np.asarray(pair)[0],p.spacing,n_samples=72);td['rvip']=np.asarray(pair)
            except (ValueError,TypeError,IndexError):td=None
        self.canvas.show_plane(p,mask,td,self.view,self.measurement.ed_frame if self.measurement else None)
        measured=f'ED={self.measurement.ed_frame} | 已测{len(self.measurement.slices)}/{len(self.case.slices)}层' if self.measurement else '尚未确定分析ED'
        self.ui.set_text(self.coverage,f'{measured} | spacing {p.spacing[0]:.3f} × {p.spacing[1]:.3f} mm | {p.unit_note}')
    def _view_changed(self,k,v):self.view[k]=v;self.redraw()
    def center_lv(self):
        p=self.current_plane()
        if p is None:return
        mask=p.masks.get(self.mask_mode.currentData())
        if mask is None or not np.any(mask==2):return
        self.view['center_rc']=np.argwhere(mask==2).mean(axis=0).tolist();self.view.update(pan_x=0.,pan_y=0.);self.redraw()
    def fit_image(self):
        p=self.current_plane()
        if p is None:return
        self.view.pop('center_rc',None);self.view.update(pan_x=0.,pan_y=0.);self.fov.setValue(max(np.array(p.image.shape)*np.array(p.spacing))*1.04);self.redraw()
    def _pan(self,x,y):self.view['pan_x']+=x;self.view['pan_y']+=y;self.redraw()
    def _zoom(self,f):self.fov.setValue(np.clip(self.fov.value()*f,25,500))
    def _mask_changed(self):
        if self.worker:return
        self._clear_results();self.ui.set_text(self.result_note,'ROI / JSON设置已变化，请重新计算厚度。');self.redraw()
    def goto_max(self):
        if not self.measurement:return
        s,f=self.measurement.max_key;self.slice_slider.setValue(self.case.slices.index(s));self.frame_slider.setValue(self.case.frames.index(f));self.redraw()
    def set_ed(self):
        if self.case and not self.worker:self.ed_override=self.case.frames[self.frame_slider.value()];self.measure_current()
    def reset_ed(self):
        if self.case and not self.worker:self.ed_override=None;self.measure_current()
    def _next_frame(self):self.frame_slider.setValue((self.frame_slider.value()+1)%(self.frame_slider.maximum()+1))
    def play(self):
        if self.play_timer.isActive():self.play_timer.stop()
        elif self.case and not self.worker:self.play_timer.start(180)
    def _table(self):
        self.table.setRowCount(len(self.measurement.rows))
        for i,row in enumerate(self.measurement.rows):
            for j,key in enumerate(['slice','frame','study_max_mm','rvip_source','status']):self.table.setItem(i,j,QTableWidgetItem('—' if row[key] is None else self.ui.message(str(row[key]))))
    def table_select(self,row,col):
        if not self.measurement:return
        data=self.measurement.rows[row];self.slice_slider.setValue(self.case.slices.index(data['slice']));self.frame_slider.setValue(self.case.frames.index(data['frame']))
    def set_point_mode(self,mode):
        if self.worker or not self.case:return
        self.point_mode=mode;self.canvas.editing=True;self.tabs.setCurrentIndex(0);self.ui.set_text(self.result_note,'请在影像上点击'+('前' if mode=='anterior' else '后')+'RV插入点；之后重新计算。')
    def _point(self,row,col):
        p=self.current_plane()
        if not p or not(0<=row<p.image.shape[0] and 0<=col<p.image.shape[1]):return
        pair=self.pending_points.get(p.key)
        if pair is None:
            base=self.manual_rvip.get(p.key)
            if base is None:base=detect_rvip(p.masks[self.mask_mode.currentData()]) if self.mask_mode.currentData() in p.masks else None
            pair=np.array(base,float) if base is not None else np.full((2,2),np.nan)
        pair[0 if self.point_mode=='anterior' else 1]=[row,col];self.pending_points[p.key]=pair
        if np.isfinite(pair).all():self.manual_rvip[p.key]=pair.tolist()
        self.point_mode=None;self.canvas.editing=False;self._clear_results();self.logmsg(f'层{p.slice}帧{p.frame}已记录手动插入点；需重新计算。');self.redraw()
    def clear_points(self):
        if self.worker:return
        self.manual_rvip={};self.pending_points={};self._clear_results();self.redraw()
    def export_result(self):
        if not self.measurement:
            if self.case and self.last_run and self.case.metadata.get('segmentation_state')=='complete':
                self.logmsg('分割文件已保存到：'+self.last_run);QDesktopServices.openUrl(QUrl.fromLocalFile(self.last_run));return
            self.notice('尚无结果','请先完成厚度计算。');return
        self.update_reference();case=self.case;m=self.measurement;ref=self.reference_result;demo=self.demographics();view=dict(self.view);manual=dict(self.manual_rvip);run=self.last_run
        self._start(lambda w:('export',export_analysis(case,m,ref,demo,run,view,manual,cancel=lambda:w.cancelled,language=self.ui.language)))
    def open_project(self,path=None):
        if not path:path,_=QFileDialog.getOpenFileName(self,self.ui('打开LVWT项目'),'','LVWT project (*.lvwt.json)',options=QFileDialog.Option.DontUseNativeDialog)
        if not path:return
        try:d=read_project(path)
        except (ValueError,OSError,KeyError) as e:self.notice('项目无法打开',str(e),warning=True);return
        self.selected_inputs=[];self.selection_display=None;self.input_organization='auto'
        self.pending_project=d;self.input.setText(d['input_path']);self.masks.setText(d['mask_folder']);self.load_input()
    def cancel(self):
        if self.worker:self.worker.cancelled=True;self.logmsg('取消请求已发送；当前平面完成后停止。')
    def closeEvent(self,event):
        if self.worker and self.worker.isRunning():self.cancel();event.ignore();self.notice('正在停止','请等待当前任务结束后关闭。')
        else:event.accept()

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--input',nargs='+');ap.add_argument('--masks');ap.add_argument('--project');ap.add_argument('--demo',action='store_true');ap.add_argument('--language',choices=['zh','en']);args=ap.parse_args()
    QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    app=QApplication(sys.argv)
    f=Path(r'C:\Windows\Fonts\msyh.ttc')
    if f.exists():QFontDatabase.addApplicationFont(str(f))
    app.setFont(QFont('Microsoft YaHei',9))
    style.use(str(APP_ROOT/'assets/openscience.mplstyle'))
    w=Window(language=args.language)
    if args.language:
        try:save_language(args.language)
        except OSError as error:w.logmsg('语言偏好未能保存：'+str(error))
    def exception_hook(kind,value,tb):
        message=''.join(traceback.format_exception(kind,value,tb));print(message,flush=True);w.logmsg(message);w.ui.set_text(w.status,'ERROR · 界面操作未完成');w.notice('界面操作未完成',str(value),warning=True)
    sys.excepthook=exception_hook
    rect=app.primaryScreen().availableGeometry();w.resize(min(1480,rect.width()-40),min(920,rect.height()-60));w.show()
    if args.project:QTimer.singleShot(100,lambda:w.open_project(args.project))
    elif args.demo and (APP_ROOT/'qa/demo.local.json').exists():
        d=json.loads((APP_ROOT/'qa/demo.local.json').read_text(encoding='utf-8'));w.input.setText(d['input']);w.set_demographics(d['demographics']);QTimer.singleShot(100,w.load_input)
    elif args.input:
        if args.masks:w.masks.setText(args.masks)
        QTimer.singleShot(100,lambda:w.select_inputs(args.input))
    sys.exit(app.exec())

if __name__=='__main__':main()
