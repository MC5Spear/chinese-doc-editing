# 中文文档编辑与审计

`chinese-doc-editing` 是一个面向 AI 编程助手的中文文档编辑技能，用于技术文档、规则库、技能说明和代码注释的写作、更新与审查。

它关注的不只是句子是否通顺，而是文档能否让读者直接理解当前事实并完成任务：要求变化后修改原有结论，而不是不断追加补丁；把必要的前提、关系和操作讲清楚，而不是只把文字变短；使用自然准确的中文，而不是让读者猜测自创术语。

## 适合处理什么问题

- **新旧说法并存**：检查当前依据，修正失效正文及相关引用，让读者不必考证修订顺序。
- **文档写成工作日志**：移走无用过程，保留解释当前行为所需的设计理由、限制和升级说明。
- **内容齐全却难以照做**：按读者任务重组，补足有依据的前提、顺序、因果和例外。
- **中文表达生硬**：处理英文直译、自创黑话和不一致的术语，准确保留技术标识。
- **代码注释过期或重复代码**：维护接口约定、失败行为和实现理由，删除没有额外信息的复述。

编辑不得擅自改变事实、已批准要求、权限或确定程度。材料冲突又无法确认时，应列出差异和所需决定，而不是编造一个统一答案。

## 安装

本项目按 [Agent Skills Specification](https://agentskills.io/specification) 组织。仓库根目录就是一个完整技能，入口为 [SKILL.md](<./SKILL.md>)；安装时保留整个目录，不能只复制入口文件，因为正文会按需引用方法文档和脚本。

### 使用 Claude Code

以下按 [Claude Code 官方技能目录约定](https://code.claude.com/docs/en/skills#where-skills-live) 安装到个人技能目录，供该账号的本地项目会话使用。需要先安装 Git 和 Claude Code。以下命令用于首次安装；如果目标目录已有同名技能，先检查并保存现有内容，不要直接覆盖。

**macOS / Linux：**

```sh
mkdir -p ~/.claude/skills
git clone https://github.com/MC5Spear/chinese-doc-editing.git ~/.claude/skills/chinese-doc-editing
```

**Windows PowerShell：**

```powershell
New-Item -ItemType Directory -Force "$HOME/.claude/skills" | Out-Null
git clone https://github.com/MC5Spear/chinese-doc-editing.git "$HOME/.claude/skills/chinese-doc-editing"
```

安装后，在需要处理的项目中启动新的 Claude Code 会话，输入 `/chinese-doc-editing`，后面附上任务与文件范围。若命令未被识别，先检查 [SKILL.md](<./SKILL.md>) 是否直接位于个人技能目录下的 `chinese-doc-editing` 文件夹中，避免多套一层解压目录；再按官方说明检查技能发现设置。

### 使用其他支持 Agent Skills 的助手

将完整仓库克隆或下载到本地，保持技能目录名为 `chinese-doc-editing`，再放入目标助手文档指定的技能目录。不同助手的目录位置和调用方式不同，不能直接套用 Claude Code 的路径与斜杠命令。

本项目提供通用格式的技能文件；上述 Claude Code 安装方式依据官方文档，尚未完成该宿主的实际运行验证。

## 如何使用

开始时说明三件事：**处理哪些文件、文档给谁阅读、允许审查还是直接修改**。已批准需求、当前实现或发布信息是判断依据时，一并提供，避免助手凭文字新旧猜测权威。

例如，在已安装技能的 Claude Code 会话中，可以先进行只读审查：

```text
/chinese-doc-editing 审查 docs/ 中的安装说明，目标读者是第一次使用本项目的开发者。先不要修改文件，指出过期结论、缺少的操作前提和难以理解的表达，并说明依据。
```

也可以直接授权整理：

```text
/chinese-doc-editing 根据当前配置和已批准需求，重写 docs/ 中的部署说明。可以修改相关文档；先确认原文已有可恢复的 Git 基线。完成后说明修改范围、验证结果和仍需确认的事项，不提交或推送。
```

### 修改前的版本保护

实质性修改项目文档前，技能默认要求 Git 版本保护：相关原文已经保存且能够恢复，已有改动与本次改动可以区分。已有合适提交就复用；存在未提交内容时，按授权先保存。仅有 Git 仓库，并不意味着当前原文已经受到保护。

有授权和可靠基线后，助手应直接完成必要的重写、删除与整合，不必为可恢复的编辑反复确认。编辑、提交和推送是不同权限，以具体任务授权为准。只读审查和对话内短段改写不要求初始化仓库；非 Git 环境需先确认可接受的等效保护办法。

### 按需检查术语

[术语检查脚本](<./scripts/lint_terms.py>)需要 Python 3，只使用标准库；阅读和执行技能中的编辑方法不需要安装 Python。脚本只报告候选问题，不修改文件，也不能判断文档事实是否正确、解释是否完整。

在终端进入安装后的技能目录，将下列占位路径换成需要检查的文档或项目目录：

```sh
python scripts/lint_terms.py "<待检查的文档或目录>"
```

如果系统用 `python3` 启动 Python 3，将命令开头的 `python` 换为 `python3`。扫描 Markdown 正文及部分源码注释，支持的文件类型与跳过规则见[工具说明](<./references/tools.md#三术语表与术语检查>)。

默认退出码 `0` 表示已扫描内容没有 error，仍可能有 warning；`1` 表示存在 error，启用 `--strict` 后 warning 也会使退出码变为 `1`；`2` 表示参数、路径或词表读取等已识别的使用错误。读取失败或检查中断不能视为通过。结合上下文处理报告，再完整审读文档。

项目已有专用术语时，可以使用 `--terms` 加载经批准的 TSV 词表。生成方法见[领域覆盖表](<./references/terminology.md#一领域覆盖表最高优先级用户自建>)，不要将 Markdown 批准记录直接作为扫描输入。

## 内容结构

技能按“抽象原则、方法论、工具”三层组织。助手激活技能时先读取入口，再按任务需要读取附件；人工阅读可以从感兴趣的问题进入。

| 材料 | 回答什么问题 |
| --- | --- |
| [技能入口](<./SKILL.md>) | 编辑的目标、共同边界、四项原则和版本保护前提是什么 |
| [编辑方法](<./references/editing-method.md>) | 如何辨认依据、解决冲突、更新和重组内容，再验证结果 |
| [中文表达方法](<./references/controlled-chinese.md>) | 如何讲清前提与关系，避免直译、过度压缩和语义变化 |
| [代码注释方法](<./references/code-comment.md>) | 哪些信息值得写进注释，如何随代码维护 |
| [工具说明](<./references/tools.md>) | 如何使用 Git、搜索和术语检查辅助编辑 |
| [术语表](<./references/terminology.md>) | 已批准的用词决定及项目覆盖规则是什么 |

## 反馈与贡献

欢迎通过 [Issues](https://github.com/MC5Spear/chinese-doc-editing/issues) 提供问题和改写建议，也可以提交 Pull Request。说明目标读者、原文、具体理解困难及建议理由；公开示例请先去掉私有信息。

修改规则时，检查受影响的解释、例子和引用是否一致。术语条目与级别的变更应说明语境与理由，经维护者确认后同步到词表和脚本，不能只为消除扫描提示而放宽规则。

## 许可与来源

项目文档与脚本采用 [MIT 许可](<./LICENSE>)。允许使用、修改和再分发，分发时须按许可保留版权与许可声明。

通用词表参考了 `ninehills/public-skills` 的 `deslop-zh` 和 `KKKKhazix/human-writing`。对应来源、适用内容及上游 MIT 许可全文见[第三方声明](<./THIRD_PARTY_NOTICES.md>)；分发相关内容时一并保留。
