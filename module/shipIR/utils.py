# Mappings from Chinese to English arguments for dock_filter_set
INDEX_MAP = {
    '全部': 'all', '前排': 'vanguard', '后排': 'main',
    '驱逐': 'dd', '轻巡': 'cl', '重巡': 'ca', '战列': 'bb',
    '航母': 'cv', '维修': 'repair', '潜艇': 'ss', '其他': 'others',
    '前排先锋': 'vanguard', '后排主力': 'main'
}

FACTION_MAP = {
    '全部': 'all', '白鹰': 'eagle', '皇家': 'royal', '重樱': 'sakura',
    '铁血': 'iron', '东煌': 'dragon', '撒丁帝国': 'sardegna',
    '北方联合': 'northern', '自由鸢尾': 'iris', '维希教廷': 'vichya',
    '郁金王国': 'tulipa','META': 'meta', '飓风': 'tempesta', '其他': 'other'
}

RARITY_MAP = {
    '全部': 'all', '普通': 'common', '稀有': 'rare', 
    '精锐': 'elite', '超稀有': 'super_rare', '海上传奇': 'ultra',
    '紫色': 'elite', '金色': 'super_rare', '彩色': 'ultra'
}

EXTRA_MAP = {
    '无限制': 'no_limit', '特殊': 'special', '未获取': 'un_get'
}



def convert_filter_to_params(check_filter: list) -> dict:
    """
    Converts a list of Chinese filter strings into a dictionary of parameters
    for the `dock_filter_set` method, based on a fixed order.
    Required order: [index, faction, rarity, extra]

    Args:
        check_filter: A list of 4 Chinese strings representing filter options.
                      Example: ["轻巡", "白鹰", "精锐", "无限制"]

    Returns:
        A dictionary of parameters for dock_filter_set.
        Example: {'index': 'cl', 'faction': 'eagle', 'rarity': 'elite', 'extra': 'no_limit'}
    """
    if len(check_filter) != 4:
        print(f"Error: check_filter must contain exactly 4 items, but got {len(check_filter)}.")
        return {}

    maps_in_order = [INDEX_MAP, FACTION_MAP, RARITY_MAP, EXTRA_MAP]
    param_names = ['index', 'faction', 'rarity', 'extra']
    params = {}

    for i, item in enumerate(check_filter):
        current_map = maps_in_order[i]
        param_name = param_names[i]
        
        if item in current_map:
            params[param_name] = current_map[item]
        else:
            print(f"Warning: Filter '{item}' at position {i+1} is not a valid value for category '{param_name}'. It will be ignored.")

    return params 

if __name__ == "__main__":
    check_filter1 = ["前排先锋","白鹰","稀有","无限制"]
    check_filter2 = ["轻巡","白鹰","精锐","无限制"]
    check_filter3 = ["轻巡","白鹰","全部","无限制"]

    params1 = convert_filter_to_params(check_filter1)
    params2 = convert_filter_to_params(check_filter2)
    params3 = convert_filter_to_params(check_filter3)

    # 打印出来看看结果
    print(f"{check_filter1} -> {params1}")
    print(f"{check_filter2} -> {params2}")
    print(f"{check_filter3} -> {params3}")