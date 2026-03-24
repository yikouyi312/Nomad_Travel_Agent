import json
import os
from datetime import datetime


def save_experiment_result(
    task_id, agent_type, itinerary, logs, results, file_path="data/experiments.json"
):
    # Create the data structure
    entry = {
        "timestamp": datetime.now().isoformat(),
        "task_id": task_id,
        "agent_type": agent_type,  # "DirectBaseline" or "SerpAgent"
        "itinerary": itinerary,
        "tool_logs": logs,
        "metrics": {"csr": results["csr"], "tool_accuracy": results["tool_accuracy"]},
    }

    # Load existing and append
    data = []
    if os.path.exists(file_path):
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)

    data.append(entry)

    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)


def save_as_markdown(task_id, agent_type, itinerary):
    directory = f"outputs/{agent_type}"
    os.makedirs(directory, exist_ok=True)

    filename = f"{directory}/{task_id}.md"
    with open(filename, "w", encoding="utf-8") as f:
        f.write(f"# Benchmark Result: {task_id}\n")
        f.write(f"**Agent Type:** {agent_type}\n\n")
        f.write("## Generated Itinerary\n")
        f.write(itinerary)  # 这里的 itinerary 已经是 Markdown 格式了
