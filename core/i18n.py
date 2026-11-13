"""Presentation-only translations; scientific keys, flags and values stay canonical."""
import re
from string import Formatter

LANGUAGES=('zh','en')
EN={
    'LVWT  /  CineSAX Research Workbench':'LVWT  /  CineSAX Research Workbench',
    'READY · 研究原型':'READY · Research prototype',
    'RUNNING · 后台处理中':'RUNNING · Background task',
    'ERROR · 请查看日志':'ERROR · See run log',
    'ERROR · 界面操作未完成':'ERROR · UI action incomplete',
    'RELOAD · 输入已变化':'RELOAD · Input changed',
    'DONE · {device}':'DONE · {device}',
    '01 载入图像   →   02 自动分割   →   03 ED / MWT   →   04 人口学参照':'01 Load images   →   02 Segment   →   03 ED / MWT   →   04 Demographic reference',
    '单病例CineSAX目录或NIfTI体积':'One CineSAX case folder or NIfTI volume',
    '可选：独立ROI文件夹':'Optional: separate ROI folder',
    '输入与输出':'Input and output', '图像输入':'Image input',
    '已有ROI目录（可选）':'Existing ROI folder (optional)', '输出目录':'Output folder',
    '分割权重':'Segmentation weights', '载入病例':'Load case', '打开项目':'Open project',
    '分割设置':'Segmentation settings', '自动（优先CUDA）':'Auto (prefer CUDA)',
    '计算设备':'Device', '连通域约束':'Connected components',
    'LV腔包含约束':'LV cavity containment', '间隙填充':'Gap filling',
    '已有ROI':'Existing ROI', '后处理预测':'Postprocessed prediction', '原始预测':'Raw prediction',
    '测量来源':'Measurement source',
    '已有ROI优先使用配对JSON插入点':'Prefer paired JSON RV insertion points',
    '人口学输入':'Demographics', '请选择':'Select', '男':'Male', '女':'Female',
    ' 岁':' years', '模型性别':'Model sex', '年龄':'Age', '身高':'Height', '体重':'Weight',
    '运行分割 + MWT':'Run segmentation + MWT', '使用当前ROI计算厚度':'Measure current ROI',
    '保存项目 / 报告':'Save project / report', '取消':'Cancel', '确定':'OK',
    '参考结果\n\nμ：相同年龄、性别和BSA的预期正常MWT。\n\nUL：冻结模型的正常上参考限。\n\nZ：(实测MWT − μ) / 性别特异残差SD。\n\n改变人口学输入会立即更新参照值，不需要重新分割。':
        'Reference results\n\nμ: Expected normal MWT for the same age, sex and BSA.\n\nUL: Upper reference limit from the frozen model.\n\nZ: (Measured MWT − μ) / sex-specific residual SD.\n\nDemographic changes update the reference values immediately, without re-segmentation.',
    '病例 / 分割':'Case / segment', '人口学参照':'Reference',
    '输出保存在独立run目录。超限状态不是HCM诊断。':'Outputs use a separate run folder. Exceeding the limit is not an HCM diagnosis.',
    '实测 MWT':'Measured MWT', '预期正常 μ':'Expected normal μ',
    '正常上限 UL':'Upper limit UL', '标准化 Z':'Standardized Z',
    '载入影像后，可运行分割或使用已有ROI。':'Load images, then segment or measure existing ROI masks.',
    '当前层面 / 时相：—':'Current slice / frame: —',
    '层面':'Slice', '时相':'Frame', '定位最大层':'Go to maximum',
    '设当前为ED':'Set current as ED', '自动ED':'Auto ED', '播放/暂停':'Play / pause',
    '视图（不改变测量）':'View (display only)', '窗位':'Level', '窗宽':'Width', '旋转':'Rotate',
    '左右翻转':'Flip horizontal', '上下翻转':'Flip vertical', '标签填充':'Label fill',
    '厚度叠图':'Image underlay', '居中左室':'Center LV', '适配全图':'Fit image',
    '影像与测量':'Images / measurement', 'ED帧':'ED frame', '最大厚度 mm':'Max thickness (mm)',
    'RVIP来源':'RVIP source', '状态':'Status', '标记前插入点':'Mark anterior RVIP',
    '标记后插入点':'Mark posterior RVIP', '清除手动插入点':'Clear manual points',
    '层面数据 / 插入点':'Slices / insertion points', '运行记录':'Run log',
    '有效层面 / ED / 像素间距将在载入后显示。':'Valid slices, ED and pixel spacing appear after loading.',
    '选择分割权重':'Select segmentation weights', '选择输入':'Select input',
    '载入单病例文件夹，或单个3D/4D NIfTI文件。':'Load one case folder or a single 3D/4D NIfTI file.',
    '病例文件夹':'Case folder', 'NIfTI文件':'NIfTI file', '单病例目录':'Single-case folder',
    'NIfTI体积':'NIfTI volume', '选择目录':'Select folder', '处理未完成':'Processing incomplete',
    '当前输入尚无有效分析结果。':'No valid analysis result for the current input.',
    '输入已变化，请重新载入病例。':'Input changed. Please reload the case.',
    '等待重新载入当前输入。':'Waiting to reload the current input.',
    '正在载入…':'Loading…', '正在核对层面 / 时相 / 物理间距。':'Checking slices, frames and physical spacing.',
    '已载入{planes}个平面 / {slices}层 / {frames}帧。':'Loaded {planes} planes / {slices} slices / {frames} frames.',
    '已载入。请选择分割运行，或使用已有ROI计算厚度。':'Loaded. Run segmentation or measure existing ROI masks.',
    '完成：MWT={mwt} mm，ED帧{frame}，测量{slices}层。':'Complete: MWT={mwt} mm, ED frame {frame}, {slices} measured slices.',
    '项目 / 报告已保存':'Project / report saved', '项目和报告已更新：{path}':'Project and report updated: {path}',
    '尚未载入':'No case loaded', '请先载入单病例序列。':'Load one case series first.',
    '输入已变化':'Input changed', '图像或ROI目录已变化，请重新载入当前输入。':'The image or ROI folder changed. Reload the input.',
    '载入指定权重并运行CorSeg预处理/预测…':'Loading weights and running CorSeg preprocessing / inference…',
    '分割未完成':'Segmentation incomplete', '请完成分割，或选择已有ROI。':'Complete segmentation or select existing ROI masks.',
    '保存项目/结果':'Saving project / results', '超过人口学参考上限':'Above the demographic reference limit',
    '未超过人口学参考上限':'Not above the demographic reference limit',
    '当前支持单元n={n}；仍需核对覆盖与轮廓。':'Support cell n={n}; review coverage and contours.',
    '{message}（另有{n}条见报告）':'{message} ({n} more notes in the report)',
    '当前层面 / 时相没有对应图像。':'No image for the selected slice / frame.',
    '当前层面 ID {slice}':'Slice ID {slice}', '时相 ID {frame}':'Frame ID {frame}',
    '分析ED':'Analysis ED', '预览':'Preview', '已测{n}/{total}层':'Measured {n}/{total} slices',
    '尚未确定分析ED':'Analysis ED not yet determined',
    'ROI / JSON设置已变化，请重新计算厚度。':'ROI / JSON settings changed. Recalculate thickness.',
    '请在影像上点击前RV插入点；之后重新计算。':'Click the anterior RV insertion point, then recalculate.',
    '请在影像上点击后RV插入点；之后重新计算。':'Click the posterior RV insertion point, then recalculate.',
    '层{slice}帧{frame}已记录手动插入点；需重新计算。':'Manual insertion point recorded at slice {slice}, frame {frame}; recalculate.',
    '尚无结果':'No result', '请先完成厚度计算。':'Complete thickness measurement first.',
    '打开LVWT项目':'Open LVWT project', '项目无法打开':'Cannot open project',
    '取消请求已发送；当前平面完成后停止。':'Cancellation requested; stopping after the current step.',
    '正在停止':'Stopping', '请等待当前任务结束后关闭。':'Wait for the current task to stop before closing.',
    '界面操作未完成':'UI action incomplete',
    '语言偏好未能保存：{error}':'Could not save the language preference: {error}',
    # Canonical core diagnostics are translated only at the presentation boundary.
    '输出目录不能等于输入目录或位于输入目录内。':'The output folder cannot equal or be inside the input folder.',
    '请选择模型性别。':'Select the model sex.', '年龄/BSA必须为有效数值。':'Age and BSA must be valid numbers.',
    '人口学输入包含非有限值。':'Demographic inputs contain non-finite values.',
    '参考模型用于成人，请输入18–120岁的年龄。':'The reference model is for adults. Enter an age of 18–120 years.',
    '请核对身高（单位cm）。':'Check height (in cm).', '请核对体重（单位kg）。':'Check weight (in kg).',
    '年龄超出参考观测范围':'Age is outside the observed reference range',
    'BSA超出参考观测范围':'BSA is outside the observed reference range',
    'BMI超出参考入组范围18–35':'BMI is outside the reference inclusion range of 18–35',
    '当前年龄/BSA单元样本稀疏（n={n}）':'Sparse age/BSA support cell (n={n})',
    '已取消导出；当前run保留已写入的文件。':'Export cancelled; completed files remain in the current run.',
    '已取消导出。':'Export cancelled.', '不支持的项目版本。':'Unsupported project version.',
    '当前Python环境不支持CUDA，请选择CPU或使用已配置GPU启动器。':'CUDA is unavailable in this Python environment. Select CPU or use the configured GPU launcher.',
    '当前程序仅支持单通道2D四标签CineSAX权重。':'Only single-channel, 2D, four-label CineSAX weights are supported.',
    '权重label_map不是0/1/2/3恒等映射，不能自动替换标签语义。':'The checkpoint label_map is not an identity mapping for 0/1/2/3. Label semantics cannot be substituted automatically.',
    '自动分割已取消；已完成文件保留在当前run目录。':'Segmentation cancelled; completed files remain in the current run.',
    '自动分割':'Segmenting', 'v2 JSON不是original坐标约定。':'The v2 JSON does not use original-image coordinates.',
    'JSON插入点超出原图，可能为转置坐标；请核对。':'JSON insertion points are outside the image; check for transposed coordinates.',
    '没有同时包含LV心肌和LV腔的有效ROI。':'No valid ROI contains both LV myocardium and LV cavity.',
    '部分层面物理位置重复，需核对覆盖和AHA位置。':'Some slice positions repeat. Review coverage and AHA location.',
    '指定ED帧不在当前序列。':'The selected ED frame is not in this series.',
    '单时相输入：请确认该帧为舒张末期。':'Single-phase input: confirm that this frame is end diastole.',
    '人工指定ED帧：{frame}':'Manually selected ED frame: {frame}',
    '人工排除层面：{slices}':'Manually excluded slices: {slices}',
    '手动RV插入点必须为图像内两个有效坐标。':'Manual RV insertion points must be two valid coordinates inside the image.',
    '层{slice} JSON忽略：{reason}':'Slice {slice} JSON ignored: {reason}',
    '已取消厚度计算':'Thickness measurement cancelled',
    '无RV插入点；可导入JSON或手动定位':'No RV insertion points; import JSON or mark them manually',
    '层{slice}的LV标签接触图像边缘，请核对覆盖。':'LV labels touch the image edge in slice {slice}; review coverage.',
    '无法提取有效LV轮廓':'Unable to extract valid LV contours', '非有限厚度结果':'Non-finite thickness result',
    '层{slice}未测量：{reason}':'Slice {slice} not measured: {reason}', '提取厚度':'Measuring thickness',
    '未获得可用厚度；请检查ROI、RV插入点及层面覆盖。':'No usable thickness result. Check ROI masks, RV insertion points and coverage.',
    '有效ED层数少于4；AHA位置未分配，需核对短轴覆盖。':'Fewer than 4 valid ED slices; AHA location is unassigned. Review SAX coverage.',
    '包含手动RV插入点。':'Includes manual RV insertion points.',
    '按研究规则仅使用最长连续有效层段。':'Only the longest contiguous valid stack is used, following the study rule.',
    '不支持的空间单位：{unit}':'Unsupported spatial unit: {unit}', '无效像素间距/affine。':'Invalid pixel spacing or affine.',
    'NIfTI affine与header像素间距不一致。':'NIfTI affine and header pixel spacing disagree.',
    '不支持剪切的层面几何，请先核对图像。':'Sheared in-plane geometry is unsupported. Check the images.',
    'Header单位unknown；按研究约定将zoom视为mm':'Original header units unknown; zooms interpreted as mm by the study convention',
    'Header单位unknown':'Original header units unknown',
    '按研究约定将zoom视为mm':'zooms interpreted as mm by the study convention',
    '不支持的2D尺寸：{shape}':'Unsupported 2D shape: {shape}', '影像含非有限像素。':'Image contains non-finite pixels.',
    'ROI与原图尺寸不一致。':'ROI and image shapes differ.', 'ROI必须是离散标签。':'ROI must contain discrete labels.',
    'ROI标签应为0/1/2/3。':'ROI labels must be 0/1/2/3.', '配对2D ROI含多个层面/时相。':'A paired 2D ROI contains multiple slices or frames.',
    'ROI与原图affine不匹配；不会自动配准。':'ROI and image affines differ; automatic registration is not performed.',
    '仅支持2D/3D/4D NIfTI：{shape}':'Only 2D/3D/4D NIfTI is supported: {shape}',
    '该序列过大，请按单病例/单序列拆分。':'The series is too large. Split it into individual cases/series.',
    '体积ROI与原图affine不匹配。':'Volume ROI and image affines differ.', '体积ROI与原图shape不匹配。':'Volume ROI and image shapes differ.',
    '已取消DICOM加载':'DICOM loading cancelled',
    '当前版本不解析Enhanced/multiframe DICOM；请先转换为明确轴序的4D NIfTI。':'Enhanced/multiframe DICOM is unsupported. Convert to 4D NIfTI with explicit axes first.',
    'DICOM缺少方向/位置/PixelSpacing，不能可靠计算毫米厚度。':'DICOM orientation, position or PixelSpacing is missing; millimetre thickness cannot be determined reliably.',
    'DICOM方向/位置/像素间距无效。':'Invalid DICOM orientation, position or pixel spacing.',
    'DICOM方向余弦必须为正交单位向量。':'DICOM direction cosines must be orthogonal unit vectors.',
    'DICOM时相字段无效。':'Invalid DICOM temporal field.',
    '目录包含多个DICOM序列，请选择单个短轴序列目录。':'Multiple DICOM series found. Select one SAX series folder.',
    '没有匹配的DICOM切片。':'No matching DICOM slices.',
    '重复层面缺少时相字段，不能猜测cine帧序；请转换为4D NIfTI。':'Repeated positions lack temporal fields. Cine frame order cannot be inferred; convert to 4D NIfTI.',
    '单序列包含不同层面方向，请核对系列选择。':'The series contains differing slice orientations. Check the selected series.',
    'DICOM序列内存超过700MB，请拆分单序列。':'DICOM image memory exceeds 700 MB. Split the series.',
    'DICOM SliceThickness无效。':'Invalid DICOM SliceThickness.',
    '请载入单病例序列，不超过5000个文件。':'Load one case series with no more than 5000 files.',
    '多个NIfTI文件需采用CineSAX-层_帧_名称命名；或选择单个3D/4D文件。':'Multiple NIfTI files must use CineSAX-slice_frame_name; otherwise select one 3D/4D file.',
    '已取消加载':'Loading cancelled', '输入影像内存超过700MB，请拆分单病例序列。':'Input image memory exceeds 700 MB. Split the case series.',
    '多个体积文件不能合并为一个病例，请逐个选择。':'Multiple volumes cannot be merged into one case. Select them individually.',
    '载入影像':'Loading images',
    '目录中未发现直接属于该病例的NIfTI/DICOM文件；不会递归合并不同患者。':'No NIfTI/DICOM files found directly in this case folder. Subfolders are not merged recursively.',
    '层面/时相键重复，可能混入多个序列。':'Duplicate slice/frame keys; multiple series may be mixed.',
    '当前交互版限制为单序列不超过5000个平面。':'This interactive version supports at most 5000 planes per series.',
    '序列内存超过700MB，请拆分或降低输入范围。':'Image memory exceeds 700 MB. Split or reduce the input series.',
    '输入来源说明文件过大。':'Input provenance notes are too large.', '输入来源说明格式无效。':'Invalid input provenance-note format.',
}
EN.update({
    '选择或拖入DICOM / NIfTI（支持多选）':'Select / drop DICOM or NIfTI (multiple allowed)',
    '可拖入单张、多张单帧或多层多帧影像。':'Drop single images, single-frame sets or multi-slice/multi-frame files.',
    '文件':'Files', '文件夹':'Folder', '输入清单':'Input list', '输入文件与序列':'Input files / series',
    '已选择{count}个文件/目录':'Selected: {count} items',
    '分割文件已保存到：{path}':'Segmentation files are saved in: {path}',
    '已选择{count}个文件/目录；载入后显示层面和时相。':'{count} files / folders selected; slice/frame counts appear after loading.',
    '{files}文件 → {slices}层 × {frames}帧（{planes}平面）':'{files} files → {slices} slices × {frames} frames ({planes} planes)',
    '选择DICOM / NIfTI文件（可多选）':'Select DICOM / NIfTI files (multiple allowed)',
    '输入组织：{method}':'Input organization: {method}', '实际读取文件':'Files decoded',
    '确认层面与时相组织':'Confirm slice / frame organization',
    '将采用你确认的组织方式，原始像素和物理坐标不变。':'The confirmed layout will be used. Source pixels and physical coordinates are preserved.',
    '同位置按文件/帧序配对':'Order frames within each position',
    '按文件续接层面':'Append files as slice blocks', '按文件续接时间块':'Append files as time blocks',
    'WAIT · 待确认序列组织':'WAIT · Confirm input organization',
    '输入尚未组织；可重新选择文件或再次载入。':'Input layout not confirmed. Select files again or reload.',
    'SEGMENTED · 自动分割完成':'SEGMENTED · Segmentation complete',
    '自动分割完成':'Segmentation complete',
    '自动分割完成，厚度结果不可用：{reason}':'Segmentation complete; thickness is unavailable: {reason}',
    '该层/时相缺少影像，未补帧。':'No image for this slice/frame; no frame was synthesized.',
    '无效DICOM数值：{field}':'Invalid DICOM value: {field}',
    '文件不是可读取的DICOM影像：{file}':'Not a readable DICOM image: {file}',
    '仅支持单通道灰度DICOM影像。':'Only single-channel grayscale DICOM images are supported.',
    '请选择MR短轴影像，而不是其他DICOM模态。':'Select MR short-axis images, not another DICOM modality.',
    '当前输入包含非线性Modality LUT，请先转换为定量NIfTI。':'A nonlinear Modality LUT is present; convert to quantitative NIfTI first.',
    'DICOM逐帧元数据数量与NumberOfFrames不一致。':'Per-frame DICOM metadata count differs from NumberOfFrames.',
    'DICOM DimensionIndexValues与维度定义不一致。':'DICOM DimensionIndexValues do not match the dimension definitions.',
    'DICOM FrameTimeVector无效。':'Invalid DICOM FrameTimeVector.', 'DICOM FrameTime无效。':'Invalid DICOM FrameTime.',
    'DICOM RescaleSlope不能为0。':'DICOM RescaleSlope cannot be zero.',
    'DICOM NumberOfFrames无效。':'Invalid DICOM NumberOfFrames.',
    'DICOM实际像素帧数与NumberOfFrames不一致。':'Decoded pixel frames do not match DICOM NumberOfFrames.',
    '仅支持实值单通道NIfTI影像。':'Only real-valued, single-channel NIfTI images are supported.',
    'NIfTI第4维为频率维度，不能作为cine时相。':'The fourth NIfTI axis is frequency, not cine time.',
    '影像时间标记不完整，请确认时相组织方式。':'Temporal metadata is incomplete. Confirm frame organization.',
    '已核对并去重{count}个重复SOP平面。':'Verified and removed {count} duplicate SOP planes.',
    '输入超过5000平面或700MB影像内存限制。':'Input exceeds 5000 planes or the 700 MB image-memory limit.',
    '所选DICOM来自不同受试者、检查或空间参考系，请分批导入。':'Selected DICOM files differ in patient, study or frame of reference. Import them separately.',
    '所选DICOM含不同回波或图像分量，请分批导入。':'Selected DICOM files contain different echoes or image components. Import them separately.',
    '重复SOP实例的图像或几何不一致。':'Duplicate SOP instances contain different pixels or geometry.',
    '重复SOP实例的图像、几何或时相不一致。':'Duplicate SOP instances disagree in pixels, geometry or time.',
    'DICOM像素无法解码，请检查文件完整性或压缩解码器：{reason}':'Cannot decode DICOM pixels; check file completeness or compression decoders: {reason}',
    '请选择原始影像；ROI掩膜请放在已有ROI目录。':'Select source images; put ROI masks in the existing-ROI folder.',
    '请将DICOM和NIfTI作为独立输入组导入，避免重复合并。':'Import DICOM and NIfTI as separate input groups to avoid duplicate merging.',
    '多层NIfTI缺少有效层间距。':'A multi-slice NIfTI lacks valid slice spacing.',
    'NIfTI VolumeTiming无效。':'Invalid NIfTI VolumeTiming.',
    '所选影像方向、尺寸或像素间距不一致，请分组导入。':'Selected images differ in orientation, dimensions or pixel spacing. Import compatible groups separately.',
    '已按明确文件层号保留不同几何层面，请核对短轴覆盖。':'Differing slice geometries are retained using explicit file slice IDs; review SAX coverage.',
    '同层面图像存在平面内位置偏移；不会自动配准。':'Images at the same slice position have in-plane offsets; automatic registration is not performed.',
    '影像时间标记含非有限值。':'Image temporal markers contain non-finite values.',
    '没有可读取的影像平面。':'No readable image planes.', '不支持的序列组织方式。':'Unsupported series organization mode.',
    '文件的层面/时相标记发生冲突，请确认组织方式。':'File slice/frame labels conflict. Confirm the input organization.',
    '文件层号与物理位置不一致，请核对输入。':'File slice labels disagree with physical positions. Check the input.',
    '重复层面缺少统一时间标记，请确认文件如何组成时相。':'Repeated positions lack common temporal markers. Confirm how the files form frames.',
    '多个文件占用相同层面和时相，需确认是时间块还是层面块。':'Multiple files occupy the same slice/frame. Confirm whether they are time blocks or slice blocks.',
    '多个NIfTI按内部帧序对齐，请核对各文件的心动时相一致性。':'NIfTI files are aligned by internal frame index. Review cardiac-phase alignment between files.',
    '已按用户确认的同位置文件/帧序配对时相；该顺序不代表已验证的触发时间。':'Frames use the confirmed within-position file/frame order; this is not verified trigger timing.',
    '已按用户确认的自然文件顺序续接层面；原始物理位置未修改。':'Slice blocks use the confirmed natural filename order; original physical positions are retained.',
    '已按用户确认的自然文件顺序续接时间块。':'Time blocks use the confirmed natural filename order.',
    '组织后的层面/时相键仍有重复，请检查输入。':'Organized slice/frame keys still repeat. Check the input.',
    '序列存在{count}个缺失层面/时相组合；未补帧或插值。':'The series has {count} missing slice/frame combinations; no frames were synthesized or interpolated.',
})
ZH={
    'No image for this slice / frame':'该层面 / 时相无影像',
    'LVWT  /  CineSAX Research Workbench':'LVWT  /  CineSAX 研究工作台',
    'READY · 研究原型':'就绪 · 研究原型', 'RUNNING · 后台处理中':'运行中 · 后台处理中',
    'ERROR · 请查看日志':'错误 · 请查看日志', 'ERROR · 界面操作未完成':'错误 · 界面操作未完成',
    'RELOAD · 输入已变化':'待载入 · 输入已变化', 'CANCELLED':'已取消', 'DONE · {device}':'完成 · {device}',
    'EXISTING ROI':'已有ROI', 'Original cine':'原始cine影像', 'Segmentation':'分割结果',
    'Thickness sampling':'厚度采样', 'Load one CineSAX series':'请载入一个CineSAX序列',
    'Slice max: {value} mm':'当前层最大值：{value} mm', 'spacing {a} × {b} mm':'像素间距 {a} × {b} mm',
    'manual points':'手动点', 'study mask detector':'研究掩膜检测', 'study dilation fallback':'研究膨胀回退',
    'study spatial interpolation':'研究空间插值', 'interpolated':'插值', 'measured':'已测量',
    'JADE JSON v{version}':'JADE JSON v{version}',
    'DICOM PixelSpacing mm; LPS geometry converted to RAS':'DICOM像素间距为mm；LPS几何已转为RAS',
    'Frozen spline knots are invalid.':'冻结模型样条结点无效。',
    'Measured MWT':'实测MWT', 'ED frame':'ED帧', 'Measured ED slices':'已测ED层数',
    'AHA location':'AHA位置', 'Expected normal MWT':'预期正常MWT',
    'Upper reference limit':'正常上参考限', 'Z score':'Z值', 'Above reference limit':'超过参考上限',
    'Yes':'是', 'No':'否', 'Review notes':'复核提示', 'Research result':'研究结果',
    'Demographics/reference output incomplete':'人口学输入 / 参考结果不完整',
    'Reference limits support clinical assessment; they do not independently diagnose HCM.':'参考上限用于辅助临床评估，不能独立诊断HCM。',
    'Image/contour/thickness review':'影像 / 轮廓 / 厚度复核', 'LVWT research result':'LVWT研究结果',
    'Unassigned':'未分配',
}

def _pattern(template):
    parts=[]
    for literal,field,_,_ in Formatter().parse(template):
        parts.append(re.escape(literal))
        if field is not None:parts.append('(?P<'+field+'>.+?)')
    return re.compile(''.join(parts),re.DOTALL)

TEMPLATES=[(key,_pattern(key)) for key in dict.fromkeys([*EN,*ZH]) if '{' in key]

class Translator:
    def __init__(self,language='zh'):
        if language not in LANGUAGES:raise ValueError('Unsupported UI language: '+str(language))
        self.language=language

    def __call__(self,source,**values):
        template=(EN if self.language=='en' else ZH).get(source,source)
        return template.format(**values) if values else template

    def message(self,source,_depth=0):
        """Translate canonical diagnostics at display time, including nested notes.

        Unrecognized paths and third-party technical details pass through verbatim.
        This never changes the stored diagnostic strings or analysis data.
        """
        source=str(source)
        if _depth>8:return source
        catalog=EN if self.language=='en' else ZH
        if source in catalog:return catalog[source]
        stripped=source.strip()
        if stripped and stripped!=source:
            left=len(source)-len(source.lstrip());right=len(source.rstrip())
            return source[:left]+self.message(stripped,_depth+1)+source[right:]
        for template,pattern in TEMPLATES:
            if template not in catalog:continue
            match=pattern.fullmatch(source)
            if match:
                values={key:self.message(value,_depth+1) for key,value in match.groupdict().items()}
                return catalog[template].format(**values)
        for separator in ['\n','  |  ',' | ','；',' · ']:
            if separator in source:
                join='; ' if separator=='；' and self.language=='en' else separator
                return join.join(self.message(part,_depth+1) for part in source.split(separator))
        exception=re.fullmatch(r'(\w+(?:Error|Exception)): (.+)',source,re.DOTALL)
        if exception:return exception[1]+': '+self.message(exception[2],_depth+1)
        # Progress formats retain Qt's %v/%m/%p placeholders.
        if '  %v / %m' in source:
            stage,suffix=source.split('  %v / %m',1)
            return self.message(stage,_depth+1)+'  %v / %m'+suffix
        return source
