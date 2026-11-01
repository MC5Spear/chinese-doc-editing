#!/usr/bin/env python3
"""术语检查：扫描中文文档与代码注释中的禁用词和待规范词。

用法：
    python3 lint_terms.py PATH [PATH ...] [--strict] [--terms FILE] [--skip-path REGEX]

- error：术语表有明确映射的词，默认导致非零退出。
- warning：需要人工判断语境的词（如「对齐/阻塞/落盘」），默认不导致失败；--strict 时也失败。
- 扫描范围：.md/.markdown 全文；.py 的 # 注释与 docstring；.sh/.yaml/.yml 的 # 注释；
  .c/.cu/.cpp/.h/.hpp/.js/.jsx/.ts/.tsx/.mjs/.cjs 的 // 行注释与 /* */ 块注释内容
  （含 JSDoc）；.toml 全行扫（仅跳过纯注释行）；其余扩展名不扫。未识别的「--」选项、
  不存在的路径、打不开或编码错误的词表文件一律 stderr 报错并 exit 2，不静默通过。
- 自动跳过 tmp/、__pycache__/、.git/、node_modules/，references/ 下的三份规范附件
  （terminology/controlled-chinese/code-comment，表内必然列禁用词，扫了必自伤）与
  脚本自身；Markdown 围栏代码块与行内代码不扫。显式传入的目录本身不做跳过匹配
  （显式优先），其内部子目录照常剪枝。
- --skip-path REGEX 追加项目专属的跳过目录（如 vendored 上游）：路径先归一化为
  「/」分隔再匹配，Windows 下正则同样用「/」写。支持 --skip-path=REGEX 等值写法。
- --terms FILE 叠加加载项目领域词表：UTF-8 文本，每行「词<TAB>规范表述<TAB>error|warn」，
  井号开头为注释；领域词与内置词冲突时以领域词为准（对应术语表优先级）。领域
  字面词先命中并屏蔽该处，构词模式不再重报——可用领域 warn 条目把内置 error 级
  构词族误报（如项目词撞上 xx门）在本项目降级。支持 --terms=FILE 等值写法。

已知局限：字符串字面量内的「#」「//」「/*」会按注释起点处理；Markdown 缩进代码块
与「~~~」围栏不识别。

按需运行的自查工具，不挂准入检查。唯一权威 = references/terminology.md。
"""

import os
import re
import sys

# 词 -> (规范表述, 级别)。error = 明确替换；warn = 视语境保留或替换。
# 与 references/terminology.md §二/§三/§四保持一致；改词表先改术语表并经用户决定。
TERM_TABLE = {
    "台账": ("记录表", "error"),
    "闭环": ("处理完成 / 跟踪到关闭", "error"),
    "铁律": ("强制规则", "error"),
    "兜底": ("回退（值/路径）；备用（方案）；检出/承接（安全网）", "error"),
    "收口": ("收尾 / 收敛", "error"),
    "跑通": ("验证通过 / 正常运行", "error"),
    "卡点": ("阻碍点 / 卡住的问题", "error"),
    "链路": ("调用链 / 数据链（写全称）", "error"),
    "赋能": ("提供 / 支持", "error"),
    "抓手": ("切入点 / 具体措施 / 手段", "error"),
    "打通": ("连接 / 集成 / 对接", "error"),
    "拉通": ("同步 / 达成一致", "error"),
    "颗粒度": ("粒度", "error"),
    "沉淀": ("整理 / 积累 / 保存", "error"),
    "落地": ("实现 / 实施 / 上线", "error"),
    "能力": ("功能 / 支持 / 接口（「具备 XX 能力」改「支持 XX」；指真实能力保留）", "warn"),
    "场景": ("使用场景 / 用例（确指专业语境可保留）", "warn"),
    "输出": ("提供 / 生成 / 提交（作动词时）", "warn"),
    "底层逻辑": ("原理 / 核心机制 / 基本规则", "error"),
    "心智负担": ("理解成本 / 记忆成本", "error"),
    "底座": ("基础平台 / 基础设施", "error"),
    "中台": ("共享服务 / 平台", "error"),
    "飞轮": ("正向循环 / 持续积累", "error"),
    "叙事": ("描述 / 说明", "error"),
    "张力": ("差异 / 矛盾", "error"),
    "长尾": ("少量低频（确指长尾分布时保留）", "warn"),
    "e2e": ("端到端（语境清晰的测试类型名可保留）", "warn"),
    "control arm": ("对照组", "error"),
    "median": ("中位数", "error"),
    "wall": ("墙钟时间", "error"),
    "bench": ("基准测试", "error"),
    "warmup": ("预热", "error"),
    "staging": ("暂存", "error"),
    "拍板": ("决定 / 批准", "error"),
    "踩坑": ("暴露问题 / 先行验证", "error"),
    "造轮子": ("重复实现", "error"),
    "对齐": ("与…保持一致；挂载/内存对齐保留", "warn"),
    "阻塞": ("blocking 作动词保留；作名词改阻塞问题", "warn"),
    "落盘": ("保留（写入磁盘的标准术语）", "warn"),
    "水位": ("进度线 / 上界 / 截至点（流处理 watermark 语境保留水位线）", "warn"),
    "门禁": ("准入检查；出入控制的意思保留", "warn"),
    "门控": ("启用条件 / 开关 / 前提（按语义；电路/ML 本义保留）", "warn"),
    "gate": ("检查点 / 验收 / 准入条件；文件名/路径保留", "warn"),
    "checkpoint": ("保留英文，首次注明含义", "warn"),
    "控制臂": ("对照组", "error"),
    "对照臂": ("对照组", "error"),
    "裁决": ("决定（法律/体育本义保留）", "warn"),
    "电池": ("测试集（battery of tests 直译残留；物理电池保留）", "warn"),
}

# 构词模式 -> (规范表述, 级别, 白名单)。门/闸/硬/面四个能产语素族：
# 新衍生词由模式自动拦截，无须逐词登记；唯一权威 = references/terminology.md §三。
# 白名单按包含关系豁免本义词；后缀族配 lookahead 防止误吞合法续字（如「受门控」的门控）。
# 量词与指示词+门（一门语言、这门课是量词/指示用法，非构词）由「门」前一字符的
# lookbehind 豁免——守卫必须贴在「门」上，放词首会被「是一门」这类贪心中途吞字绕过。
PATTERN_TABLE = [
    (re.compile(r"[一-鿿]{1,3}(?<![一两三四五六七八九十数几这那哪])门(?!控|限|禁|票|槛|诊|户|道|铃|牌|板|框|扇|卫|厅|面|口|帘)"),
     "xx门 → xx验收 / xx审查 / xx条件（按语义）", "error",
     ("部门", "专门", "热门", "大门", "入门", "出门", "开门", "关门", "冷门", "佛门", "嗓门", "窍门", "阀门", "闸门", "家门", "龙门")),
    (re.compile(r"(?<![一两三四五六七八九十数几这那哪])门[一-鿿]{1,2}"),
     "门xx → 验收xx / 审查xx（按语义）", "error",
     ("门禁", "门口", "门诊", "门槛", "门票", "门户", "门道", "门铃", "门牌", "门板", "门框", "门扇", "门卫", "门厅", "门面", "门帘", "门牙", "门生")
     # 「专门检测」类：门xx 模式的「门」落在 xx门 白名单词内部，按区间相交豁免。
     + ("部门", "专门", "热门", "大门", "入门", "出门", "开门", "关门", "冷门", "佛门", "嗓门", "窍门", "阀门", "闸门", "家门", "龙门")),
    (re.compile(r"[一-鿿]{1,3}闸(?!门|阀|刀|口)"),
     "xx闸 → xx检查 / xx审查；表拦停条件 → 前置条件 / 准入条件", "error",
     ("闸门", "闸阀", "闸刀", "闸口")),
    (re.compile(r"闸[一-鿿]{1,2}"),
     "闸xx → 检查xx / 审查xx", "error",
     ("闸门", "闸阀", "闸刀", "闸口")),
    (re.compile(r"硬[一-鿿]{1,2}"),
     "硬xx → 强制xx / 固定xx / 硬性xx（按语义）", "error",
     ("硬件", "硬性", "硬盘", "硬伤", "硬编码", "硬链接", "硬实时", "硬拷贝", "硬币", "硬度", "硬化", "硬座", "硬卧", "硬水")),
    (re.compile(r"[一-鿿]{1,3}面(?!临|向|积|板|孔|子|目|包|条|粉|试|前|对|霜|脂|码|议|具|皮|筋|巾|汤|饼)"),
     "xx面 → 作分类标题删后缀；确指层面改 方面/环节/部分/范围（按语义）", "warn",
     ("方面", "书面", "全面", "表面", "层面", "局面", "页面", "面积", "面向", "面临", "面子", "面孔", "面目", "上面", "下面", "前面", "后面", "里面", "外面", "对面", "侧面", "场面", "地面", "桌面", "画面", "封面", "版面", "正面", "负面", "两面", "平面", "截面", "剖面", "断面", "水面", "门面", "纸面", "照面", "市面", "体面", "颜面", "脸面", "界面")),
]

SKIP_PATH = re.compile(r"(^|/)(tmp|__pycache__|\.git|node_modules)(/|$)")
SKIP_TERM_DOCS = re.compile(r"references/(terminology|controlled-chinese|code-comment)(-[^/]*)?\.md$")
SKIP_SELF = re.compile(r"scripts/lint_terms\.py$")

INLINE_CODE = re.compile(r"`[^`]*`")


def load_terms_file(path):
    """加载项目领域词表：UTF-8，每行「词<TAB>规范表述<TAB>error|warn」。"""
    extra = {}
    with open(path, encoding="utf-8") as fh:
        for raw in fh:
            line = raw.rstrip("\n")
            if not line or line.startswith("#"):
                continue
            parts = line.split("\t")
            if len(parts) < 2:
                continue
            word, suggestion = parts[0], parts[1]
            level = parts[2].strip() if len(parts) >= 3 else "error"
            if level not in ("error", "warn"):
                level = "error"
            extra[word] = (suggestion, level)
    return extra


def is_markdown(path):
    return path.endswith((".md", ".markdown"))


def is_source(path):
    return path.endswith((".py", ".sh", ".c", ".cu", ".cpp", ".h", ".hpp",
                          ".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs",
                          ".yaml", ".yml", ".toml"))


def scan_line(path, lineno, text, term_table):
    """返回该行的违规元组列表 (path, lineno, word, suggestion, level)。"""
    hits = []
    if is_markdown(path):
        text = INLINE_CODE.sub("", text)
    # 「验收口径」中的「收口」是子串误报，先屏蔽。
    text = text.replace("口径", "　")
    # bench 作为脚本名/数据集名的一部分（bench_*、foo-bench、bench.py）不按正文算。
    text = re.sub(r"bench[-_.]", "　", text)
    text = re.sub(r"[-_/.]bench\b", "　", text)
    work = text
    for word, (suggestion, level) in sorted(term_table.items(), key=lambda kv: len(kv[0]), reverse=True):
        if word.isascii():
            matched = re.search(rf"\b{re.escape(word)}\b", work)
        else:
            matched = word in work
        if matched:
            hits.append((path, lineno, word, suggestion, level))
            # 字面词命中处屏蔽，防止构词模式在同一处重复报。
            if word.isascii():
                work = re.sub(rf"\b{re.escape(word)}\b", "　" * len(word), work)
            else:
                work = work.replace(word, "　" * len(word))
    spans = []
    for pattern, suggestion, level, whitelist in PATTERN_TABLE:
        # 白名单按行内出现区间豁免：匹配区间与白名单词出现区间相交即跳过，
        # 覆盖「专门检测」这类白名单词与后续字组合被后缀族误吞的情况。
        wl_spans = []
        for w in whitelist:
            pos = work.find(w)
            while pos >= 0:
                wl_spans.append((pos, pos + len(w)))
                pos = work.find(w, pos + 1)
        for m in pattern.finditer(work):
            token = m.group(0)
            if any(w in token for w in whitelist):
                continue
            if any(s < m.end() and m.start() < e for s, e in wl_spans):
                continue
            if any(s < m.end() and m.start() < e for s, e in spans):
                continue
            spans.append((m.start(), m.end()))
            hits.append((path, lineno, token, suggestion, level))
    return hits


def scan_markdown(path, fh, term_table):
    hits = []
    in_fence = False
    for lineno, raw in enumerate(fh, 1):
        line = raw.rstrip("\n")
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        hits.extend(scan_line(path, lineno, line, term_table))
    return hits


def scan_source(path, fh, term_table):
    """仅扫描注释与 docstring，跳过代码本体。"""
    hits = []
    text = fh.read()
    if path.endswith((".sh", ".yaml", ".yml")):
        for lineno, line in enumerate(text.splitlines(), 1):
            stripped = line.strip()
            if stripped.startswith("#"):
                hits.extend(scan_line(path, lineno, stripped[1:], term_table))
        return hits
    if path.endswith(".toml"):
        # TOML 内容几乎全是值（提示词/配置文本），逐行全扫，仅跳过纯注释行。
        for lineno, line in enumerate(text.splitlines(), 1):
            if line.strip().startswith("#"):
                continue
            hits.extend(scan_line(path, lineno, line, term_table))
        return hits
    # Python：docstring 与 # 行注释（含行内注释）。
    if path.endswith(".py"):
        in_doc = False
        for lineno, line in enumerate(text.splitlines(), 1):
            if '"""' in line:
                # 单行 docstring（一行两个 """）不应翻转状态；只有成单的边界才翻转。
                if line.count('"""') % 2 == 1:
                    in_doc = not in_doc
                hits.extend(scan_line(path, lineno, line.replace('"""', ""), term_table))
                continue
            if in_doc:
                hits.extend(scan_line(path, lineno, line, term_table))
                continue
            if "#" in line:
                code, _, comment = line.partition("#")
                if comment and not _is_url_or_codepoint(code, comment):
                    hits.extend(scan_line(path, lineno, comment, term_table))
        return hits
    # C 系（含 JS/TS）：逐行提取注释文本——// 行注释与块注释内容（含 JSDoc）都扫，
    # 代码本体跳过；块注释跨行由 in_block 跟踪，不删文本，行号天然不漂移。
    in_block = False
    for lineno, line in enumerate(text.splitlines(), 1):
        rest = line
        parts = []
        while rest:
            if in_block:
                end = rest.find("*/")
                if end < 0:
                    parts.append(rest)
                    rest = ""
                else:
                    parts.append(rest[:end])
                    rest = rest[end + 2:]
                    in_block = False
                continue
            bstart = rest.find("/*")
            lstart = rest.find("//")
            if lstart >= 0 and (bstart < 0 or lstart < bstart):
                parts.append(rest[lstart + 2:])
                break
            if bstart >= 0:
                end = rest.find("*/", bstart + 2)
                if end < 0:
                    parts.append(rest[bstart + 2:])
                    rest = ""
                    in_block = True
                else:
                    parts.append(rest[bstart + 2:end])
                    rest = rest[end + 2:]
                continue
            break
        for part in parts:
            # JSDoc 续行的 * 前缀剥掉再扫。
            part = part.lstrip("* ").strip()
            if part:
                hits.extend(scan_line(path, lineno, part, term_table))
    return hits


def _is_url_or_codepoint(code, comment):
    """行内 '#' 若属 URL 或颜色值/十六进制字面量，跳过。"""
    if re.search(r"https?://[^ ]*#", code + comment):
        return True
    if re.search(r"0x[0-9a-fA-F]+#", code):
        return True
    return False


def main(argv):
    strict = False
    terms_files = []
    skip_regexes = []
    paths = []
    i = 0
    while i < len(argv):
        arg = argv[i]
        if arg == "--strict":
            strict = True
            i += 1
            continue
        opt, eq, inline = arg.partition("=")
        if opt in ("--terms", "--skip-path"):
            if eq:
                value = inline
                i += 1
            elif i + 1 < len(argv) and not argv[i + 1].startswith("--"):
                value = argv[i + 1]
                i += 2
            else:
                print(f"lint_terms: {opt} 缺少参数值", file=sys.stderr)
                return 2
            if opt == "--terms":
                terms_files.append(value)
            else:
                try:
                    skip_regexes.append(re.compile(value))
                except re.error as exc:
                    print(f"lint_terms: --skip-path 正则无效 {value!r}: {exc}", file=sys.stderr)
                    return 2
            continue
        if arg.startswith("--"):
            print(f"lint_terms: 未知选项 {arg!r}（仅支持 --strict/--terms/--skip-path）", file=sys.stderr)
            return 2
        paths.append(arg)
        i += 1
    if not paths:
        print(__doc__)
        return 2
    term_table = dict(TERM_TABLE)
    for tf in terms_files:
        try:
            term_table.update(load_terms_file(tf))
        except (OSError, UnicodeError) as exc:
            print(f"lint_terms: 领域词表读取失败 {tf}: {exc}", file=sys.stderr)
            return 2

    def skipped(p):
        # 统一为正斜杠，保证 Windows 反斜杠路径也能命中跳过规则。
        p = p.replace("\\", "/")
        if SKIP_PATH.search(p) or SKIP_TERM_DOCS.search(p) or SKIP_SELF.search(p):
            return True
        return any(rx.search(p) for rx in skip_regexes)

    errors = warnings = 0
    for root in paths:
        if not os.path.exists(root):
            print(f"lint_terms: 路径不存在 {root}", file=sys.stderr)
            return 2
        if os.path.isdir(root):
            files = []
            for dirpath, dirnames, filenames in os.walk(root):
                dirnames[:] = [d for d in dirnames if not skipped(dirpath + "/" + d + "/")]
                for name in filenames:
                    full = os.path.join(dirpath, name)
                    if is_markdown(full) or is_source(full):
                        files.append(full)
        else:
            if skipped(root):
                print(f"lint_terms: 显式路径命中跳过规则，未扫描 {root}", file=sys.stderr)
                continue
            files = [root]
        for path in sorted(files):
            if skipped(path):
                continue
            with open(path, encoding="utf-8", errors="replace") as fh:
                if is_markdown(path):
                    hits = scan_markdown(path, fh, term_table)
                else:
                    hits = scan_source(path, fh, term_table)
            for path, lineno, word, suggestion, level in hits:
                print(f"{path}:{lineno}: {word} → {suggestion} [{level}]")
                if level == "error":
                    errors += 1
                else:
                    warnings += 1
    print(f"\n{errors} error(s), {warnings} warning(s)")
    if errors > 0 or (strict and warnings > 0):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))