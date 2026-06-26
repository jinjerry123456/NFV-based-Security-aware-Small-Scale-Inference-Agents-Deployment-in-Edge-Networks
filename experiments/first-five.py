# -*- coding: utf-8 -*-
"""
并行版本：使用多进程加速六个实验的运行

相比原版本，使用 multiprocessing 并行运行六个实验，可以大幅提升速度。
每个实验在子进程中完成后立即写入独立的Excel文件，避免所有结果同时存在于内存中。
"""

import os
import sys
from multiprocessing import Pool, cpu_count
import time
from datetime import datetime
import gc

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, PatternFill


# 导入实验模块（不含客户端接受率）
import experiments.compare_algorithms_by_nodes as exp_nodes
import experiments.compare_algorithms_by_degree as exp_degree
import experiments.compare_algorithms_by_clients as exp_clients
import experiments.compare_algorithms_by_nf_instances as exp_nf
import experiments.compare_algorithms_by_security as exp_security
# import experiments.compare_algorithms_by_client_acceptance as exp_client_acceptance  # 不运行接受率实验

# 导入原有的聚合和写入函数
from experiments.export_all_comparisons_to_excel import (
    ALGORITHM_NAMES,
    METRICS,
    aggregate_by_nodes,
    aggregate_by_degree,
    aggregate_by_clients,
    aggregate_by_nf,
    aggregate_by_security,
    # aggregate_by_client_acceptance,
    write_nodes_sheet,
    write_degree_sheet,
    write_clients_sheet,
    write_nf_sheet,
    write_security_sheet,
    # write_client_acceptance_sheet,
    _set_all_num_runs,
    _set_all_generated_topologies_per_combo,
    _set_all_verbose_progress,
)


# 默认参数
DEFAULT_NUM_RUNS = 120
DEFAULT_GENERATED_TOPOLOGIES_PER_COMBO = 4
DEFAULT_VERBOSE_PROGRESS = False


def run_experiment_and_save_excel(args):
    """
    在子进程中运行实验、聚合结果并写入独立的Excel文件
    返回：(实验名称, Excel文件路径, 耗时, 错误信息)
    
    这样可以在子进程中完成所有操作，避免将大量数据传输回主进程。
    """
    exp_name, module_name, func_name, num_runs, topo_per_combo, verbose_progress, output_dir = args
    start_time = time.time()
    excel_path = None
    
    try:
        # 在子进程中重新导入实验模块（Windows spawn 模式需要）
        import importlib
        
        # 导入所有实验模块以便设置参数（不含客户端接受率）
        import experiments.compare_algorithms_by_nodes as exp_nodes
        import experiments.compare_algorithms_by_degree as exp_degree
        import experiments.compare_algorithms_by_clients as exp_clients
        import experiments.compare_algorithms_by_nf_instances as exp_nf
        import experiments.compare_algorithms_by_security as exp_security
        # import experiments.compare_algorithms_by_client_acceptance as exp_client_acceptance
        
        # 在子进程中设置参数
        for mod in (exp_nodes, exp_degree, exp_clients, exp_nf, exp_security):  # 不含 exp_client_acceptance
            if hasattr(mod, "NUM_RUNS"):
                setattr(mod, "NUM_RUNS", int(num_runs))
            if hasattr(mod, "GENERATED_TOPOLOGIES_PER_COMBO"):
                setattr(mod, "GENERATED_TOPOLOGIES_PER_COMBO", int(topo_per_combo))
            if hasattr(mod, "VERBOSE_PROGRESS"):
                setattr(mod, "VERBOSE_PROGRESS", bool(verbose_progress))
        
        # 运行实验
        module = importlib.import_module(module_name)
        exp_func = getattr(module, func_name)
        result = exp_func()
        
        # 在子进程中导入聚合和写入函数
        from experiments.export_all_comparisons_to_excel import (
            aggregate_by_nodes, write_nodes_sheet,
            aggregate_by_degree, write_degree_sheet,
            aggregate_by_clients, write_clients_sheet,
            aggregate_by_nf, write_nf_sheet,
            aggregate_by_security, write_security_sheet,
            # aggregate_by_client_acceptance, write_client_acceptance_sheet,  # 不运行接受率实验
        )
        
        # 实验名称到聚合/写入函数的映射（不含客户端接受率）
        exp_handlers = {
            "按节点数量": (aggregate_by_nodes, write_nodes_sheet),
            "按度数": (aggregate_by_degree, write_degree_sheet),
            "按客户端数量": (aggregate_by_clients, write_clients_sheet),
            "按NF个数": (aggregate_by_nf, write_nf_sheet),
            "按安全需求": (aggregate_by_security, write_security_sheet),
            # "按客户端接受率": (aggregate_by_client_acceptance, write_client_acceptance_sheet),
        }
        
        if exp_name not in exp_handlers:
            raise ValueError(f"未知的实验名称: {exp_name}")
        
        aggregate_func, write_func = exp_handlers[exp_name]
        
        # 聚合结果
        summary = aggregate_func(result)
        
        # 释放原始结果数据
        del result
        gc.collect()
        
        # 创建Excel文件
        wb = Workbook()
        default_sheet = wb.active
        wb.remove(default_sheet)
        
        # 写入数据
        write_func(wb, summary)
        
        # 保存Excel文件（output_dir已经在主进程中创建，但为了安全再次检查）
        excel_filename = f"{exp_name}.xlsx"
        excel_path = os.path.join(output_dir, excel_filename)
        
        # 确保输出目录存在（虽然主进程已创建，但多进程环境下再次检查更安全）
        os.makedirs(output_dir, exist_ok=True)
        
        wb.save(excel_path)
        
        # 释放内存
        del summary
        del wb
        gc.collect()
        
        elapsed = time.time() - start_time
        return (exp_name, excel_path, elapsed, None)
        
    except Exception as e:
        elapsed = time.time() - start_time
        import traceback
        error_msg = f"{str(e)}\n{traceback.format_exc()}"
        return (exp_name, excel_path, elapsed, error_msg)


def main(
    num_runs: int = DEFAULT_NUM_RUNS,
    topo_per_combo: int = DEFAULT_GENERATED_TOPOLOGIES_PER_COMBO,
    verbose_progress: bool = DEFAULT_VERBOSE_PROGRESS,
    num_processes: int = None,
):
    """
    并行运行六个实验并导出 Excel 汇总
    
    参数：
        num_processes: 使用的进程数，默认为 CPU 核心数（最多6个）
    
    每个实验将生成一个独立的Excel文件，所有文件放在 results/{NUM_RUNS}_{TOPO_PER_COMBO}_{TIMESTAMP}/ 文件夹中
    """
    # 创建输出文件夹：results/{NUM_RUNS}_{TOPO_PER_COMBO}_{TIMESTAMP}/
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    folder_name = f"{num_runs}_{topo_per_combo}_{timestamp}"
    output_dir = os.path.join("results", folder_name)
    
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    print("=" * 80)
    print("并行运行五个实验并导出 Excel 汇总（每个实验独立写入Excel，不含客户端接受率）")
    print("=" * 80)

    # 统一设置六个实验脚本的运行次数
    _set_all_num_runs(num_runs)
    _set_all_generated_topologies_per_combo(topo_per_combo)
    _set_all_verbose_progress(verbose_progress)
    
    # 确定使用的进程数（5个实验，最多5个进程）
    if num_processes is None:
        num_processes = min(cpu_count(), 5)  # 最多5个进程（对应5个实验，不含客户端接受率）
    
    print(f"\n本次实验参数：")
    print(f"  - NUM_RUNS = {num_runs}")
    print(f"  - 每个(size, degree)生成的拓扑数量 = {topo_per_combo}")
    print(f"  - VERBOSE_PROGRESS = {verbose_progress}")
    print(f"  - 并行进程数 = {num_processes}")
    print(f"  - CPU 核心数 = {cpu_count()}")
    print(f"  - 输出文件夹: {output_dir}")
    print(f"  - 每个实验将写入独立的Excel文件")

    # 定义五个实验（不含客户端接受率）
    experiments = [
        ("按节点数量", "experiments.compare_algorithms_by_nodes", "run_all_algorithms_by_nodes", num_runs, topo_per_combo, verbose_progress, output_dir),
        ("按度数", "experiments.compare_algorithms_by_degree", "run_all_algorithms_by_degree", num_runs, topo_per_combo, verbose_progress, output_dir),
        ("按客户端数量", "experiments.compare_algorithms_by_clients", "run_all_algorithms_by_clients", num_runs, topo_per_combo, verbose_progress, output_dir),
        ("按NF个数", "experiments.compare_algorithms_by_nf_instances", "run_all_algorithms_by_nf_instances", num_runs, topo_per_combo, verbose_progress, output_dir),
        ("按安全需求", "experiments.compare_algorithms_by_security", "run_all_algorithms_by_security_requirement", num_runs, topo_per_combo, verbose_progress, output_dir),
        # ("按客户端接受率", "experiments.compare_algorithms_by_client_acceptance", "run_all_algorithms_by_client_acceptance", num_runs, topo_per_combo, verbose_progress, output_dir),
    ]

    # 并行运行实验（每个实验在子进程中完成并写入独立的Excel文件）
    print(f"\n开始并行运行 {len(experiments)} 个实验...")
    print(f"每个实验将在完成后立即写入独立的Excel文件")
    start_time = time.time()
    
    with Pool(processes=num_processes) as pool:
        results = pool.map(run_experiment_and_save_excel, experiments)
    
    total_time = time.time() - start_time
    
    # 检查结果
    print(f"\n实验完成！总耗时: {total_time:.2f} 秒")
    print("\n各实验耗时和Excel文件：")
    
    excel_files = []
    for exp_name, excel_path, elapsed, error in results:
        if error:
            print(f"  ✗ {exp_name}: 失败 ({elapsed:.2f}s)")
            print(f"    错误: {error[:200]}...")  # 只显示前200个字符
            raise RuntimeError(f"实验 '{exp_name}' 失败: {error}")
        else:
            print(f"  ✓ {exp_name}: {elapsed:.2f} 秒")
            print(f"    Excel文件: {excel_path}")
            excel_files.append(excel_path)
    
    print(f"\n✓ 所有结果已保存到文件夹: {output_dir}")
    print(f"✓ 共生成 {len(excel_files)} 个Excel文件")
    print(f"✓ 总耗时: {total_time:.2f} 秒")
    print("=" * 80)
    
    return output_dir


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="并行运行五个实验并导出 Excel 汇总（不含客户端接受率，每个实验独立写入Excel文件）")
    parser.add_argument("--runs", "-r", type=int, default=DEFAULT_NUM_RUNS,
                        help="每个配置的运行次数")
    parser.add_argument("--topo", "-t", type=int, default=DEFAULT_GENERATED_TOPOLOGIES_PER_COMBO,
                        help="每个(size, degree)生成的拓扑数量")
    parser.add_argument("--verbose", "-v", action="store_true",
                        help=f"打印详细进度信息（默认: {DEFAULT_VERBOSE_PROGRESS}）")
    parser.add_argument("--no-verbose", action="store_true",
                        help="不打印详细进度信息（覆盖默认值）")
    parser.add_argument("--processes", "-p", type=int, default=None,
                        help="并行进程数（默认为CPU核心数，最多6）")
    
    args = parser.parse_args()
    
    # 处理verbose参数
    import sys
    has_verbose_flag = '--verbose' in sys.argv or '-v' in sys.argv
    has_no_verbose_flag = '--no-verbose' in sys.argv
    
    if has_no_verbose_flag:
        verbose_progress = False
    elif has_verbose_flag:
        verbose_progress = True
    else:
        verbose_progress = DEFAULT_VERBOSE_PROGRESS
    
    main(
        num_runs=args.runs,
        topo_per_combo=args.topo,
        verbose_progress=verbose_progress,
        num_processes=args.processes,
    )
