# 猫耳 + 漫播每周自动数据仓库

这个 repository 用于每周自动抓取：

- 猫耳 / Missevan 在播剧数据
- 漫播周数据
- 自动读取上一周原始数据
- 计算周增、周增率
- 每周五北京时间 04:00 通过 GitHub Actions 自动运行

## 目录

```text
.
├── .github/
│   └── workflows/
│       └── weekly_data.yml
├── data/
│   ├── 猫耳在播剧id（跑程序版）.xlsx
│   └── 漫播临时周数据链接.xlsx
├── output/
│   ├── 猫耳周数据MMDD.xlsx
│   ├── 猫耳周数据对比版MMDD.xlsx
│   ├── 漫播周数据MMDD.xlsx
│   └── 漫播周数据对比版MMDD.xlsx
├── scripts/
│   ├── fetch_maoer.py
│   ├── compare_maoer.py
│   ├── fetch_manbo.py
│   └── compare_manbo.py
├── requirements.txt
└── README.md
```

## 1. 第一次使用

把两个输入 Excel 放进 `data/`：

```text
data/猫耳在播剧id（跑程序版）.xlsx
data/漫播临时周数据链接.xlsx
```

其中：

### 猫耳

需要至少有一个能够定位剧集的列：

- `url`
- 或 `id`
- 或 `剧id`
- 或 `剧集id`

如果同时存在 `url` 和 `id`，程序优先使用 `url`。

### 漫播

需要有：

```text
url
```

列。

## 2. GitHub Secret

猫耳接口如果需要 Cookie，不要把 Cookie 写进代码。

进入：

```text
GitHub repository
→ Settings
→ Secrets and variables
→ Actions
→ New repository secret
```

建立：

```text
MISSEVAN_COOKIE
```

Value 填当前可用的猫耳/Missevan Cookie。

如果之前把真实 Cookie 提交进过公开 repository，建议先更换 Cookie，再只把新的 Cookie 放进 Secret。

## 3. 自动运行时间

GitHub Actions 使用 UTC。

工作流：

```yaml
cron: '0 20 * * 4'
```

对应：

```text
UTC：周四 20:00
北京时间：周五 04:00
```

另外保留 `workflow_dispatch`，所以可以在 GitHub Actions 页面手动运行。

## 4. 输出

每周运行会产生四类文件。

### 猫耳原始周数据

```text
output/猫耳周数据0925.xlsx
```

这是本周抓取的原始快照。

### 猫耳周增对比

```text
output/猫耳周数据对比版0925.xlsx
```

上一周和本周按照 `url` 匹配，计算：

- `ID周增`
- `总弹幕周增`
- `追剧周增`
- `播放周增`
- `追剧周增率`
- `播放周增率`
- `比例差`
- `本周ID活跃比`

### 漫播原始周数据

```text
output/漫播周数据0925.xlsx
```

### 漫播周增对比

```text
output/漫播周数据对比版0925.xlsx
```

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
