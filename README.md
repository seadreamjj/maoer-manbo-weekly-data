# 猫耳 + 漫播每周自动数据仓库

这个 repository 用于每周自动抓取：

- Missevan 在播剧数据
- 克拉克拉周数据
- 自动读取上一周原始数据
- 计算周增、周增率
- 每周五北京时间 04:00 通过 GitHub Actions 自动运行

## 目录


```


## 4. 输出

每周运行会产生四类文件。



上一周和本周按照 `url` 匹配，计算：

- `ID周增`
- `总弹幕周增`
- `追剧周增`
- `播放周增`
- `追剧周增率`
- `播放周增率`
- `比例差`
- `本周ID活跃比`



按照 `url` 匹配，计算主要数值字段的：

```text
本周值
周增
周增率
```

## 5. 重要设计

程序不会拿“对比版”作为下一周的历史基准。

历史搜索只认：

```text
猫耳周数据MMDD.xlsx
漫播周数据MMDD.xlsx
```

不会认：

```text
猫耳周数据对比版MMDD.xlsx
漫播周数据对比版MMDD.xlsx
```

这样可以避免：

```text
本周对比版
    ↓
下一周又被当作历史原始数据
    ↓
产生错误的二次比较
```

## 6. 手动测试

本地安装：

```bash
pip install -r requirements.txt
```

然后：

```bash
python scripts/fetch_maoer.py
python scripts/compare_maoer.py

python scripts/fetch_manbo.py
python scripts/compare_manbo.py
```

如果猫耳 Cookie 已设置：

macOS / Linux：

```bash
export MISSEVAN_COOKIE='你的Cookie'
```

Windows PowerShell：

```powershell
$env:MISSEVAN_COOKIE="你的Cookie"
```

## 7. 第一次运行

如果 repository 里面还没有上一周数据：

```text
fetch
    ↓
生成本周原始数据
    ↓
compare
    ↓
发现没有上一周
    ↓
只输出本周数据，不计算周增
```

从第二周开始自动计算周增。

## 8. 关于 GitHub Actions 提交

workflow 会自动：

```text
抓取
→ 生成 Excel
→ git add
→ git commit
→ git push
```

所以 repository 会逐周留下历史文件。

如果不希望把 Excel 提交进 repository，可以后续改成 GitHub Artifacts、Release 或 Supabase 存储。
