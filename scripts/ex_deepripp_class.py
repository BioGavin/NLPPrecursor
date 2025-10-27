import argparse
import glob
import json
import os
from typing import List, Tuple

import pandas as pd

def get_json_file_pair(directory: str) -> List[Tuple[str, str]]:
    json_file_pair_ls = []
    class_pattern = os.path.join(directory, '*.class_predictions.json')
    class_json_paths = glob.glob(class_pattern)
    for class_json_path in class_json_paths:
        cleavage_json_path = class_json_path.replace('.class_predictions.json', '.cleavage_predictions.json')
        if os.path.exists(cleavage_json_path):
            json_file_pair_ls.append((class_json_path, cleavage_json_path))
    print(f"Found {len(json_file_pair_ls)} pairs of class and cleavage prediction files.")
    return json_file_pair_ls


def read_class_predictions(json_path: str) -> pd.DataFrame:
    base_file_name = os.path.basename(json_path).removesuffix('.class_predictions.json')
    
    # Load JSON content
    with open(json_path, 'r') as f:
        data = json.load(f)

    # Build records
    records = []
    for entry in data:
        orf_name = entry.get("name")
        for pred in entry.get("class_predictions", []):
            records.append({
                "file": base_file_name,
                "name": orf_name,
                "predicted_class": pred.get("class"),
                "score": pred.get("score")
            })

    # Convert to DataFrame
    df = pd.DataFrame(records)
    return df

def read_cleavage_predictions(json_path: str) -> pd.DataFrame:
    base_file_name = os.path.basename(json_path).removesuffix('.cleavage_predictions.json')
    
    # Load JSON content
    with open(json_path, 'r') as f:
        data = json.load(f)

    # Build records
    records = []
    for entry in data:
        orf_name = entry.get("name")
        cp = entry.get("cleavage_prediction", {})
        records.append({
            "file": base_file_name,
            "name": orf_name,
            "sequence": cp.get("sequence"),
            "start": cp.get("start"),
            "stop": cp.get("stop"),
            "score": cp.get("score"),
            "status": cp.get("status")
        })

    # Convert to DataFrame
    df = pd.DataFrame(records, columns=["file", "name", "sequence", "start", "stop", "score", "status"])
    return df



def consolidate_predictions(directory: str, output_csv: str) -> None:
    res_df = []
    json_file_pair = get_json_file_pair(directory=directory)
    for class_json, cleavage_json in json_file_pair:
        class_df = read_class_predictions(class_json)
        cleavage_df = read_cleavage_predictions(cleavage_json)
        # combine the two DataFrames
        combined_df = pd.merge(class_df, cleavage_df, on=["file", "name"], how="outer")
        res_df.append(combined_df)
    if not res_df:
        print("No DeepRiPP prediction pairs found. Skipping CSV export.")
        return
    # Concatenate all DataFrames into one
    res_df = pd.concat(res_df, ignore_index=True)
    # Save the combined DataFrame to a CSV file
    res_df.to_csv(output_csv, index=False)
    print(f"Saved combined predictions to {output_csv}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Combine DeepRiPP class and cleavage prediction JSON files into a CSV."
    )
    parser.add_argument(
        "deepripp_out_directory",
        help="Directory containing *.class_predictions.json and *.cleavage_predictions.json files.",
    )
    parser.add_argument(
        "output_csv",
        help="Path to the CSV file that will store the merged predictions.",
    )
    return parser.parse_args()


if __name__ == '__main__':
    args = parse_args()
    consolidate_predictions(args.deepripp_out_directory, args.output_csv)
        
    
