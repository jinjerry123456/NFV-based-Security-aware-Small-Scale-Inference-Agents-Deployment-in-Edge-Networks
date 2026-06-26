import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
import os
import glob
from datetime import datetime

# 1. 创建输出目录
output_dir = os.path.join("results", "visualization")
if not os.path.exists(output_dir):
    os.makedirs(output_dir)

def find_latest_file(pattern):
    """ 在 results 文件夹下搜索包含关键字的文件 """
    files = glob.glob(os.path.join("results", f"*{pattern}*"))
    return files[0] if files else None

def plot_beautified_results(file_path, x_col_name, output_filename, title_suffix):
    """
    基于用户提供的样式片段，生成高度美化的学术分组柱状图。
    """
    if not file_path or not os.path.exists(file_path):
        print(f"找不到文件: {file_path}")
        return

    # 读取数据 (支持 .xlsx 和 .csv)
    try:
        if file_path.endswith('.xlsx'):
            df_raw = pd.read_excel(file_path)
        else:
            df_raw = pd.read_csv(file_path)
    except Exception as e:
        print(f"读取文件错误 {file_path}: {e}")
        return
    
    # 学术字体设置
    plt.rcParams['font.family'] = ['Times New Roman', 'DejaVu Sans']
    plt.rcParams['font.size'] = 11
    plt.rcParams['axes.linewidth'] = 1.0
    plt.rcParams['axes.spines.top'] = False
    plt.rcParams['axes.spines.right'] = False
    
    # 算法及其专属样式 (4种算法)
    algos = ['My Algorithm', 'Cost-first', 'Price-first', 'Security-first']
    colors = ['#8b9bb4', '#d8aa82', '#96ad90', '#c19797'] # 莫兰迪学术色
    hatches = ['///', '...', '\\\\\\', 'xxx']
    edge_colors = ['#2C3E50', '#7B3F00', '#2E4B2E', '#4B2E2E']
    # 趋势线使用更浅的颜色，便于区分不同算法的趋势
    trend_colors = ['#6B7A94', '#B8956F', '#7A8D73', '#9D7A7A']  # 浅色版本
    trend_styles = [':', '--', '-.', '-']
    # 误差条使用浅色
    error_colors = ['#B0C0D0', '#E0C5A8', '#B8C5B8', '#D0B0B0']  # 浅色误差条

    # 根据文件名决定绘制的指标
    if "acceptance" in file_path.lower():
        metrics_map = {'接受率': 'Acceptance Rate'}
        fig_size = (9, 7)  # 单个子图
        rows = 1
    else:
        metrics_map = {
            '总体成本 ($)': 'Resource Cost ($)',
            '平均安全级别': 'Security Level',
            '运行时间 (s)': 'Runtime (s)'
        }
        fig_size = (24, 7)  # 三个子图
        rows = 3
    
    # 准备 X 轴
    df_metrics = df_raw[df_raw['指标/统计'].notna()].copy()
    df_metrics[x_col_name] = pd.to_numeric(df_metrics[x_col_name], errors='coerce')
    df_metrics = df_metrics.dropna(subset=[x_col_name])
    x_labels = sorted(df_metrics[x_col_name].unique())
    x_positions = np.arange(len(x_labels))
    width = 0.18  # 柱子宽度
    
    # X 轴翻译
    x_trans = {'安全需求': 'Security Req (θ)', '客户端数': 'Num of Clients', 
                'NF个数': 'Num of NFs', '度数': 'Network Degree'}
    eng_x_label = x_trans.get(x_col_name, x_col_name)

    # 创建子图
    if rows == 1:
        fig, axes = plt.subplots(1, 1, figsize=fig_size)
        axes = [axes]  # 转换为列表以便统一处理
    else:
        fig, axes = plt.subplots(1, 3, figsize=fig_size)
    
    for i, (metric_prefix, ylabel) in enumerate(metrics_map.items()):
        ax = axes[i]
        for j, algo in enumerate(algos):
            means, mins, maxs = [], [], []
            for x in x_labels:
                subset = df_metrics[df_metrics[x_col_name] == x]
                # 提取平均值、最小值、最大值
                avg_r = subset[subset['指标/统计'].str.contains(f"{metric_prefix}-平均值", regex=False)]
                min_r = subset[subset['指标/统计'].str.contains(f"{metric_prefix}-最小值", regex=False)]
                max_r = subset[subset['指标/统计'].str.contains(f"{metric_prefix}-最大值", regex=False)]
                
                if not avg_r.empty:
                    means.append(avg_r[algo].values[0])
                    mins.append(min_r[algo].values[0])
                    maxs.append(max_r[algo].values[0])
            
            if not means: continue
            
            # 计算柱子位置并绘图（添加误差条）
            pos = x_positions + (j - 1.5) * width
            yerr = [np.array(means) - np.array(mins), np.array(maxs) - np.array(means)]
            
            ax.bar(pos, means, width, label=algo, 
                   color=colors[j], alpha=0.6, edgecolor=edge_colors[j], 
                   linewidth=1.5, hatch=hatches[j],
                   yerr=yerr, capsize=4, ecolor=error_colors[j], 
                   error_kw={'elinewidth': 2, 'alpha': 0.7})
            
            # 添加趋势线（使用浅色，便于区分不同算法的趋势）
            if len(x_labels) > 1:
                trend = np.polyfit(x_positions, means, 1)
                ax.plot(pos, np.polyval(trend, x_positions), 
                        trend_styles[j], color=trend_colors[j], linewidth=2.5, alpha=0.8)

        # 细节优化
        ax.set_xlabel(eng_x_label, fontsize=16, fontweight='bold')
        ax.set_ylabel(ylabel, fontsize=16, fontweight='bold')
        ax.set_xticks(x_positions)
        ax.set_xticklabels(x_labels, fontsize=14)
        ax.grid(True, alpha=0.3, linestyle='--', axis='y')
        ax.set_facecolor('#f8f9fa')
        
        # 调整Y轴范围：坐标上移，避免误差条太长导致bar看不见
        y_min, y_max = ax.get_ylim()
        # 如果最小值接近0，从0开始；否则留出一些底部空间
        if y_min >= 0:
            y_bottom = 0
        else:
            y_range = y_max - y_min
            y_bottom = y_min - y_range * 0.05
        
        # 针对不同指标调整顶部空间
        y_range = y_max - y_bottom
        # Resource Cost 和 Runtime 减少顶部空间，让bar更明显
        if ylabel == 'Resource Cost ($)' or ylabel == 'Runtime (s)':
            ax.set_ylim(bottom=y_bottom, top=y_bottom + y_range * 1.15)
        else:
            # 其他指标保持原有空间
            ax.set_ylim(bottom=y_bottom, top=y_bottom + y_range * 1.4)
        
        ax.legend(loc='upper left', frameon=True, shadow=True, ncol=2, prop={'size': 14}, framealpha=0.9)

    plt.tight_layout(pad=3.0)
    fig.suptitle(f'Comprehensive Analysis: {title_suffix}', fontsize=22, fontweight='bold', y=1.05)
    
    # 在文件名后添加时间戳
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    name, ext = os.path.splitext(output_filename)
    output_filename_with_timestamp = f"{name}_{timestamp}{ext}"
    save_path = os.path.join(output_dir, output_filename_with_timestamp)
    plt.savefig(save_path, dpi=300, bbox_inches='tight')
    plt.close()
    print(f"已生成美化图表: {save_path}")

# --- 执行所有任务 ---
if __name__ == "__main__":
    # 任务列表: (文件关键字, X轴原始列名, 输出图片名, 标题后缀)
    tasks = [
        ('security', '安全需求', 'security.png', 'Impact of Security Requirement'),
        ('client_count', '客户端数', 'clients.png', 'Impact of Client Number'),
        ('node_num', 'NF个数', 'nodes.png', 'Impact of Network Nodes'),
        ('degree', '度数', 'degree.png', 'Impact of Network Degree'),
        ('nf_instances', 'NF个数', 'instances.png', 'Impact of NF Instances'),
        ('client_acceptance', '客户端数', 'acceptance.png', 'Acceptance Rate')
    ]

    print(">>> 启动自动化可视化脚本...")
    if not os.path.exists("results"):
        print("错误: 找不到 'results' 文件夹，请确保脚本在正确的位置运行。")
    else:
        for pattern, x, out, title in tasks:
            file_path = find_latest_file(pattern)
            if file_path:
                plot_beautified_results(file_path, x, out, title)
            else:
                print(f"未找到匹配 '{pattern}' 的文件")
    print(">>> 任务完成！")