# 期末实验报告

报告源文件：

```text
report/final_report.tex
```

课程提供的原始规范文件：

```text
课程设计报告封面.docx
课程设计报告书写提纲.doc
课程设计报告排版格式模板.doc
```

当前 LaTeX 已按照规范设置课程评价封面、中英文题名与摘要、五号宋体正文、标题字号、参考文献和带注释代码附录。

手工验收截图说明：

```text
report/figures/README.md
```

将截图按指定文件名放入 `report/figures`，重新编译后会自动替换报告中的占位框。

生成 PDF：

```powershell
cd E:\eve_jump\web_proxy_final_lab\report
latexmk -xelatex -interaction=nonstopmode final_report.tex
```

生成结果：

```text
report/final_report.pdf
```

如果 `final_report.pdf` 正被 VS Code 或 PDF 阅读器占用，Windows 会拒绝覆盖。可以先关闭预览，或使用备用文件名编译：

```powershell
latexmk -xelatex -jobname=final_report_revised -interaction=nonstopmode final_report.tex
```

清理 LaTeX 中间文件：

```powershell
latexmk -c
```

提交前可以在 `final_report.tex` 首页修改姓名、学号、班级、课程名称和指导教师。
