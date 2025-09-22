import re

def parse_average_retrieval_time(log_file):
    times = []

    # 正则匹配 "Average retrival time=xxxxs"
    # pattern = re.compile(r"Average retrival time=([\d.]+)s")
    pattern = re.compile(r"Average tokens: ([\d.]+)")
    # Average retrival time=
    # Time after llm=
    # Average tokens: ([\d.]+)

    with open(log_file, "r", encoding="utf-8") as f:
        for line in f:
            match = pattern.search(line)
            if match:
                times.append(float(match.group(1)))

    if times:
        # filtered = [x for x in times if 20 <= x <= 300]
        avg_time = sum(times) / len(times)
        print(f"共提取到 {len(times)} 条记录")
        print(f"平均检索时间: {avg_time:.4f}s")
    else:
        print("未找到任何 Average retrival time 记录")

if __name__ == "__main__":
    log_path = "/home/mengke/code/GraphRAG/log.txt"  # 换成你的日志文件路径
    parse_average_retrieval_time(log_path)