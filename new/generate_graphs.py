import os
import json
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

def generate_graphs(reports_dir="."):
    data = []
    for filename in os.listdir(reports_dir):
        if filename.startswith("report_") and filename.endswith(".json"):
            filepath = os.path.join(reports_dir, filename)
            with open(filepath, "r", encoding="utf-8") as f:
                try:
                    report = json.load(f)
                    data.append({
                        "Platform": report.get("platform_detected", "Unknown"),
                        "CLIP_Score": report.get("step3_analysis_results", {}).get("clip_friction_score", 0),
                        "Status": report.get("step3_analysis_results", {}).get("status", "FAILED")
                    })
                except Exception as e:
                    print(f"Error reading {filename}: {e}")
    
    if not data:
        print("No JSON reports found in the directory to generate graphs.")
        return

    df = pd.DataFrame(data)

    sns.set_theme(style="whitegrid")
    plt.figure(figsize=(12, 5))

    plt.subplot(1, 2, 1)
    sns.countplot(data=df, x="Platform", palette="viridis")
    plt.title("Posts Scanned per Platform")
    plt.ylabel("Count")

    plt.subplot(1, 2, 2)
    sns.histplot(data=df, x="CLIP_Score", bins=10, kde=True, color="coral")
    plt.title("Distribution of CLIP Scores")
    plt.xlabel("CLIP Score")
    plt.ylabel("Frequency")

    plt.tight_layout()
    
    plt.savefig("statistics_dashboard.png")
    print("✅ Statistical graphs saved successfully as 'statistics_dashboard.png'!")
    plt.show()

if __name__ == "__main__":
    generate_graphs()