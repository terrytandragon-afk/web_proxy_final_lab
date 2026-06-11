# 期末实验报告

报告源文件：

```text
report/final_report.tex
```

生成 PDF：

```powershell
cd E:\eve_jump\web_proxy_final_lab\report
latexmk -xelatex -interaction=nonstopmode final_report.tex
```

生成结果：

```text
report/final_report.pdf
```

清理 LaTeX 中间文件：

```powershell
latexmk -c
```

提交前可以在 `final_report.tex` 首页修改姓名、学号、班级、课程名称和指导教师。
