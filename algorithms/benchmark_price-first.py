# -*- coding: utf-8 -*-
"""
Price-first基准算法实现

策略：为每个客户端选择GPU单价最低的节点提供服务
其余逻辑（安全检查、容量约束、带宽计算、统计输出等）与Cost-first保持一致
"""

import sys
import os
import time
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from topology_config import (
    calculate_security_cost, calculate_compute_cost, calculate_bandwidth_cost,
    get_client_quantity, get_client_deployment, get_all_node_ids,
    get_all_client_ids, CLIENT_NODES, get_node_info,
    get_client_security_requirement, calculate_node_security_level,
    get_node_nf_names, S_NF_PROTECTION_MATRIX, S_NF_BASIC_INFO,
    NF_INSTANCE_ID_TO_NAME, get_service_node_ids, get_network_node_ids,
    get_client_nodes, set_active_topology, get_node_gpu_price,
    get_hops_to_client,
)


def calculate_sec_msl(node_id, client_id, security_cost_override=None):
    """
    计算Sec-MSLn,u指标，供调试或展示使用
    
    其中：
    - 安全开销 = 安全补足的NF的gpu_unit总和 × GPU单价（不包括节点原本的NF）
    - 算力开销 = 节点的gpu_unit × GPU单价
    - 带宽开销 = 跳数 × 带宽单价 × 客户端数量
    
    Args:
        node_id: 节点ID
        client_id: 客户端ID
        security_cost_override: 可选，如果提供则使用此值作为安全开销（用于安全补足场景）
    """
    client_quantity = get_client_quantity(client_id)
    if client_quantity == 0:
        return {"error": f"客户端 {client_id} 的数量为0"}

    # 如果提供了安全开销覆盖值，则使用它（通常来自安全补足），否则为0（因为只计算补足的NF）
    if security_cost_override is not None:
        security_cost = security_cost_override
    else:
        security_cost = 0.0  # 默认只计算安全补足的NF，如果没有补足则为0
    compute_cost = calculate_compute_cost(node_id)

    client_deployment = get_client_deployment()
    client_node_id = client_deployment.get(client_id)

    if not client_node_id:
        return {"error": f"客户端 {client_id} 没有对应的部署节点"}

    bandwidth_cost = calculate_bandwidth_cost(node_id, client_node_id, client_quantity)
    if bandwidth_cost == -1:
        return {"error": f"节点 {node_id} 到客户端节点 {client_node_id} 不可达"}

    total_cost = security_cost + compute_cost + bandwidth_cost
    sec_msl = total_cost / client_quantity

    return {
        "node_id": node_id,
        "client_id": client_id,
        "client_node_id": client_node_id,
        "client_quantity": client_quantity,
        "security_cost": security_cost,
        "compute_cost": compute_cost,
        "bandwidth_cost": bandwidth_cost,
        "total_cost": total_cost,
        "sec_msl": sec_msl
    }


def print_sec_msl_summary(node_id, client_id):
    """打印Sec-MSLn,u指标的详细信息"""
    details = calculate_sec_msl(node_id, client_id)

    if "error" in details:
        print(f"错误: {details['error']}")
        return

    print("=" * 60)
    print(f"Sec-MSL{node_id},{client_id} 计算详情")
    print("=" * 60)
    print(f"节点ID: {details['node_id']}")
    print(f"客户端ID: {details['client_id']}")
    print(f"客户端部署节点: {details['client_node_id']}")
    print(f"客户端数量: {details['client_quantity']}")
    print("-" * 60)
    print(f"安全开销: ${details['security_cost']:.2f}")
    print(f"算力开销: ${details['compute_cost']:.2f}")
    print(f"带宽开销: ${details['bandwidth_cost']:.2f}")
    print(f"总开销: ${details['total_cost']:.2f}")
    print("-" * 60)
    print(f"Sec-MSL{node_id},{client_id} = {details['sec_msl']:.4f}")
    print("=" * 60)


def check_node_capacity(node_id, client_id, node_used_capacity):
    """检查节点是否有足够容量服务客户端"""
    node_info = get_node_info(node_id)
    if not node_info:
        return False

    total_capacity = node_info.get("client_capacity", 0)
    used_capacity = node_used_capacity.get(node_id, 0)
    client_quantity = get_client_quantity(client_id)

    return (used_capacity + client_quantity) <= total_capacity


def _compute_combined_protection_vector(nf_names):
    """基于NF名称列表计算联合防护向量"""
    if not nf_names:
        return [0] * len(next(iter(S_NF_PROTECTION_MATRIX.values())))
    num_attacks = len(next(iter(S_NF_PROTECTION_MATRIX.values())))
    combined = [0] * num_attacks
    for nf in nf_names:
        if nf not in S_NF_PROTECTION_MATRIX:
            continue
        vec = S_NF_PROTECTION_MATRIX[nf]
        for i in range(num_attacks):
            if vec[i] > combined[i]:
                combined[i] = vec[i]
    return combined


def _sum_security_level(protection_vector):
    """求联合防护向量的总安全级别"""
    return sum(protection_vector)


def _compute_nf_contribution(nf_name, current_vector):
    """计算单个NF相对当前联合防护向量的贡献"""
    if nf_name not in S_NF_PROTECTION_MATRIX:
        return 0, [0] * len(current_vector)
    nf_vec = S_NF_PROTECTION_MATRIX[nf_name]
    num_attacks = len(current_vector)
    contrib_vec = [0] * num_attacks
    for i in range(num_attacks):
        if nf_vec[i] > current_vector[i]:
            contrib_vec[i] = nf_vec[i] - current_vector[i]
    return sum(contrib_vec), contrib_vec


def plan_security_augmentation(node_id, required_security_level):
    """
    为指定节点规划安全补足方案（不修改全局NODE_DATA）
    """
    current_nf_names = get_node_nf_names(node_id) or []
    current_vector = _compute_combined_protection_vector(current_nf_names)
    current_level = _sum_security_level(current_vector)
    original_security_level = current_level

    if current_level >= required_security_level:
        return {
            'added_nf_names': [],
            'final_security_level': current_level,
            'original_security_level': original_security_level,
            'met_requirement': True,
            'additional_security_cost': 0.0,
        }

    all_nf_names = list(S_NF_PROTECTION_MATRIX.keys())
    chosen = []
    additional_gpu_units = 0.0
    selection_steps = []

    while current_level < required_security_level:
        best_nf = None
        best_index = None
        best_contrib_sum = 0
        remaining_needed = max(0, required_security_level - current_level)

        valid_candidates = []
        for nf in all_nf_names:
            if nf in current_nf_names or nf in chosen:
                continue
            contrib_sum, _ = _compute_nf_contribution(nf, current_vector)
            if contrib_sum > 0:
                valid_candidates.append((nf, contrib_sum))

        is_last_hop_optimization = all(contrib >= remaining_needed for _, contrib in valid_candidates) if valid_candidates else False

        for nf in all_nf_names:
            if nf in current_nf_names or nf in chosen:
                continue
            contrib_sum, _ = _compute_nf_contribution(nf, current_vector)
            if contrib_sum <= 0:
                continue
            gpu_unit = S_NF_BASIC_INFO.get(nf, {}).get('gpu_unit', 0.0) or 1e-9

            if is_last_hop_optimization:
                index = remaining_needed / gpu_unit
            else:
                index = contrib_sum / gpu_unit

            if best_index is None or index > best_index or (index == best_index and contrib_sum > best_contrib_sum):
                best_index = index
                best_nf = nf
                best_contrib_sum = contrib_sum

        if best_nf is None:
            break

        _, contrib_vec = _compute_nf_contribution(best_nf, current_vector)
        for i in range(len(current_vector)):
            current_vector[i] += contrib_vec[i]
        current_level = _sum_security_level(current_vector)

        chosen.append(best_nf)
        additional_gpu_units += S_NF_BASIC_INFO.get(best_nf, {}).get('gpu_unit', 0.0)

        selection_steps.append({
            'nf': best_nf,
            'used_index': best_index,
            'contrib_sum': best_contrib_sum,
            'gpu_unit': S_NF_BASIC_INFO.get(best_nf, {}).get('gpu_unit', 0.0),
            'remaining_needed_before': remaining_needed,
            'level_after': current_level,
        })

    node_gpu_price = get_node_gpu_price(node_id)

    return {
        'added_nf_names': chosen,
        'final_security_level': current_level,
        'original_security_level': original_security_level,
        'met_requirement': current_level >= required_security_level,
        'additional_security_cost': additional_gpu_units * node_gpu_price,
        'additional_gpu_units': additional_gpu_units,
        'selection_steps': selection_steps,
    }


def price_first_algorithm():
    """
    Price-first基准算法：为每个客户端选择GPU单价最低的节点提供服务
    其他约束及流程与Cost-first算法一致
    """
    start_time = time.time()

    MS = set()
    CS = set()
    client_deployment = get_client_deployment()
    U = set(client_deployment.keys())
    node_client_mapping = {}
    node_used_capacity = {}

    total_security_cost = 0.0
    total_compute_cost = 0.0
    total_bandwidth_cost = 0.0
    security_augmentation_cost = 0.0
    total_augmented_nf_count = 0
    total_security_level_gain = 0.0
    total_augmentation_gpu_units = 0.0

    print("=" * 70)
    print("开始执行Price-first基准算法")
    print("=" * 70)
    print(f"实际部署客户端数量: {len(U)}")
    print(f"实际部署客户端列表: {sorted(U)}")
    print(f"客户端部署映射: {client_deployment}")
    print(f"网络拓扑节点: {sorted(get_network_node_ids())}")
    print(f"客户端节点: {sorted(get_client_nodes())}")
    print(f"可用候选节点: {sorted(get_service_node_ids())}")
    print("=" * 70)

    iteration = 1

    while CS != U:
        print(f"\n第 {iteration} 轮选择:")
        print("-" * 50)

        min_gpu_price = float('inf')
        best_node = None
        best_client = None
        best_details = None

        for client_id in U - CS:
            print(f"  处理客户端 {client_id}...")
            client_node_id = client_deployment.get(client_id)

            if not client_node_id:
                print(f"    警告: 客户端 {client_id} 没有对应的部署节点，跳过")
                continue

            available_nodes = set(get_service_node_ids())

            for node_id in available_nodes:
                client_security_req = get_client_security_requirement(client_id)
                node_security_level = calculate_node_security_level(node_id)

                augmentation_plan = None
                adjusted_security_cost = None
                final_security_level = node_security_level

                if node_security_level < client_security_req:
                    print(f"    节点 {node_id}: 安全级别不足 (节点级别: {node_security_level}, 需要: {client_security_req}) → 尝试安全补足")
                    augmentation_plan = plan_security_augmentation(node_id, client_security_req)
                    if not augmentation_plan.get('met_requirement', False):
                        print("      安全补足失败：无可提升或仍不足，跳过该节点")
                        continue
                    # 安全开销只计算安全补足的NF，不包括节点原本的NF
                    adjusted_security_cost = augmentation_plan['additional_security_cost']
                    final_security_level = augmentation_plan.get('final_security_level', node_security_level)

                if not check_node_capacity(node_id, client_id, node_used_capacity):
                    node_info = get_node_info(node_id)
                    total_capacity = node_info.get("client_capacity", 0)
                    used_capacity = node_used_capacity.get(node_id, 0)
                    client_quantity = get_client_quantity(client_id)
                    print(f"    节点 {node_id}: 容量不足 (已用: {used_capacity}/{total_capacity}, 需要: {client_quantity})")
                    continue

                client_quantity = get_client_quantity(client_id)
                # 安全开销只计算安全补足的NF，如果没有补足则为0
                if adjusted_security_cost is not None:
                    security_cost_val = adjusted_security_cost  # 只计算安全补足的NF的开销
                else:
                    security_cost_val = 0.0  # 没有安全补足，安全开销为0
                compute_cost_val = calculate_compute_cost(node_id)
                bandwidth_cost_val = calculate_bandwidth_cost(node_id, client_node_id, client_quantity)
                if bandwidth_cost_val == -1:
                    print(f"    节点 {node_id}: 到客户端节点不可达，跳过")
                    continue
                total_cost_val = security_cost_val + compute_cost_val + bandwidth_cost_val
                node_gpu_price = get_node_gpu_price(node_id)

                result = {
                    "node_id": node_id,
                    "client_id": client_id,
                    "client_node_id": client_node_id,
                    "client_quantity": client_quantity,
                    "security_cost": security_cost_val,
                    "compute_cost": compute_cost_val,
                    "bandwidth_cost": bandwidth_cost_val,
                    "total_cost": total_cost_val,
                    "security_level": final_security_level,
                    "gpu_price": node_gpu_price,
                    "_augmentation_plan": augmentation_plan,
                    "_original_node_security_level": node_security_level,
                    "_required_security_level": client_security_req,
                }

                print(f"    节点 {node_id}: GPU单价 = ${node_gpu_price:.2f}, 总成本 = ${total_cost_val:.2f}")

                if node_gpu_price < min_gpu_price:
                    min_gpu_price = node_gpu_price
                    best_node = node_id
                    best_client = client_id
                    best_details = result
                elif node_gpu_price == min_gpu_price:
                    if best_details is None or total_cost_val < best_details['total_cost']:
                        best_node = node_id
                        best_client = client_id
                        best_details = result

        if best_node is not None and best_client is not None:
            MS.add(best_node)

            if best_node not in node_client_mapping:
                node_client_mapping[best_node] = []
                node_used_capacity[best_node] = 0

            CS.add(best_client)
            node_client_mapping[best_node].append(best_client)
            node_used_capacity[best_node] += get_client_quantity(best_client)

            aug_plan = (best_details or {}).get('_augmentation_plan')
            if aug_plan and aug_plan.get('added_nf_names'):
                name_to_id = {v: k for k, v in NF_INSTANCE_ID_TO_NAME.items()}
                node_info_mut = get_node_info(best_node)
                nf_ids = list(node_info_mut.get('NF_instance_ids', []))
                for nf_name in aug_plan['added_nf_names']:
                    nf_id = name_to_id.get(nf_name)
                    if nf_id and nf_id not in nf_ids:
                        nf_ids.append(nf_id)
                node_info_mut['NF_instance_ids'] = nf_ids
                security_augmentation_cost += aug_plan.get('additional_security_cost', 0.0)
                total_augmented_nf_count += len(aug_plan['added_nf_names'])
                total_augmentation_gpu_units += aug_plan.get('additional_gpu_units', 0.0)
                orig = aug_plan.get('original_security_level')
                if orig is not None:
                    total_security_level_gain += (aug_plan['final_security_level'] - orig)

            total_security_cost += best_details['security_cost']
            total_compute_cost += best_details['compute_cost']
            total_bandwidth_cost += best_details['bandwidth_cost']

            print(f"\n  选择结果:")
            print(f"    最优节点: {best_node}")
            print(f"    服务客户端: {best_client}")
            print(f"    GPU单价: ${best_details['gpu_price']:.2f}")
            print(f"    安全级别: {best_details['security_level']}")
            print(f"    安全开销: ${best_details['security_cost']:.2f}")
            print(f"    算力开销: ${best_details['compute_cost']:.2f}")
            print(f"    带宽开销: ${best_details['bandwidth_cost']:.2f}")
            print(f"    总成本: ${best_details['total_cost']:.2f}")

            if '_augmentation_plan' in best_details and best_details['_augmentation_plan']:
                ap = best_details['_augmentation_plan']
                added_list = ap.get('added_nf_names', [])
                add_cost = ap.get('additional_security_cost', 0.0)
                final_level = ap.get('final_security_level')
                req_level = best_details.get('_required_security_level')
                orig_level = best_details.get('_original_node_security_level')
                print("    [AUG-DEBUG] 原安全级别/需求/最终:", orig_level, req_level, final_level)
                print("    [AUG-DEBUG] 新增NF:", added_list if added_list else '[]')
                print(f"    [AUG-DEBUG] 补足安全开销(安全部分): ${add_cost:.2f}")

            node_info = get_node_info(best_node)
            total_capacity = node_info.get("client_capacity", 0)
            used_capacity = node_used_capacity[best_node]
            remaining_capacity = total_capacity - used_capacity
            print(f"    节点容量: {used_capacity}/{total_capacity} (剩余: {remaining_capacity})")

            print(f"\n  当前状态:")
            print(f"    已选择节点: {sorted(MS)}")
            print(f"    已服务客户端: {sorted(CS)}")
            print(f"    剩余客户端: {sorted(U - CS)}")
            print(f"    节点-客户端映射: {node_client_mapping}")
            print(f"    节点容量使用: {node_used_capacity}")
        else:
            print("  错误: 无法找到有效的节点-客户端组合")
            break

        iteration += 1

    end_time = time.time()
    execution_time = end_time - start_time

    print("\n" + "=" * 70)
    print("算法执行完成")
    print("=" * 70)
    print(f"最终结果:")
    print(f"  已选择节点 (MS): {sorted(MS)}")
    print(f"  已服务客户端 (CS): {sorted(CS)}")
    print(f"  总选择节点数: {len(MS)}")
    print(f"  总服务客户端数: {len(CS)}")

    print("\n" + "=" * 70)
    print("整体运行统计")
    print("=" * 70)
    print(f"算法执行时间: {execution_time:.4f} 秒")
    print(f"总轮次数: {iteration - 1}")

    print("\n成本统计:")
    print("-" * 50)
    print(f"总安全开销: ${total_security_cost:.2f}")
    print(f"总算力开销: ${total_compute_cost:.2f}")
    print(f"总带宽开销: ${total_bandwidth_cost:.2f}")
    print(f"安全补足开销: ${security_augmentation_cost:.2f}")
    print(f"总开销: ${total_security_cost + total_compute_cost + total_bandwidth_cost:.2f}")

    print("\n节点-客户端服务关系:")
    print("-" * 50)
    for node_id in sorted(MS):
        client_list = node_client_mapping[node_id]
        node_info = get_node_info(node_id)
        total_capacity = node_info.get("client_capacity", 0)
        used_capacity = node_used_capacity[node_id]
        node_security_level = calculate_node_security_level(node_id)
        print(f"  节点 {node_id} (安全级别: {node_security_level}) → 服务客户端 {client_list} (容量: {used_capacity}/{total_capacity})")
    print("=" * 70)

    levels = [calculate_node_security_level(nid) for nid in sorted(MS)]
    max_node_security_level = max(levels) if levels else 0
    avg_node_security_level = (sum(levels) / len(levels)) if levels else 0.0

    # Client 到 Node 平均跳数（用于导出指标）
    client_deployment = get_client_deployment()
    total_hops = 0
    hop_count = 0
    for node_id, client_list in node_client_mapping.items():
        for client_id in client_list:
            client_node_id = client_deployment.get(client_id)
            if client_node_id is not None:
                h = get_hops_to_client(node_id, client_node_id)
                if h >= 0:
                    total_hops += h
                    hop_count += 1
    avg_client_node_hops = (total_hops / hop_count) if hop_count else None

    print("\n" + "=" * 70)
    print("服务节点安全级别统计")
    print("=" * 70)
    print(f"最高安全级别: {max_node_security_level}")
    print(f"平均安全级别: {avg_node_security_level:.2f}")
    print("=" * 70)

    return {
        "MS": MS,
        "CS": CS,
        "node_client_mapping": node_client_mapping,
        "node_used_capacity": node_used_capacity,
        "total_nodes": len(MS),
        "total_clients": len(CS),
        "execution_time": execution_time,
        "total_security_cost": total_security_cost,
        "total_compute_cost": total_compute_cost,
        "total_bandwidth_cost": total_bandwidth_cost,
        "total_cost": total_security_cost + total_compute_cost + total_bandwidth_cost,
        "security_augmentation_cost": security_augmentation_cost,
        "max_node_security_level": max_node_security_level,
        "avg_node_security_level": avg_node_security_level,
        "avg_client_node_hops": avg_client_node_hops,
        "total_augmented_nf_count": total_augmented_nf_count,
        "total_security_level_gain": total_security_level_gain,
        "total_augmentation_gpu_units": total_augmentation_gpu_units,
    }


def main():
    """主函数：运行Price-first基准算法"""
    print("开始运行Price-first基准算法...")
    result = price_first_algorithm()

    print("\n" + "=" * 80)
    print("算法执行结果摘要")
    print("=" * 80)
    print(f"选择的节点: {sorted(result['MS'])}")
    print(f"服务的客户端: {sorted(result['CS'])}")
    print(f"总节点数: {result['total_nodes']}")
    print(f"总客户端数: {result['total_clients']}")

    print(f"\n运行时间:")
    print(f"  总执行时间: {result['execution_time']:.4f} 秒")

    print(f"\n成本分析:")
    print(f"  总安全开销: ${result['total_security_cost']:.2f}")
    print(f"  总算力开销: ${result['total_compute_cost']:.2f}")
    print(f"  总带宽开销: ${result['total_bandwidth_cost']:.2f}")
    print(f"  安全补足开销: ${result['security_augmentation_cost']:.2f}")
    print(f"  总开销: ${result['total_cost']:.2f}")

    print("\n服务节点安全级别统计:")
    print(f"  最高安全级别: {result['max_node_security_level']}")
    print(f"  平均安全级别: {result['avg_node_security_level']:.2f}")

    print("\n详细服务关系:")
    print("-" * 40)
    for node_id in sorted(result['MS']):
        client_list = result['node_client_mapping'][node_id]
        used_capacity = result['node_used_capacity'][node_id]
        node_security_level = calculate_node_security_level(node_id)
        print(f"节点 {node_id} (安全级别: {node_security_level}) → 服务客户端 {client_list} (已用容量: {used_capacity})")

    print("=" * 80)


if __name__ == "__main__":
    set_active_topology(60)
    main()


