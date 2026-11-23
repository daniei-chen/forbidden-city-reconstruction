# 紫禁城三维复原

以公开测绘资料、地图轮廓和实景影像为依据，持续复原北京紫禁城的可编辑 Blender 三维模型、建筑细节与沉浸式漫游。

本仓库提供生成原生 `.blend` 场景的 Python 源码和地图底稿。场景以米为单位，包含宫墙、护城河、院落和建筑。太和殿与文渊阁有独立的构件集合，可在 Blender 中查看、测量和编辑。

## 在 Blender 中重建

使用 Blender 4.5。将 `requirements.txt` 中的依赖安装到 **Blender 自带的 Python** 环境中。Windows 便携版的解释器位于 Blender 目录下的 `4.5/python/bin/python.exe`，可用它运行 `-m pip install -r requirements.txt`。如果该环境还没有 pip，先用同一解释器运行 `-m ensurepip`。

在仓库根目录执行下列命令。命令假定 `blender` 在 PATH 上，也可使用可执行文件的完整路径。

```text
blender --background --factory-startup --python-exit-code 1 --python source/build_scene.py
```

输出 `The_Forbidden_City_1to1.blend`。在命令末尾加上 `-- --preview` 可额外渲染一张太和殿预览，加上 `-- --export` 可导出 GLB。可通过 `PALACE_CJK_FONT` 环境变量指定本机的中文字库，生成匾额文字。Windows 安装楷体时脚本会自动使用系统字体。

仓库可在没有摄影贴图的情况下独立构建。构建结果使用简化的表面材质，和本地包含实拍贴图、城外扩展环境、细化瓦作及漫游动画的 Blender 主工程是不同版本。源码中的 `1to1` 文件名表示场景单位采用实际米制。

## 资料与精度

- `source/palace_osm_full.xml` 是从 OpenStreetMap 导出的地图底稿。© [OpenStreetMap 贡献者](https://www.openstreetmap.org/copyright)，数据适用 [ODbL 1.0](https://opendatacommons.org/licenses/odbl/1-0/)。
- 太和殿柱网参考张学芹、刘畅《康熙三十四年建太和殿大木结构研究》表二、表三。建筑总高、形制等参照[故宫博物院太和殿资料](https://www.dpm.org.cn/explore/building/236465.html)。[测绘论文](https://www.dpm.org.cn/Uploads/pdf/5077/T00035_00.pdf)
- 文渊阁柱网与楼层参考刘榕《从实测谈文渊阁结构与艺术特点》，《故宫博物院院刊》1993 年第 3 期。屋面高度、书橱位置与表面细节包含推定。[故宫博物院文渊阁资料](https://www.dpm.org.cn/explore/building/236513.html)

项目仍在逐栋核对。米制场景、公开资料中有记录的尺寸与基于照片推定的部分有不同的证据强度。全城尚无逐物测量及逐像素比对记录。第三方原始影像、航拍和论文扫描件保留在本地资料库。
