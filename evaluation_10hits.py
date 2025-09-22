import json
import argparse
import os
from collections import defaultdict
import re


def normalize_text(text):
    """
    语义标准化：处理标点、大小写、空格、缩写和同义词
    """
    import re
    
    if not isinstance(text, str):
        text = str(text)
    
    # 转换为小写
    text = text.lower()
    
    # 处理日期格式标准化 (2015-06-20 -> 2015 06 20)
    text = re.sub(r'(\d{4})[/-](\d{1,2})[/-](\d{1,2})', r'\1 \2 \3', text)
    
    # 处理时间格式标准化 (12:30 -> 12 30)
    text = re.sub(r'(\d{1,2}):(\d{2})', r'\1 \2', text)
    
    # 去除所有标点符号，只保留字母、数字和空格
    text = re.sub(r'[^\w\s]', ' ', text)
    
    # 处理常见缩写展开
    abbreviations = {
        'uk': 'united kingdom',
        'usa': 'united states america',
        'us': 'united states',
        'pm': 'prime minister',
        'pres': 'president',
        'min': 'minister',
        'dept': 'department',
        'gov': 'government',
        'assoc': 'association',
        'org': 'organization',
        'corp': 'corporation',
        'ltd': 'limited',
        'inc': 'incorporated'
    }
    
    words = text.split()
    normalized_words = []
    for word in words:
        if word in abbreviations:
            normalized_words.extend(abbreviations[word].split())
        else:
            normalized_words.append(word)
    
    text = ' '.join(normalized_words)
    
    # 同义词映射
    synonyms = {
        'cabinet': 'council',
        'advisors': 'advisers', 
        'adviser': 'advisor',
        'britain': 'united kingdom',
        'england': 'united kingdom', 
        'great britain': 'united kingdom',
        'america': 'united states',
        'usa': 'united states',
        'insurgency': 'rebellion',
        'violence': 'attack',
        'unconventional violence': 'terrorist attack',
        'prime minister': 'pm',
        'president': 'pres'
    }
    
    # 应用同义词替换
    for synonym, replacement in synonyms.items():
        text = text.replace(synonym, replacement)
    
    # 去重复词汇 (council council -> council)
    words = text.split()
    unique_words = []
    for word in words:
        if not unique_words or word != unique_words[-1]:
            unique_words.append(word)
    
    # 标准化空格
    text = ' '.join(unique_words)
    
    return text


def extract_answer1_from_output(output):
    """
    从output中提取answer1:后的引号内文本
    支持多种引号格式: "text", 'text', "text", 'text'
    """
    if not output:
        return None
    
    # 匹配 answer1: 后的引号内容，支持多种引号
    patterns = [
        r'answer1\s*:\s*["\'""]([^"\'""]*?)["\'""]',  # answer1: "text"
        r'answer1\s*:\s*([^,\n\r]+)',  # answer1: text (无引号)
    ]
    
    for pattern in patterns:
        match = re.search(pattern, output, re.IGNORECASE)
        if match:
            extracted_text = match.group(1).strip()
            if extracted_text:  # 确保不是空字符串
                return extracted_text
    
    return None


def extract_answers_1to5_from_output(output):
    """
    从output中提取answer1到answer5的所有答案
    返回字典格式: {'answer1': 'text1', 'answer2': 'text2', ...}
    """
    if not output:
        return {}
    
    extracted_answers = {}
    
    # 遍历answer1到answer5
    for i in range(1, 6):
        answer_key = f'answer{i}'
        
        # 匹配 answerN: 后的引号内容，支持多种引号
        patterns = [
            rf'{answer_key}\s*:\s*["\'""]([^"\'""]*?)["\'""]',  # answerN: "text"
            rf'{answer_key}\s*:\s*([^,\n\r]+)',  # answerN: text (无引号)
        ]
        
        for pattern in patterns:
            match = re.search(pattern, output, re.IGNORECASE)
            if match:
                extracted_text = match.group(1).strip()
                if extracted_text:  # 确保不是空字符串
                    extracted_answers[answer_key] = extracted_text
                    break  # 找到匹配就跳出内层循环
    
    return extracted_answers


def check_answer_match(answers, output):
    """
    检查output是否包含答案列表中的任一答案
    使用语义标准化进行匹配
    """
    if not answers or not output:
        return False
    
    # 标准化output
    normalized_output = normalize_text(output)
    
    # 遍历所有可能的答案
    for answer in answers:
        # 标准化答案
        normalized_answer = normalize_text(answer)
        
        # 检查标准化后的答案是否在标准化后的output中
        if normalized_answer and normalized_answer in normalized_output:
            return True
    
    return False


def check_answer1_match(answers, extracted_answer1):
    """
    检查提取的answer1文本是否与标准答案匹配
    """
    if not answers or not extracted_answer1:
        return False
    
    # 标准化提取的answer1
    normalized_answer1 = normalize_text(extracted_answer1)
    
    # 遍历所有可能的答案
    for answer in answers:
        # 标准化答案
        normalized_answer = normalize_text(answer)
        
        # 检查标准化后的答案是否匹配
        if normalized_answer and normalized_answer1 and normalized_answer == normalized_answer1:
            return True
        # 也支持包含关系匹配
        if normalized_answer and normalized_answer1 and normalized_answer in normalized_answer1:
            return True
    
    return False


def check_answers_1to5_match(answers, extracted_answers_1to5):
    """
    检查提取的answer1-5中是否有任一个与标准答案匹配
    """
    if not answers or not extracted_answers_1to5:
        return False, {}
    
    match_details = {}  # 记录每个提取答案的匹配情况
    
    # 遍历所有提取的答案（answer1到answer5）
    for answer_key, extracted_answer in extracted_answers_1to5.items():
        if not extracted_answer:
            match_details[answer_key] = False
            continue
            
        # 标准化提取的答案
        normalized_extracted = normalize_text(extracted_answer)
        is_match = False
        
        # 与标准答案列表进行匹配
        for standard_answer in answers:
            normalized_standard = normalize_text(standard_answer)
            
            # 检查是否匹配（完全匹配或包含关系）
            if normalized_standard and normalized_extracted:
                if (normalized_standard == normalized_extracted or 
                    normalized_standard in normalized_extracted):
                    is_match = True
                    break
        
        match_details[answer_key] = is_match
        
        # 如果有任一个匹配，就返回True
        if is_match:
            return True, match_details
    
    return False, match_details


def evaluate_single_item(item):
    """评估单个问答项目，包括整体匹配、answer1提取匹配和hit5匹配"""
    answer = item.get("answer", [])
    output = item.get("output", "")
    
    # 1. 检查整体匹配 (原有逻辑)
    is_correct_full = check_answer_match(answer, output)
    
    # 2. 提取answer1并检查匹配
    extracted_answer1 = extract_answer1_from_output(output)
    is_correct_answer1 = check_answer1_match(answer, extracted_answer1)
    
    # 3. 提取answer1-5并检查匹配（新增hit5功能）
    extracted_answers_1to5 = extract_answers_1to5_from_output(output)
    is_correct_hit5, hit5_match_details = check_answers_1to5_match(answer, extracted_answers_1to5)
    
    # 创建评估结果
    evaluation_item = item.copy()
    evaluation_item["10hit_accu"] = 1 if is_correct_full else 0  # 整体文本匹配
    evaluation_item["1hit_accu"] = 1 if is_correct_answer1 else 0  # answer1提取匹配
    evaluation_item["5hit_accu"] = 1 if is_correct_hit5 else 0  # hit5匹配（新增）
    evaluation_item["extracted_answer1"] = extracted_answer1 if extracted_answer1 else ""  # 记录提取的answer1
    evaluation_item["extracted_answers_1to5"] = extracted_answers_1to5  # 记录提取的answer1-5（新增）
    evaluation_item["hit5_match_details"] = hit5_match_details  # 记录每个答案的匹配详情（新增）
    
    # 保持向后兼容
    evaluation_item["accuracy"] = evaluation_item["10hit_accu"]
    
    return evaluation_item


def process_results(input_path, output_path):
    """处理结果文件，生成评估文件"""
    evaluation_results = []
    
    print(f"Reading results from: {input_path}")
    print(f"Using semantic normalization (handles punctuation, abbreviations, synonyms)")
    
    with open(input_path, 'r', encoding='utf-8') as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
                
            try:
                item = json.loads(line)
                evaluation_item = evaluate_single_item(item)
                evaluation_results.append(evaluation_item)
                
                # 打印一些处理进度和样例
                if line_num <= 5 or line_num % 100 == 0:
                    answer = item.get("answer", [])
                    output = item.get("output", "")
                    accuracy = evaluation_item["accuracy"]
                    hit5_accu = evaluation_item["5hit_accu"]
                    extracted_1to5 = evaluation_item["extracted_answers_1to5"]
                    print(f"Line {line_num}: Answer={answer[:50] if answer else 'None'}...")
                    print(f"  -> 10hit: {accuracy}, 5hit: {hit5_accu}, Extracted: {list(extracted_1to5.keys())}")
                    
            except json.JSONDecodeError as e:
                print(f"Warning: Could not parse line {line_num}: {e}")
                continue
    
    # 保存评估结果
    print(f"Saving evaluation results to: {output_path}")
    with open(output_path, 'w', encoding='utf-8') as f:
        for item in evaluation_results:
            json.dump(item, f, ensure_ascii=False)
            f.write('\n')
    
    print(f"Successfully processed {len(evaluation_results)} items")
    return evaluation_results


def generate_statistics(evaluation_results):
    """生成统计信息，包括10hit_accu、1hit_accu和5hit_accu"""
    stats = {
        'overall_10hit': {'count': 0, 'correct': 0, 'accuracy': 0.0},
        'overall_1hit': {'count': 0, 'correct': 0, 'accuracy': 0.0},
        'overall_5hit': {'count': 0, 'correct': 0, 'accuracy': 0.0},  # 新增
        'by_qlabel_10hit': defaultdict(lambda: {'count': 0, 'correct': 0, 'accuracy': 0.0}),
        'by_qlabel_1hit': defaultdict(lambda: {'count': 0, 'correct': 0, 'accuracy': 0.0}),
        'by_qlabel_5hit': defaultdict(lambda: {'count': 0, 'correct': 0, 'accuracy': 0.0}),  # 新增
        'by_answer_type_10hit': defaultdict(lambda: {'count': 0, 'correct': 0, 'accuracy': 0.0}),
        'by_answer_type_1hit': defaultdict(lambda: {'count': 0, 'correct': 0, 'accuracy': 0.0}),
        'by_answer_type_5hit': defaultdict(lambda: {'count': 0, 'correct': 0, 'accuracy': 0.0}),  # 新增
        'answer1_extraction_stats': {'total': 0, 'extracted': 0, 'extraction_rate': 0.0},
        'answers_1to5_extraction_stats': {  # 新增
            'total': 0, 
            'at_least_one_extracted': 0, 
            'extraction_rate': 0.0,
            'by_position': {f'answer{i}': {'extracted': 0, 'rate': 0.0} for i in range(1, 6)}
        }
    }
    
    for item in evaluation_results:
        accuracy_10hit = item.get('10hit_accu', 0)
        accuracy_1hit = item.get('1hit_accu', 0)
        accuracy_5hit = item.get('5hit_accu', 0)  # 新增
        extracted_answer1 = item.get('extracted_answer1', '')
        extracted_answers_1to5 = item.get('extracted_answers_1to5', {})  # 新增
        qlabel = item.get('qlabel', 'Unknown')
        answer_type = item.get('answer_type', 'Unknown')
        
        # Answer1提取统计
        stats['answer1_extraction_stats']['total'] += 1
        if extracted_answer1:
            stats['answer1_extraction_stats']['extracted'] += 1
        
        # Answers1-5提取统计（新增）
        stats['answers_1to5_extraction_stats']['total'] += 1
        if extracted_answers_1to5:
            stats['answers_1to5_extraction_stats']['at_least_one_extracted'] += 1
        
        # 按位置统计提取情况
        for i in range(1, 6):
            answer_key = f'answer{i}'
            if answer_key in extracted_answers_1to5 and extracted_answers_1to5[answer_key]:
                stats['answers_1to5_extraction_stats']['by_position'][answer_key]['extracted'] += 1
        
        # 10hit整体统计
        stats['overall_10hit']['count'] += 1
        stats['overall_10hit']['correct'] += accuracy_10hit
        
        # 1hit整体统计
        stats['overall_1hit']['count'] += 1
        stats['overall_1hit']['correct'] += accuracy_1hit
        
        # 5hit整体统计（新增）
        stats['overall_5hit']['count'] += 1
        stats['overall_5hit']['correct'] += accuracy_5hit
        
        # 按qlabel统计 - 10hit
        stats['by_qlabel_10hit'][qlabel]['count'] += 1
        stats['by_qlabel_10hit'][qlabel]['correct'] += accuracy_10hit
        
        # 按qlabel统计 - 1hit
        stats['by_qlabel_1hit'][qlabel]['count'] += 1
        stats['by_qlabel_1hit'][qlabel]['correct'] += accuracy_1hit
        
        # 按qlabel统计 - 5hit（新增）
        stats['by_qlabel_5hit'][qlabel]['count'] += 1
        stats['by_qlabel_5hit'][qlabel]['correct'] += accuracy_5hit
        
        # 按answer_type统计 - 10hit
        stats['by_answer_type_10hit'][answer_type]['count'] += 1
        stats['by_answer_type_10hit'][answer_type]['correct'] += accuracy_10hit
        
        # 按answer_type统计 - 1hit
        stats['by_answer_type_1hit'][answer_type]['count'] += 1
        stats['by_answer_type_1hit'][answer_type]['correct'] += accuracy_1hit
        
        # 按answer_type统计 - 5hit（新增）
        stats['by_answer_type_5hit'][answer_type]['count'] += 1
        stats['by_answer_type_5hit'][answer_type]['correct'] += accuracy_5hit
    
    # 计算准确率
    if stats['overall_10hit']['count'] > 0:
        stats['overall_10hit']['accuracy'] = stats['overall_10hit']['correct'] / stats['overall_10hit']['count']
    
    if stats['overall_1hit']['count'] > 0:
        stats['overall_1hit']['accuracy'] = stats['overall_1hit']['correct'] / stats['overall_1hit']['count']
    
    if stats['overall_5hit']['count'] > 0:  # 新增
        stats['overall_5hit']['accuracy'] = stats['overall_5hit']['correct'] / stats['overall_5hit']['count']
    
    # 计算answer1提取率
    if stats['answer1_extraction_stats']['total'] > 0:
        stats['answer1_extraction_stats']['extraction_rate'] = stats['answer1_extraction_stats']['extracted'] / stats['answer1_extraction_stats']['total']
    
    # 计算answers1-5提取率（新增）
    if stats['answers_1to5_extraction_stats']['total'] > 0:
        stats['answers_1to5_extraction_stats']['extraction_rate'] = (
            stats['answers_1to5_extraction_stats']['at_least_one_extracted'] / 
            stats['answers_1to5_extraction_stats']['total']
        )
        
        # 计算每个位置的提取率
        total = stats['answers_1to5_extraction_stats']['total']
        for i in range(1, 6):
            answer_key = f'answer{i}'
            extracted = stats['answers_1to5_extraction_stats']['by_position'][answer_key]['extracted']
            stats['answers_1to5_extraction_stats']['by_position'][answer_key]['rate'] = extracted / total
    
    # 计算分类准确率
    for category in stats['by_qlabel_10hit'].values():
        if category['count'] > 0:
            category['accuracy'] = category['correct'] / category['count']
    
    for category in stats['by_qlabel_1hit'].values():
        if category['count'] > 0:
            category['accuracy'] = category['correct'] / category['count']
    
    for category in stats['by_qlabel_5hit'].values():  # 新增
        if category['count'] > 0:
            category['accuracy'] = category['correct'] / category['count']
    
    for category in stats['by_answer_type_10hit'].values():
        if category['count'] > 0:
            category['accuracy'] = category['correct'] / category['count']
    
    for category in stats['by_answer_type_1hit'].values():
        if category['count'] > 0:
            category['accuracy'] = category['correct'] / category['count']
    
    for category in stats['by_answer_type_5hit'].values():  # 新增
        if category['count'] > 0:
            category['accuracy'] = category['correct'] / category['count']
    
    return stats


def print_statistics(stats):
    """打印统计信息"""
    print("\n" + "="*70)
    print("EVALUATION STATISTICS")
    print("="*70)
    
    # Answer1提取统计
    extract_stats = stats['answer1_extraction_stats']
    print(f"\nAnswer1 Extraction Statistics:")
    print(f"  Total Questions: {extract_stats['total']}")
    print(f"  Successfully Extracted: {extract_stats['extracted']}")
    print(f"  Extraction Rate: {extract_stats['extraction_rate']:.4f} ({extract_stats['extraction_rate']*100:.2f}%)")
    
    # Answers1-5提取统计（新增）
    extract_1to5_stats = stats['answers_1to5_extraction_stats']
    print(f"\nAnswers1-5 Extraction Statistics:")
    print(f"  Total Questions: {extract_1to5_stats['total']}")
    print(f"  At Least One Extracted: {extract_1to5_stats['at_least_one_extracted']}")
    print(f"  Extraction Rate: {extract_1to5_stats['extraction_rate']:.4f} ({extract_1to5_stats['extraction_rate']*100:.2f}%)")
    print(f"  By Position:")
    for i in range(1, 6):
        answer_key = f'answer{i}'
        pos_stats = extract_1to5_stats['by_position'][answer_key]
        print(f"    {answer_key}: {pos_stats['extracted']} ({pos_stats['rate']:.4f})")
    
    # 整体统计 - 10hit
    overall_10hit = stats['overall_10hit']
    print(f"\nOverall Performance (10hit - Full Text Matching):")
    print(f"  Total Questions: {overall_10hit['count']}")
    print(f"  Correct Answers: {overall_10hit['correct']}")
    print(f"  10hit Accuracy: {overall_10hit['accuracy']:.4f} ({overall_10hit['accuracy']*100:.2f}%)")
    
    # 整体统计 - 1hit
    overall_1hit = stats['overall_1hit']
    print(f"\nOverall Performance (1hit - Answer1 Extraction Matching):")
    print(f"  Total Questions: {overall_1hit['count']}")
    print(f"  Correct Answers: {overall_1hit['correct']}")
    print(f"  1hit Accuracy: {overall_1hit['accuracy']:.4f} ({overall_1hit['accuracy']*100:.2f}%)")
    
    # 整体统计 - 5hit（新增）
    overall_5hit = stats['overall_5hit']
    print(f"\nOverall Performance (5hit - Answer1-5 Extraction Matching):")
    print(f"  Total Questions: {overall_5hit['count']}")
    print(f"  Correct Answers: {overall_5hit['correct']}")
    print(f"  5hit Accuracy: {overall_5hit['accuracy']:.4f} ({overall_5hit['accuracy']*100:.2f}%)")
    
    # 按qlabel统计
    print(f"\nPerformance by Question Label:")
    all_qlabels = set(stats['by_qlabel_10hit'].keys()) | set(stats['by_qlabel_1hit'].keys()) | set(stats['by_qlabel_5hit'].keys())
    for qlabel in sorted(all_qlabels):
        data_10hit = stats['by_qlabel_10hit'][qlabel]
        data_1hit = stats['by_qlabel_1hit'][qlabel]
        data_5hit = stats['by_qlabel_5hit'][qlabel]  # 新增
        print(f"  {qlabel}:")
        print(f"    Count: {data_10hit['count']}")
        print(f"    10hit Accuracy: {data_10hit['accuracy']:.4f} ({data_10hit['accuracy']*100:.2f}%)")
        print(f"    1hit Accuracy: {data_1hit['accuracy']:.4f} ({data_1hit['accuracy']*100:.2f}%)")
        print(f"    5hit Accuracy: {data_5hit['accuracy']:.4f} ({data_5hit['accuracy']*100:.2f}%)")  # 新增
    
    # 按answer_type统计
    print(f"\nPerformance by Answer Type:")
    all_types = set(stats['by_answer_type_10hit'].keys()) | set(stats['by_answer_type_1hit'].keys()) | set(stats['by_answer_type_5hit'].keys())
    for answer_type in sorted(all_types):
        data_10hit = stats['by_answer_type_10hit'][answer_type]
        data_1hit = stats['by_answer_type_1hit'][answer_type]
        data_5hit = stats['by_answer_type_5hit'][answer_type]  # 新增
        print(f"  {answer_type}:")
        print(f"    Count: {data_10hit['count']}")
        print(f"    10hit Accuracy: {data_10hit['accuracy']:.4f} ({data_10hit['accuracy']*100:.2f}%)")
        print(f"    1hit Accuracy: {data_1hit['accuracy']:.4f} ({data_1hit['accuracy']*100:.2f}%)")
        print(f"    5hit Accuracy: {data_5hit['accuracy']:.4f} ({data_5hit['accuracy']*100:.2f}%)")  # 新增


def save_statistics(stats, output_dir):
    """保存统计信息到JSON文件"""
    stats_path = os.path.join(output_dir, "statistics.json")
    
    # 转换defaultdict为普通dict以便JSON序列化
    json_stats = {
        'overall_10hit': stats['overall_10hit'],
        'overall_1hit': stats['overall_1hit'],
        'overall_5hit': stats['overall_5hit'],  # 新增
        'by_qlabel_10hit': dict(stats['by_qlabel_10hit']),
        'by_qlabel_1hit': dict(stats['by_qlabel_1hit']),
        'by_qlabel_5hit': dict(stats['by_qlabel_5hit']),  # 新增
        'by_answer_type_10hit': dict(stats['by_answer_type_10hit']),
        'by_answer_type_1hit': dict(stats['by_answer_type_1hit']),
        'by_answer_type_5hit': dict(stats['by_answer_type_5hit']),  # 新增
        'answer1_extraction_stats': stats['answer1_extraction_stats'],
        'answers_1to5_extraction_stats': stats['answers_1to5_extraction_stats']  # 新增
    }
    
    with open(stats_path, 'w', encoding='utf-8') as f:
        json.dump(json_stats, f, indent=2, ensure_ascii=False)
    
    print(f"\nStatistics saved to: {stats_path}")


def main():
    parser = argparse.ArgumentParser(description="Evaluate GraphRAG results with semantic text matching and Hit5 support")
    parser.add_argument(
        "-result_path", 
        type=str, 
        required=True,
        help="Path to the result file (JSONL format)"
    )
    parser.add_argument(
        "-output_dir", 
        type=str, 
        default=None,
        help="Output directory for evaluation results (optional)"
    )
    
    args = parser.parse_args()
    
    # 创建输出目录
    if args.output_dir is None:
        result_dir = os.path.dirname(args.result_path)
        output_dir = os.path.join(result_dir, "evaluation_output")
    else:
        output_dir = args.output_dir
    
    os.makedirs(output_dir, exist_ok=True)
    
    # 设置输出路径
    evaluation_output_path = os.path.join(output_dir, "evaluation_result.json")
    
    try:
        # 处理结果文件
        evaluation_results = process_results(args.result_path, evaluation_output_path)
        
        # 生成统计信息
        stats = generate_statistics(evaluation_results)
        
        # 打印统计信息
        print_statistics(stats)
        
        # 保存统计信息
        save_statistics(stats, output_dir)
        
        print(f"\n✓ Evaluation completed successfully!")
        print(f"✓ Used semantic normalization (punctuation, abbreviations, synonyms)")
        print(f"✓ Added Hit5 evaluation (answer1-5 extraction matching)")
        print(f"✓ Evaluation results saved to: {evaluation_output_path}")
        
    except Exception as e:
        print(f"Error during evaluation: {e}")
        raise


if __name__ == "__main__":
    main()