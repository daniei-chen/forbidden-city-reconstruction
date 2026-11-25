# 紫禁城三维复原

以公开测绘资料、地图轮廓和实景影像为依据，持续复原北京紫禁城的可编辑 Blender 三维模型、建筑细节与沉浸式漫游。

**[下载可编辑的 Blender 工程](https://github.com/daniei-chen/forbidden-city-reconstruction/releases/latest)**。用 Blender 4.5 打开 `.blend` 即可查看、测量和编辑，场景单位为米。主场景覆盖宫墙、护城河和宫院，可从顶部场景选择器切换到文华殿、浴德堂、澄瑞亭和堆秀山的四段漫游。

公开工程收录了太和殿内景、文渊阁、文华殿和武英殿组群、浴德堂及御花园北部的细化模型。万春亭、千秋亭包含亚字台基、四面踏道、重檐与可仰视的藻井。公开版使用程序化材质和原生汉字匾额，保留照片作为考据来源；工程本身不包含原始照片和航拍文件。匾额的笔迹和满文暂未复原。

## 从源码重建基础场景

使用 Blender 4.5。将 `requirements.txt` 中的依赖安装到 **Blender 自带的 Python** 环境中。Windows 便携版的解释器位于 Blender 目录下的 `4.5/python/bin/python.exe`，可用它运行 `-m pip install -r requirements.txt`。如果该环境还没有 pip，先用同一解释器运行 `-m ensurepip`。

在仓库根目录执行下列命令。命令假定 `blender` 在 PATH 上，也可使用可执行文件的完整路径。

```text
blender --background --factory-startup --python-exit-code 1 --python source/build_scene.py
```

输出 `The_Forbidden_City_1to1.blend`。在命令末尾加上 `-- --preview` 可额外渲染一张太和殿预览，加上 `-- --export` 可导出 GLB。可通过 `PALACE_CJK_FONT` 环境变量指定本机的中文字库，生成匾额文字。Windows 安装楷体时脚本会自动使用系统字体。

要构建御花园两组细化建筑，运行：

```text
blender --background --factory-startup --python-exit-code 1 --python source/build_scene.py -- --garden --preview
```

这会生成 `The_Forbidden_City_Imperial_Garden_Base.blend` 与 `renders/fubi_garden_preview.png`。浮碧亭、澄瑞亭各有贯通水池的单券桥、三开间柱网、可穿行的抱厦和分层藻井；摛藻堂、位育斋位于两池北岸。各组使用同一次地图投影，桥、瓦、栏板、格扇和天花都可以在 Blender 中编辑。省略 `--preview` 可只构建模型。

仓库可在没有摄影贴图的情况下独立构建。构建结果使用简化的表面材质，和本地包含实拍贴图、城外扩展环境、细化瓦作及漫游动画的 Blender 主工程是不同版本。源码中的 `1to1` 文件名表示场景单位采用实际米制。

## 细化脚本和校核

[verification/](verification/) 保存各版的建筑尺寸依据、模型参数和重开检查结果。报告中的文件名对应各自的检查版本，历史报告中的路线和构件检查不等于实地测量。

`source/refine_paired_halls_scene.py`、`refine_yude_tang_scene.py`、`refine_garden_scene.py`、`refine_north_garden_scene.py` 和 `refine_garden_twins_scene.py` 是增量脚本。各脚本的 `BASE` 指向它所需的上一版工程；`build` 以该工程为起点另存版本，`verify` 检查相应版本中的构件。直接体验最新场景请下载 Release 的 `.blend`，基础构建命令不会生成相同画面。`source/prepare_public_release.py` 以已建成的主工程为输入，生成并校验无需外部素材的公开副本。

## 资料与精度

- `source/palace_osm_full.xml` 是从 OpenStreetMap 导出的地图底稿。© [OpenStreetMap 贡献者](https://www.openstreetmap.org/copyright)，数据适用 [ODbL 1.0](https://opendatacommons.org/licenses/odbl/1-0/)。
- 太和殿柱网参考张学芹、刘畅《康熙三十四年建太和殿大木结构研究》表二、表三。建筑总高、形制等参照[故宫博物院太和殿资料](https://www.dpm.org.cn/explore/building/236465.html)。[测绘论文](https://www.dpm.org.cn/Uploads/pdf/5077/T00035_00.pdf)
- 文渊阁柱网与楼层参考刘榕《从实测谈文渊阁结构与艺术特点》，《故宫博物院院刊》1993 年第 3 期。屋面高度、书橱位置与表面细节包含推定。[故宫博物院文渊阁资料](https://www.dpm.org.cn/explore/building/236513.html)
- [浮碧亭](https://www.dpm.org.cn/explore/building/236498.html)和[澄瑞亭](https://www.dpm.org.cn/explore/building/236443.html)的约 8 米通面阔、三开间、单券桥、绿瓦黄剪边与八方双龙藻井来自建筑说明。池岸和亭址取地图原始轮廓。梁枋标高、雕刻、地坪和植物的位置有照片推定。
- [摛藻堂](https://www.dpm.org.cn/explore/building/236432.html)与[位育斋](https://www.dpm.org.cn/explore/building/236445.html)的开间、硬山屋顶取馆方形制，轮廓取地图。格扇、梁枋和材质是重建件。
- 浴德堂平剖面参考[故宫古建部提供的测绘图](https://www.dpm.org.cn/Uploads/File/2021/11/08/u6188edf18abbd.pdf)，砖石及锅炉参考[现场记录](https://www.dpm.org.cn/Uploads/File/2019/07/17/u5d2e998b92f38.pdf)。钦安殿柱脚、柱头和檐檩尺寸参考[大木测绘研究](https://www.dpm.org.cn/Uploads/File/2018/06/04/u5b1521c1583e4.pdf)。
- [万春亭和千秋亭](https://www.dpm.org.cn/explore/building/236521.html)的平面与屋面关系参考[《明堂式道教建筑初探》图 14](https://img.dpm.org.cn/Uploads/File/2020/04/08/u5e8d77d699010.pdf)。原构件的精确标高、瓦件尺度和雕刻深度仍待进一步测绘。

项目仍在逐栋核对。米制场景、公开资料中有记录的尺寸与基于照片推定的部分有不同的证据强度。全城尚无逐物测量及逐像素比对记录。第三方原始影像、航拍和论文扫描件保留在本地资料库。
