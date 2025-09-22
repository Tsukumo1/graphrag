# GraphRAG Setup and Usage Guide

## Configuration

### 1. Update Configuration File

修改 `GraphRAG/Option/Config2.yaml` 文件中的以下配置项：

- `data_root`: 设置数据根目录路径
- `working_dir`: 设置工作目录路径

```yaml
data_root: /path/to/your/data
working_dir: /path/to/your/working/directory
```

### 2. Data File Naming Convention

确保目录下的数据文件命名统一：

- 训练数据文件：`train.txt`
- 训练配置文件：`train.json`

## Usage

### 1. Start OpenLLM Service

首先启动 OpenLLM 服务：

```bash
openllm serve llama3.1:8b --port 6578
```

### 2. Run GraphRAG

在后台运行 GraphRAG 程序：

```bash
python main.py -opt Option/Method/MedG.yaml -dataset_name CronKGQA
```

### 参数说明

- `-opt Option/Method/MedG.yaml`: 指定方法配置文件
- `-dataset_name CronKGQA`: 指定数据集名称

## File Structure

```
GraphRAG/
├── Option/
│   ├── Config2.yaml          # 主配置文件
│   └── Method/
│       └── MedG.yaml         # 方法配置文件
├── data/
│   ├── train.txt             # 训练数据文件
│   └── train.json            # 训练配置文件
├── main.py                   # 主程序入口
└── log.txt                   # 运行日志文件
```

## Notes

- 确保在运行 main.py 之前 OpenLLM 服务已经启动并正常运行
- 检查端口 6578 是否被占用
- 运行过程中可以通过 `tail -f log.txt` 查看实时日志
- 使用 `ps aux | grep python` 检查程序是否在后台正常运行
