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
    基于用户提供的样式片段，生成高度美化的学术折线图。
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
    markers = ['o', 's', '^', 'D']  # 不同标记样式
    linestyles = ['-', '--', '-.', ':']  # 不同线型
    linewidths = [2.5, 2.5, 2.5, 2.5]  # 线宽
    markersizes = [9, 9, 9, 9]  # 标记大小

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
    x_values = np.array(x_labels)  # 使用实际数值而不是位置
    
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
            means = []
            x_plot = []
            for x in x_labels:
                subset = df_metrics[df_metrics[x_col_name] == x]
                # 只提取平均值
                avg_r = subset[subset['指标/统计'].str.contains(f"{metric_prefix}-平均值", regex=False)]
                
                if not avg_r.empty:
                    means.append(avg_r[algo].values[0])
                    x_plot.append(x)
            
            if not means: continue
            
            # 绘制折线图
            ax.plot(x_plot, means, 
                   label=algo, 
                   color=colors[j], 
                   linestyle=linestyles[j],
                   linewidth=linewidths[j],
                   marker=markers[j],
                   markersize=markersizes[j],
                   markerfacecolor=colors[j],
                   markeredgecolor='white',
                   markeredgewidth=1.5,
                   alpha=0.9)

        # 细节优化
        ax.set_xlabel(eng_x_label, fontsize=16, fontweight='bold')
        ax.set_ylabel(ylabel, fontsize=16, fontweight='bold')
        ax.set_xticks(x_labels)
        ax.set_xticklabels(x_labels, fontsize=14)
        ax.grid(True, alpha=0.3, linestyle='--', axis='both')
        ax.set_facecolor('#f8f9fa')
        
        # 设置Y轴范围
        y_min, y_max = ax.get_ylim()
        # 对于 Security Level 和 Resource Cost，如果数据都在上方，调整Y轴范围让线条下移
        if ylabel == 'Security Level' or ylabel == 'Resource Cost ($)':
            # 不强制从0开始，给图例留出空间
            # 调整上限，让数据向下移动
            y_range = y_max - y_min
            ax.set_ylim(bottom=y_min - y_range * 0.1, top=y_max + y_range * 0.3)
        elif y_min >= 0:
            # 其他指标从0开始
            ax.set_ylim(bottom=0)
        
        ax.legend(loc='best', frameon=True, shadow=True, ncol=2, prop={'size': 14}, framealpha=0.9)

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
        ('security', '安全需求', 'line_security.png', 'Impact of Security Requirement'),
        ('client_count', '客户端数', 'line_clients.png', 'Impact of Client Number'),
        ('node_num', 'NF个数', 'line_nodes.png', 'Impact of Network Nodes'),
        ('degree', '度数', 'line_degree.png', 'Impact of Network Degree'),
        ('nf_instances', 'NF个数', 'line_instances.png', 'Impact of NF Instances'),
        ('client_acceptance', '客户端数', 'line_acceptance.png', 'Acceptance Rate')
    ]

    print(">>> 启动自动化可视化脚本（折线图版本）...")
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
