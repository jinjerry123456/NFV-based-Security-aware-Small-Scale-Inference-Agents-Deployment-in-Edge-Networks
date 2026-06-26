import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
import os
import glob

def plot_network_simulation(file_path, x_col_name, output_filename, title_suffix=""):
    """
    针对网络仿真数据生成学术风格的对比图，并将结果保存到 results/visualization 文件夹中。
    """
    print(f">>> 正在处理: {file_path}")
    
    # 1. 确保输出目录存在
    output_dir = os.path.join("results", "visualization")
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        print(f"已创建目录: {output_dir}")
        
    output_path = os.path.join(output_dir, output_filename)

    # 2. 读取数据 (支持 .xlsx 和 .csv)
    try:
        if file_path.endswith('.xlsx'):
            df_raw = pd.read_excel(file_path)
        else:
            df_raw = pd.read_csv(file_path)
    except Exception as e:
        print(f"读取文件错误 {file_path}: {e}")
        return

    algorithms = ['My Algorithm', 'Cost-first', 'Price-first', 'Security-first']
    
    # 中英文标签映射，解决乱码并符合学术规范
    x_label_map = {
        '安全需求': 'Security Requirement (theta)',
        '客户端数': 'Number of Clients',
        'NF个数': 'Number of NFs',
        '度数': 'Network Degree'
    }
    eng_x_label = x_label_map.get(x_col_name, x_col_name)

    # 根据文件名决定绘制的指标
    if "acceptance" in file_path.lower():
        metrics_map = {'接受率': 'Acceptance Rate'}
        fig_height, rows = 6, 1
    else:
        metrics_map = {
            '运行时间 (s)': 'Runtime (s)',
            '总体成本 ($)': 'Total Cost ($)',
            '平均安全级别': 'Average Security Level'
        }
        fig_height, rows = 15, 3

    # 3. 设置绘图参数
    plt.rcParams['font.family'] = 'DejaVu Sans' # 使用系统自带字体，避免中文字体缺失报错
    plt.rcParams['font.size'] = 11
    plt.rcParams['axes.linewidth'] = 1.2
    
    colors = {'My Algorithm': '#56AEDE', 'Cost-first': '#EE7A5F', 
              'Price-first': '#F18F01', 'Security-first': '#C73E1D'}
    markers = {'My Algorithm': 'o', 'Cost-first': 's', 'Price-first': '^', 'Security-first': 'D'}

    fig, axes = plt.subplots(rows, 1, figsize=(9, fig_height))
    if rows == 1: axes = [axes]
    
    # 清理 X 轴数据
    df_metrics = df_raw[df_raw['指标/统计'].notna()].copy()
    df_metrics[x_col_name] = pd.to_numeric(df_metrics[x_col_name], errors='coerce')
    df_metrics = df_metrics.dropna(subset=[x_col_name])
    x_values = sorted(df_metrics[x_col_name].unique())

    # 4. 循环绘制每个指标
    for ax, (metric_prefix, ylabel) in zip(axes, metrics_map.items()):
        plotted_any = False
        for algo in algorithms:
            means, mins, maxs = [], [], []
            for x in x_values:
                subset = df_metrics[df_metrics[x_col_name] == x]
                try:
                    # 使用 regex=False 修复含有 $ 符号时的正则匹配警告
                    row_avg = subset[subset['指标/统计'].str.contains(f"{metric_prefix}-平均值", regex=False)]
                    row_min = subset[subset['指标/统计'].str.contains(f"{metric_prefix}-最小值", regex=False)]
                    row_max = subset[subset['指标/统计'].str.contains(f"{metric_prefix}-最大值", regex=False)]
                    
                    if not row_avg.empty:
                        means.append(row_avg[algo].values[0])
                        mins.append(row_min[algo].values[0])
                        maxs.append(row_max[algo].values[0])
                except Exception:
                    continue
            
            if means:
                yerr = [np.array(means)-np.array(mins), np.array(maxs)-np.array(means)]
                ax.errorbar(x_values, means, yerr=yerr, label=algo, color=colors[algo], 
                            marker=markers[algo], linewidth=2, capsize=4, alpha=0.9,
                            markersize=7)
                plotted_any = True

        ax.set_title(f'{ylabel} vs {title_suffix}', fontsize=13, fontweight='bold', pad=10)
        ax.set_xlabel(eng_x_label, fontsize=11, fontweight='bold')
        ax.set_ylabel(ylabel, fontsize=11, fontweight='bold')
        ax.grid(True, alpha=0.3, linestyle='--')
        if plotted_any:
            ax.legend(loc='best', fontsize=9, frameon=True)
        ax.set_facecolor('#fcfcfc')

    plt.tight_layout(pad=3.0)
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    plt.close()
    print(f"成功保存图表到: {output_path}")

def find_latest_file(pattern):
    """ 在 results 文件夹下搜索包含关键字的文件 """
    files = glob.glob(os.path.join("results", f"*{pattern}*"))
    return files[0] if files else None

if __name__ == "__main__":
    # 任务列表: (文件关键字, X轴原始列名, 输出图片名, 标题后缀)
    tasks = [
        ('security', '安全需求', 'plot_security.png', 'Security Requirement'),
        ('client_count', '客户端数', 'plot_clients.png', 'Client Number'),
        ('node_num', 'NF个数', 'plot_nodes.png', 'Network Nodes'),
        ('degree', '度数', 'plot_degree.png', 'Network Degree'),
        ('nf_instances', 'NF个数', 'plot_instances.png', 'Instance Count'),
        ('client_acceptance', '客户端数', 'plot_acceptance.png', 'Acceptance Rate')
    ]

    print(">>> 启动自动化可视化脚本...")
    if not os.path.exists("results"):
        print("错误: 找不到 'results' 文件夹，请确保脚本在正确的位置运行。")
    else:
        for pattern, x_name, out_file, suffix in tasks:
            path = find_latest_file(pattern)
            if path:
                plot_network_simulation(path, x_name, out_file, suffix)
            else:
                print(f"未找到匹配 '{pattern}' 的文件")
    print(">>> 任务完成！")