#! /usr/bin/env python3
import argparse
import os.path

from Bio import SeqIO

from torch.utils.data import Dataset, DataLoader
import time
import json
import multiprocessing as mp
import numpy as np
from nlpprecursor.classification.data import DatasetGenerator as CDG
from nlpprecursor.annotation.data import DatasetGenerator as ADG
from pathlib import Path
import nlpprecursor
import sys


def gen_intput_data(input_fna):
    """读取fna文件，并返回序列记录"""
    orfs = []
    for record in SeqIO.parse(input_fna, "fasta"):
        name = record.name
        sequence = str(record.seq).strip("*")
        orfs.append({"sequence": sequence, "name": name})
    print(f"输入{len(orfs)}条序列")
    return orfs


# def split_to_batches(lst, batch_size):
#     return [lst[i:i + batch_size] for i in range(0, len(lst), batch_size)]


def save_result(result_data, output_json):
    with open(output_json, 'w') as f:
        json.dump(result_data, f)


def help():
    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
    usage: ./predict.py -i input.faa -o1 class_predictions.json -o2 cleavage_predictions.json
            '''
    )

    parser.add_argument('-i', '--input', required=True, type=str, help='Input CDS fasta.')
    parser.add_argument('-o1', '--output_class_predictions', required=True, type=str, help='Class prediction output.')
    parser.add_argument('-o2', '--output_cleavage_predictions', required=True, type=str,
                        help='Cleavage prediction output.')

    args = parser.parse_args()
    return args


if __name__ == '__main__':
    args = help()

    start_time = time.time()
    orfs = gen_intput_data(args.input)

    # This allows for backwards compatibility of the pickled models.
    sys.modules["protai"] = nlpprecursor

    models_dir = Path("./models")  # downloaded from releases!

    class_model_dir = os.path.join(models_dir, "classification")
    class_model_path = os.path.join(class_model_dir, "model.p")
    class_vocab_path = os.path.join(class_model_dir, "vocab.pkl")
    annot_model_dir = os.path.join(models_dir, "annotation")
    annot_model_path = os.path.join(annot_model_dir, "model.p")
    annot_vocab_path = os.path.join(annot_model_dir, "vocab.pkl")

    # sequences = [
    #     {
    #         "sequence": "MTYERPTLSKAGGFRKTTGLAGGTAKDLLGGHQLI",
    #         "name": "unique_name",
    #     },
    #     {
    #         "sequence": "MTYERPTLSKAGGFRKTTGLAGGTAKDLLGGHQLI",
    #         "name": "unique_name",
    #     }
    # ]

    class_predictions = CDG.predict(class_model_path, class_vocab_path, orfs)
    cleavage_predictions = ADG.predict(annot_model_path, annot_vocab_path, orfs)
    save_result(class_predictions, args.output_class_predictions)
    save_result(cleavage_predictions, args.output_cleavage_predictions)

    print(f"Elapsed time: {time.time() - start_time} seconds")
