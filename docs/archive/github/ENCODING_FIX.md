# 脚本编码问题修复说明

## 问题描述

原始脚本中的中文字符在 Windows 环境下会出现两个问题：

### 问题 1: 乱码显示
```
========================================
Markdown State Tracker - Conda 蹇€熷惎鍔?
========================================
[1] 妫€鏌?Conda 瀹夎...
```

**原因**: Windows 控制台默认使用 GBK 编码，而文本文件是 UTF-8 编码。

### 问题 2: PowerShell 解析错误
```
所在位置 D:\Apps\Python\lab\personal_prompt\quick_start.ps1:103 字符: 23
+ Read-Host "鎸?Enter 鍏抽棴"
+                       ~
字符串缺少终止符: "。
```

**原因**: PowerShell 在解析 UTF-8 文件时，中文字符可能导致语法错误。

---

## 解决方案

我已将所有脚本改为**纯英文版本**，彻底避免编码问题：

### 修复的文件

1. **quick_start.ps1** (PowerShell 脚本)
   - 所有中文改为英文
   - 使用标准 ASCII 字符
   - 保持功能完全一致

2. **quick_start.bat** (批处理脚本)
   - 所有中文改为英文
   - 使用标准 ASCII 字符
   - 保持功能完全一致

---

## 现在可以正常使用

### PowerShell 版本

```powershell
.\quick_start.ps1
```

**预期输出**:
```
========================================
Markdown State Tracker - Quick Start
========================================

[1] Checking Conda installation...
  [OK] Conda installed: conda 24.1.2

[2] Setting up Conda environment...
  [OK] Environment already exists

[3] Activating environment...
  [OK] Environment activated

...
```

### 批处理版本

```cmd
quick_start.bat
```

**预期输出**:
```
========================================
Markdown State Tracker - Quick Start
========================================

[1] Checking Conda installation...
  [OK] Conda installed

[2] Setting up Conda environment...
  [OK] Environment already exists

...
```

---

## 测试验证

现在请重新运行脚本：

```powershell
# PowerShell
.\quick_start.ps1

# 或 CMD
quick_start.bat
```

应该不再有乱码和解析错误！

---

## 其他建议

如果你仍然遇到问题，可以：

### 方法 1: 手动运行命令（推荐）

不使用脚本，直接复制粘贴命令：

```bash
# 1. 创建环境
conda create -n markdown_tracker python=3.11 -y

# 2. 激活环境
conda activate markdown_tracker

# 3. 安装依赖
pip install -r requirements.txt

# 4. 快速测试
python main.py --init
python main.py --skip-extraction

# 5. 查看统计
python main.py --stats
```

### 方法 2: 查看文档

打开 `QUICKSTART_CONDA.md`，有详细的逐步说明（纯文本，无编码问题）。

---

## 技术说明

### 为什么会有编码问题？

1. **文件编码**: 代码文件通常使用 UTF-8 编码（支持全球字符）
2. **控制台编码**: Windows 控制台默认使用 GBK/CP936（中文 Windows）
3. **不匹配**: UTF-8 编码的中文在 GBK 控制台显示会乱码

### 为什么用英文解决？

1. **ASCII 字符**: 英文字母、数字、标点符号在所有编码中都一致
2. **兼容性**: 不需要考虑编码转换
3. **国际化**: 更适合开源项目

### 如果确实需要中文？

可以设置控制台编码：

```powershell
# PowerShell
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
chcp 65001

# CMD
chcp 65001
```

但不推荐，因为：
- 需要每次手动设置
- 某些终端可能不支持
- 可能影响其他程序

---

## 总结

✅ **问题已修复** - 所有脚本改为纯英文  
✅ **功能不变** - 所有步骤完全一致  
✅ **无需配置** - 直接运行即可  
✅ **跨平台** - 英文在所有系统都正常  

现在请重新运行脚本，应该能正常工作了！🎉
