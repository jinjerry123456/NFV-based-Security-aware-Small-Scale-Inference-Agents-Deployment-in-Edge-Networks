# -*- coding: utf-8 -*-
"""
Overall implementation cost vs # of SeR / degree / node / client / instance
五张堆叠柱状图：bar高度=总体成本平均值，下段=CPU cost，上段=总体带宽成本，标注min/max
配色模仿 visualization2.1.py
"""

import os
import re
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
from matplotlib.ticker import MaxNLocator
from matplotlib.lines import Line2D

# 数据列名（与 Excel 列一致），显示名用于图中图例与标签
ALGOS = ['My Algorithm', 'Cost-first', 'Price-first', 'Security-first']
ALGO_DISPLAY = {
    'My Algorithm': 'CS-ND',
    'Cost-first': 'CP-ND',
    'Price-first': 'PP-ND',
    'Security-first': 'SP-ND',
}
# 莫兰迪学术色（与 visualization2.1.py 一致）
COLORS = ['#8b9bb4', '#d8aa82', '#96ad90', '#c19797']


def _lighten_color(hex_color, amount=0.45):
    """将十六进制颜色变浅，与最大值同色系便于区分 min/max。amount 为混入白色的比例。"""
    c = mcolors.to_rgb(hex_color)
    r, g, b = (1 - amount) * np.array(c) + amount * np.array((1, 1, 1))
    return mcolors.to_hex((r, g, b))


RESULTS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "results", "120_4_20260215_135806")


def clean_level(x):
    if pd.isna(x):
        return np.nan
    if isinstance(x, str):
        m = re.search(r'(\d+)', str(x))
        return int(m.group(1)) if m else np.nan
    try:
        return int(x)
    except (ValueError, TypeError):
        return np.nan


def _to_float(val):
    """将单元格值转为浮点数，支持 N/A 等"""
    if val is None or pd.isna(val) or val == 'N/A':
        return np.nan
    try:
        return float(val)
    except (ValueError, TypeError):
        return np.nan


def reconstruct_metric_table(df, level_col, metric, algos=ALGOS):
    df = df.copy()
    # 兼容可能的列名
    metric_col = '指标' if '指标' in df.columns else df.columns[1]
    stat_col = '统计' if '统计' in df.columns else df.columns[2]
    df[level_col] = df[level_col].apply(clean_level)
    rows = []
    for idx in df.index[df[metric_col] == metric].tolist():
        block = df.loc[idx:idx+2, [level_col, stat_col] + [c for c in algos if c in df.columns]]
        rows.append(block)
    if not rows:
        return None
    allb = pd.concat(rows, ignore_index=True)
    for c in algos:
        if c in allb.columns:
            allb[c] = allb[c].apply(_to_float)
    pivot = allb.pivot_table(index=[level_col, stat_col], values=[c for c in algos if c in allb.columns], aggfunc='first').sort_index()
    return pivot


def build_total_cost_components(total_table, bw_table):
    """tot_avg=总体成本平均值, bw_avg=总体带宽成本平均值, cpu_avg=CPU cost (tot-bw)"""
    tot_avg = total_table.xs('平均值', level=1)
    bw_avg = bw_table.xs('平均值', level=1)
    cpu_avg = tot_avg - bw_avg
    cpu_avg = cpu_avg.clip(lower=0)
    return cpu_avg, bw_avg, tot_avg


def _setup_english_fonts():
    """统一设置英文字体为加粗 Times New Roman，避免中文导致方框"""
    plt.rcParams['font.family'] = ['Times New Roman', 'DejaVu Sans', 'sans-serif']
    # 全局基础字号稍微调大一点
    plt.rcParams['font.size'] = 13
    plt.rcParams['font.weight'] = 'bold'
    plt.rcParams['axes.labelweight'] = 'bold'
    plt.rcParams['axes.unicode_minus'] = False


def plot_stacked_with_minmax(levels, cpu_df, bw_df, total_avg_df, total_min_df, total_max_df, xlabel, outfile):
    alg_order = ALGOS
    n_levels = len(levels)
    n_alg = len(alg_order)
    group_width = 0.8
    bar_width = group_width / n_alg
    x = np.arange(n_levels)

    fig, ax = plt.subplots(figsize=(8, 5.6), dpi=200)
    _setup_english_fonts()
    plt.rcParams['axes.linewidth'] = 1.0
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)

    for i, alg in enumerate(alg_order):
        if alg not in cpu_df.columns:
            continue
        xpos = x - group_width / 2 + (i + 0.5) * bar_width

        cpu_vals = cpu_df.loc[levels, alg].values
        bw_vals = bw_df.loc[levels, alg].values
        cpu_vals = np.nan_to_num(cpu_vals, nan=0.0)
        bw_vals = np.nan_to_num(bw_vals, nan=0.0)

        disp = ALGO_DISPLAY.get(alg, alg)
        ax.bar(xpos, cpu_vals, width=bar_width, bottom=0, color=COLORS[i], alpha=0.95, edgecolor='white', linewidth=0.3, label=f"{disp}-Com")
        ax.bar(xpos, bw_vals, width=bar_width, bottom=cpu_vals, color=COLORS[i], alpha=0.65, hatch='///', edgecolor='white', linewidth=0.3, label=f"{disp}-Rout")

        avg_vals = total_avg_df.loc[levels, alg].values
        avg_vals = np.nan_to_num(avg_vals, nan=0.0)
        ymin = total_min_df.loc[levels, alg].values
        ymax = total_max_df.loc[levels, alg].values
        ymin = np.nan_to_num(ymin, nan=0.0)
        ymax = np.nan_to_num(ymax, nan=0.0)

        # error bar 长度限制：最多延伸 bar 高度的 20%，使主体更突出
        err_frac = 0.2
        err_below = np.minimum(avg_vals - ymin, np.maximum(avg_vals * err_frac, 0.01))
        err_above = np.minimum(ymax - avg_vals, np.maximum(avg_vals * err_frac, 0.01))
        err_bottom = avg_vals - err_below
        err_top = avg_vals + err_above

        c = COLORS[i]
        light_c = _lighten_color(c)
        ax.vlines(xpos, err_bottom, err_top, linewidth=1.2, colors=c, alpha=0.85)
        # 最小值：圆点、同色系浅色填充；最大值：圆点、同色系深色实心
        edge_col = '#555555'
        ax.scatter(
            xpos, err_bottom, s=30, marker='o',
            facecolors=light_c, edgecolors=edge_col,
            linewidths=0.8, zorder=3
        )
        ax.scatter(
            xpos, err_top, s=30, marker='o',
            facecolors=c, edgecolors=edge_col,
            linewidths=0.8, zorder=3
        )

    # 图例：模仿原本 Com / Rout 形式（去重，每个算法只显示一次 Com/Rout），并为图例预留上方空间
    handles, labels = ax.get_legend_handles_labels()
    seen = set()
    unique = []
    for h, l in zip(handles, labels):
        if l not in seen:
            seen.add(l)
            unique.append((h, l))

    # 为每个算法在图例中标注 min / max 点的样式：Alg-min（同色系浅色圆点）/ Alg-max（同色系深色实心圆点）
    for i, alg in enumerate(alg_order):
        c = COLORS[i]
        light_c = _lighten_color(c)
        min_proxy = Line2D(
            [0], [0], marker='o', linestyle='None',
            markerfacecolor=light_c, markeredgecolor='#555555',
            markeredgewidth=0.8, markersize=6
        )
        max_proxy = Line2D(
            [0], [0], marker='o', linestyle='None',
            markerfacecolor=c, markeredgecolor='#555555',
            markeredgewidth=0.8, markersize=6
        )
        disp = ALGO_DISPLAY.get(alg, alg)
        unique.append((min_proxy, f"{disp}-min"))
        unique.append((max_proxy, f"{disp}-max"))

    # 先调整 y 轴上限，为左上角图例腾出空间
    y_min, y_max = ax.get_ylim()
    y_range = y_max - y_min if y_max > y_min else 1.0
    ax.set_ylim(y_min, y_max + 0.35 * y_range)

    # fig_overall_cost 图例字号调小
    ax.legend(*zip(*unique), ncol=3, fontsize=11, frameon=False, loc='upper left')

    ax.set_xticks(x)
    ax.set_xticklabels(levels, fontsize=20)
    ax.set_xlabel(xlabel, fontsize=22, fontweight='bold')
    ax.set_ylabel("Overall Implementation Cost", fontsize=22, fontweight='bold')
    ax.tick_params(axis='both', labelsize=20)
    ax.grid(axis='y', alpha=0.3)

    # 强制坐标轴与图例文字使用 Times New Roman，避免个别图回退为系统默认字体
    for item in ([ax.title, ax.xaxis.label, ax.yaxis.label] +
                 ax.get_xticklabels() + ax.get_yticklabels()):
        item.set_fontname("Times New Roman")
    legend = ax.get_legend()
    if legend is not None:
        for text in legend.get_texts():
            text.set_fontname("Times New Roman")

    fig.tight_layout()
    fig.savefig(outfile, bbox_inches='tight')
    plt.close(fig)
    print(f"Saved: {outfile}")


def _safe_filename(s):
    """将指标名转为安全的文件名"""
    return re.sub(r'[\/\\:*?"<>$]', '_', s).replace(' ', '_')


def plot_line_metric(df, level_col, metric, xlabel, ylabel_en, outfile):
    """绘制单个指标的折线图（纵坐标为平均值），ylabel_en 为英文标签"""
    tab = reconstruct_metric_table(df, level_col, metric)
    if tab is None:
        print(f"  Skip (no data): {metric}")
        return
    tab_avg = tab.xs('平均值', level=1)
    levels = tab_avg.index.tolist()
    levels = sorted([x for x in levels if not (isinstance(x, float) and np.isnan(x))])

    fig, ax = plt.subplots(figsize=(8, 5.6), dpi=200)
    _setup_english_fonts()
    plt.rcParams['axes.linewidth'] = 1.0
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)

    linestyles = ['-', '--', '-.', ':']
    markers = ['o', 's', '^', 'D']
    for i, alg in enumerate(ALGOS):
        if alg not in tab_avg.columns:
            continue
        vals = np.array(tab_avg.loc[levels, alg].values, dtype=float)
        if np.all(np.isnan(vals)):
            continue
        disp = ALGO_DISPLAY.get(alg, alg)
        ax.plot(
            levels, vals,
            color=COLORS[i], linestyle=linestyles[i], marker=markers[i],
            linewidth=3, markersize=10, label=disp,
            markerfacecolor=COLORS[i], markeredgecolor='white', markeredgewidth=0.8
        )

    # 为图例预留更多上方空间
    y_min, y_max = ax.get_ylim()
    y_range = y_max - y_min if y_max > y_min else 1.0
    ax.set_ylim(y_min, y_max + 0.25 * y_range)

    ax.set_xlabel(xlabel, fontsize=22, fontweight='bold')
    ax.set_ylabel(ylabel_en, fontsize=22, fontweight='bold')
    ax.set_xticks(levels)
    ax.set_xticklabels(levels, fontsize=20)
    ax.tick_params(axis='both', labelsize=20)
    ax.grid(alpha=0.3)
    # 除 fig_overall_cost 之外，其它图的图例字号再大一点
    ax.legend(loc='upper left', ncol=2, fontsize=19, frameon=False)

    # 强制坐标轴与图例文字使用 Times New Roman
    for item in ([ax.title, ax.xaxis.label, ax.yaxis.label] +
                 ax.get_xticklabels() + ax.get_yticklabels()):
        item.set_fontname("Times New Roman")
    legend = ax.get_legend()
    if legend is not None:
        for text in legend.get_texts():
            text.set_fontname("Times New Roman")

    fig.tight_layout()
    fig.savefig(outfile, bbox_inches='tight')
    plt.close(fig)
    print(f"Saved: {outfile}")


# 13 个需要折线图展示的指标（中文名 -> 英文 y 轴标签，用于 CCFA 论文）
LINE_METRICS = [
    ("Client到Node平均跳数", "Avg Client-to-Node Hops"),
    ("总体成本/安全级别", "Overall Cost per Security Level"),
    ("平均安全级别", "Avg Security Level"),
    ("单节点平均成本 ($)", "Avg Cost per Node"),
    ("平均带宽成本 ($)", "Avg Bandwidth Cost"),
    ("平均安全补足开销 ($)", "Avg Security Augmentation Cost"),
    ("Node平均部署NF个数(补足)", "Avg Augmented NF per Node"),
    ("补足SecurityLevel/补足Cost", "Security Level per Aug Cost"),
    ("补足NF个数/补足Cost", "NF Count per Aug Cost"),
    ("Node平均扩容GPU unit", "Avg Augmentation GPU per Node"),
    ("Node个数/扩容开销", "Nodes per Augmentation Cost"),
    ("使用的节点数", "Number of Nodes Used"),
    ("Node平均Client覆盖率", "Avg Clients per Node"),
]


def export_execution_time_table(df, level_col, level_name_en, dim_dir):
    """导出算法执行时间 (s) 平均值为 CSV 和学术风格表格图（英文，用于论文）。

    目标格式：
    - 表头第一行：Level（如 SeR/Node/... 的不同取值）
    - 第一列：Algorithm（算法名）
    - 单元格：对应 Level 下的平均运行时间（秒）
    """
    EXEC_METRIC = "算法执行时间 (s)"
    tab = reconstruct_metric_table(df, level_col, EXEC_METRIC)
    if tab is None:
        print(f"  Skip execution time (no data): {EXEC_METRIC}")
        return

    # 只取平均值：index=level，columns=algorithms
    tab_avg = tab.xs("平均值", level=1)
    levels = tab_avg.index.tolist()
    levels = sorted([x for x in levels if not (isinstance(x, float) and np.isnan(x))])

    # 形成论文友好的宽表：行=算法显示名，列=levels
    algo_cols = [a for a in ALGOS if a in tab_avg.columns]
    wide = tab_avg.loc[levels, algo_cols].T
    wide.index = [ALGO_DISPLAY.get(a, a) for a in wide.index]
    wide.columns = levels

    # CSV（便于后续放到 LaTeX / Excel）
    csv_path = os.path.join(dim_dir, "execution_time_avg.csv")
    wide.to_csv(csv_path, index_label="Algorithm", float_format="%.4f")
    print(f"Saved: {csv_path}")

    # 表格图 PNG（学术风格）
    _setup_english_fonts()
    n_rows, n_cols = wide.shape
    # 动态尺寸：列多时横向拉伸；行固定为4个算法
    fig_w = max(8.5, 1.15 * (n_cols + 1))
    fig_h = max(2.6, 0.55 * (n_rows + 1))
    fig, ax = plt.subplots(figsize=(fig_w, fig_h), dpi=200)
    ax.axis("off")

    col_labels = [level_name_en] + [str(c) for c in wide.columns.tolist()]
    cell_text = []
    for alg_name, row in wide.iterrows():
        vals = [("" if pd.isna(v) else f"{float(v):.4f}") for v in row.values.tolist()]
        cell_text.append([alg_name] + vals)

    table = ax.table(
        cellText=cell_text,
        colLabels=col_labels,
        loc="center",
        cellLoc="center",
        colLoc="center",
    )
    table.auto_set_font_size(False)
    table.set_fontsize(13)

    # 论文风格：更干净的线条与斑马纹
    header_bg = "#F2F2F2"
    zebra_bg = ("#FFFFFF", "#FAFAFA")
    edge = "#333333"

    for (r, c), cell in table.get_celld().items():
        cell.set_edgecolor(edge)
        cell.set_linewidth(0.6)
        if r == 0:  # header
            cell.set_facecolor(header_bg)
            cell.set_text_props(weight="bold")
            cell.set_linewidth(0.9)
        else:
            cell.set_facecolor(zebra_bg[(r - 1) % 2])
            if c == 0:  # algorithm column
                cell.set_text_props(weight="bold")

    # 适当放大单元格，避免拥挤
    table.scale(1.15, 1.55)

    # 标题（英文，论文友好）
    ax.set_title("Average Execution Time (s)", fontsize=16, fontweight="bold", pad=10)
    fig.tight_layout()
    png_path = os.path.join(dim_dir, "execution_time_avg.png")
    fig.savefig(png_path, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved: {png_path}")


def plot_one_dimension(data_dir, filename, level_col, xlabel, outfile):
    """绘制单个维度的 overall cost 堆叠柱状图"""
    path = os.path.join(data_dir, filename)
    if not os.path.exists(path):
        print(f"跳过（文件不存在）: {path}")
        return
    df = pd.read_excel(path)

    total_table = reconstruct_metric_table(df, level_col, '总体成本 ($)')
    bw_table = reconstruct_metric_table(df, level_col, '总体带宽成本 ($)')
    if total_table is None or bw_table is None:
        print(f"跳过（缺少总体成本或总体带宽成本）: {path}")
        return

    levels = total_table.index.get_level_values(0).unique().tolist()
    levels = sorted([x for x in levels if not (isinstance(x, float) and np.isnan(x))])

    cpu_df, bw_df, tot_df = build_total_cost_components(total_table, bw_table)
    total_min_df = total_table.xs('最小值', level=1)
    total_max_df = total_table.xs('最大值', level=1)

    plot_stacked_with_minmax(
        levels=levels,
        cpu_df=cpu_df,
        bw_df=bw_df,
        total_avg_df=tot_df,
        total_min_df=total_min_df,
        total_max_df=total_max_df,
        xlabel=xlabel,
        outfile=outfile
    )


if __name__ == "__main__":
    os.makedirs(RESULTS_DIR, exist_ok=True)

    # 每个自变量对应一个子文件夹：(Excel文件名, 维度列, xlabel, 子文件夹名, 表格中维度列英文名)
    configs = [
        ("按安全需求.xlsx", "安全需求", "# of SeR", "ser", "SeR"),
        ("按度数.xlsx", "度数", "# of degree", "degree", "Degree"),
        ("按节点数量.xlsx", "节点数量", "# of node", "node", "Node"),
        ("按客户端数量.xlsx", "客户端数", "# of client", "client", "Client"),
        ("按NF个数.xlsx", "NF个数", "# of instance", "instance", "Instance"),
    ]

    for filename, level_col, xlabel, subfolder, level_name_en in configs:
        dim_dir = os.path.join(RESULTS_DIR, subfolder)
        os.makedirs(dim_dir, exist_ok=True)
        outpath = os.path.join(dim_dir, "fig_overall_cost.png")
        plot_one_dimension(RESULTS_DIR, filename, level_col, xlabel, outpath)

    # 折线图 + 算法执行时间表格：每个 Excel 放入对应自变量文件夹
    for filename, level_col, xlabel, subfolder, level_name_en in configs:
        path = os.path.join(RESULTS_DIR, filename)
        if not os.path.exists(path):
            continue
        dim_dir = os.path.join(RESULTS_DIR, subfolder)
        os.makedirs(dim_dir, exist_ok=True)
        df = pd.read_excel(path)
        for metric_cn, ylabel_en in LINE_METRICS:
            safe_name = _safe_filename(metric_cn)
            outname = f"line_{safe_name}.png"
            outpath = os.path.join(dim_dir, outname)
            plot_line_metric(df, level_col, metric_cn, xlabel, ylabel_en, outpath)
        export_execution_time_table(df, level_col, level_name_en, dim_dir)

    print("Done.")
