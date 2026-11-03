# ERA5 气温示例

`era5_t2m.yml` 使用仓库内 [ERA5 示例数据](../demo_data/README.md)。源文件保持三个时次与原始 0.25° 网格；默认仅加载第一个时刻。

## 命令

```bash
earthreel snapshot examples/era5_t2m.yml --output outputs/era5_t2m.png
earthreel render examples/era5_t2m.yml --output outputs/era5_t2m.mp4
# 快速预览另一个时刻
earthreel render examples/era5_t2m.yml --output outputs/preview.mp4 --time-index 2 --width 640 --height 360 --fps 6 --duration 2
```

相对数据路径以 YAML 文件目录为基准，输出路径以当前工作目录为基准。使用绝对配置路径时可从任意目录运行。已有媒体或同名运行记录都默认拒绝覆盖，确认替换时添加 `--overwrite`。

## 配置

| 配置项 | 含义 / 默认值 |
| --- | --- |
| `data.path` | NetCDF 或未压缩 GRIB1/GRIB2 文件路径，必填 |
| `data.variable` | 气温变量名，默认 `t2m` |
| `data.latitude`, `data.longitude`, `data.time` | 默认 `latitude`、`longitude`、`valid_time` |
| `data.time_index` | 从 0 开始的时次索引，默认 0 |
| `display.title` | 可选标题覆盖；留空时显示数据变量的 `long_name` |
| `display.layout` | `single` 单球或 `dual` 双球，默认 `dual`；可用 `--layout` 覆盖 |
| `display.interpolation` | 默认 `nearest`，每格独立着色，不做格点间平滑；可设为 `linear` 恢复连续插值 |
| `display.source`, `attribution` | 数据来源与授权，保存在配置和运行记录中，不显示在画面上 |
| `display.cmap` | Matplotlib 色表名称，默认 `coolwarm` |
| `display.vmin`, `vmax` | 摄氏度范围，默认 −60 / 40，全片固定 |
| `display.vcenter` | 色表中性色对应的数值，默认 0°C；设为 `null` 则使用线性映射 |
| `output.width`, `height` | 默认 2560 / 1440（1440p）；必须为偶数且不少于 128 |
| `output.fps`, `duration` | 默认 60 fps / 20 秒；帧数为四舍五入后的乘积 |
| `output.crf`, `preset` | 默认 22 / `slow`，控制 H.264 画质和编码速度；支持 `--crf` / `--preset` 覆盖 |
| `camera.longitude`, `latitude` | 左球初始观察中心，默认 110°E / 30°N；右球经度加 180°、纬度取相反数 |

命令行 `--layout`、`--time-index`、`--width`、`--height`、`--fps`、`--duration` 覆盖对应配置。PNG 始终只输出一帧；视频以固定仰角和距离匀速环绕，最后一帧不重复首帧。长度按实际帧数 / fps 计算。单球模式只使用第一个相机视角，并放大地球；双球模式保持两个反向视角。

两个地球使用相同数据、球面几何和色标，只有相机不同，便于对照同一时刻的全球分布。左右观看方向始终严格相反；默认左球朝向北半球、右球朝向南半球，因此南北极都处于各自的可见半球中。地平线附近仍存在球面投影压缩，环绕过程会让这些区域逐渐移向画面中央。

## 数据与显示语义

- 仅支持全球规则经纬网格、单文件、温度或速度分量变量，变量维度为一维时间 × 一维纬度 × 一维经度（顺序不限），也支持 GRIB 单时次的标量时间。未选择的额外维度、区域网格、二维曲线坐标明确报错。
- 支持常见 K 和 °C 温度单位，以及 m/s 速度分量；温度按需转换为 °C，速度保留 m/s；缺测始终保留，不变成零。纬度升降序和两种经度约定均会随数据同步整理。
- 经度周期连接，允许数值一致的重复端点。`nearest` 模式保留每个源格点的值，极区以独立的三角单元闭合，不平均极区数值。仅 `linear` 模式将极点合并为单顶点、取原极区行均值；若该行含缺测则该极点缺测。这些操作记入运行记录。
- 原始格点不降采样。默认 `nearest` 为每个源格点建立一个独立单元，边界取相邻经纬度中点、极区边界截到 ±90°；一个单元使用一个原始数值，缺测单元为灰色，不做相邻格点的均值或颜色插值。可选 `linear` 使用原来的顶点插值。科学层始终关闭光照。
- 地球内层使用完全不透明的 NASA Blue Marble 海陆底图；气温层同样不透明并裁剪背面，防止背面场透出。有效气温区域覆盖底图，不混合底图颜色。
- 顶部一行显示 EarthReel logo、变量长名称和 UTC 时间，释放纵向空间以放大地球。双球直径约占画面高度 77%，单球约占 85%；标题较长时缩小字号以避免与时间重叠。左下角不显示来源或版权，底图来源仅在文档和运行记录中保留。logo 的 SVG 矢量原稿和视频用透明 PNG 由同一套轮廓路径生成。文字和色标数字统一使用随包分发的 Noto Sans Regular（SIL OFL 1.1，可商用）。当前字体覆盖西文标签；中文标签需另配 CJK 字体。
- 右侧色标使用较长的纵向布局及变量显示单位（°C 或 m/s），两端三角形表示超出范围的数值使用端点颜色，不再显示 clipped 文字；数值本身不裁剪。色标与气温图层共用同一张颜色表。
- 默认采用以 0°C 为中心的双色归一化：−60～0°C 对应冷色半边，0～40°C 对应暖色半边。色标刻度仍沿数值范围线性分布，所以 0°C 的中性色位于色标高度的 60%，而非几何中心。`vcenter` 必须严格位于 `vmin` / `vmax` 之间，或设为 `null`。
- 每个输出有 JSON 运行记录，包含已解析配置、数据校验值、所选时间、原始单位、显示规则、软件版本和帧数。用 `config` 字段内容保存为 YAML/JSON 后可作为新配置运行；数据绝对路径在其他机器上需要调整。
- 使用离屏渲染及 imageio-ffmpeg 的 H.264 编码，输出像素格式为 yuv420p。生成时直接压缩，采用帧间预测、最多 3 个连续 B 帧、最长 5 秒 GOP；MP4 元信息前置以方便在线播放。默认 CRF 22 / slow，相较此前约 CRF 10 的高画质设置更侧重文件体积；CRF 越低画质越高，文件通常越大。`slow` 用更多编码时间换取压缩效率。视频压缩可能带来轻微色差，精确静帧以 PNG 为准。

## Linux 无显示环境

先安装系统图形库及 Xvfb，再运行小尺寸检查：

```bash
sudo apt-get install -y xvfb libgl1 libegl1 libopengl0
LIBGL_ALWAYS_SOFTWARE=1 xvfb-run -a earthreel snapshot examples/era5_t2m.yml --output outputs/linux-check.png --width 640 --height 360
```

底图和字体来源、授权见 [素材说明](../src/earthreel/assets/README.md)。首版不包含在线下载、独立海岸线图层、云体、交互窗口或数据随时间演变。

## IFS GRIB 气温示例

先安装可选读取依赖：`uv pip install -e '.[grib]'`（或 `python -m pip install -e '.[grib]'`）。
`ifs_t2m.yml` 使用本地下载的 `demo_data/ifs/20261030180000-0h-oper-fc-sfc.grib2`，
不随仓库分发。所有新数据默认忽略，仅在明确指定时使用 `git add -f` 手动跟踪。

```bash
earthreel snapshot examples/ifs_t2m.yml --output outputs/ifs_t2m_0h.png
earthreel render examples/ifs_t2m.yml --output outputs/ifs_t2m_0h.mp4
```

文件头自动识别 GRIB；`data.variable: t2m` 使用 cfgrib 的 CF 变量名筛选，因此多变量地表包只加载所需变量。
原始 GRIB 参数名为 `2t`，解码后为 `t2m`。读取不生成 `.idx` 缓存文件。
默认 `data.time: valid_time` 为预报有效时间，而非起报时间；单时次文件的 `time_index` 只能为 0。
此例为 2026-10-30 18:00 UTC 起报的 0h 场，全球 1801 × 3600、0.1° 规则经纬度网格，
保留全部格点，K 转 °C，全片数据时刻固定。仅支持已有的全球规则网格，ICON 原生三角网格仍不支持。

数据来自 ECMWF IFS Open Data，采用 CC BY 4.0；基于 ECMWF 数据和产品制作，具体来源记入场景配置和运行记录。

## IFS 表层海流分量

`ifs_sve.yml` 与 `ifs_svn.yml` 使用同一份本地 IFS 0h GRIB2 文件，分别读取东西向、南北向表层海流速度。
`SVE` 正值向东、负值向西；`SVN` 正值向北、负值向南。两者均保留原始 m/s 数值和缺测，
共用 −1～1 m/s、以 0 为中心的色标（红色为正、蓝色为负）。超出范围的值只在颜色上使用端点颜色。
灰色表示缺测，不以 0 填充。显示的是固定时刻的速度分量分布，相机旋转不代表洋流随时间演变。

```bash
earthreel render examples/ifs_sve.yml --output outputs/ifs_sve_0h.mp4
earthreel render examples/ifs_svn.yml --output outputs/ifs_svn_0h.mp4
```

数据入口 `load_field` 返回数值、名称和显示单位，渲染色标及运行记录随变量单位更新；
原有 `load_temperature` 保留为只接受温度的兼容入口。运行记录中的 `valid_range` 使用显示单位，
温度场另保留 `valid_range_c`。
