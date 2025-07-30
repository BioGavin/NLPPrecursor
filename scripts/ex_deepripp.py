#! /usr/bin/env python3

import argparse
import os
import json
from Bio.Seq import Seq
from Bio.SeqRecord import SeqRecord
from Bio import SeqIO
import pandas as pd


def ex_class_json(class_json, score_threshold):
    with open(class_json) as f:
        data = json.load(f)
    rt_data = []
    for item in data:
        name = item['name']
        class_predictions = item['class_predictions']
        if len(class_predictions) == 1:
            cls = class_predictions[0]
            if cls['class'] != "NONRIPP":
                if cls['score'] >= score_threshold:
                    cls['name'] = name
                    rt_data.append(cls)
        else:
            for cls in class_predictions:
                if cls['class'] != "NONRIPP":
                    if cls['score'] >= score_threshold:
                        cls['name'] = name
                        rt_data.append(cls)
    return rt_data


def ex_core_peptide(cleavage_json, pos_data):
    with open(cleavage_json) as f:
        data = json.load(f)

    cleavage_df = pd.DataFrame(data)
    pos_df = pd.DataFrame(pos_data)
    pos_merge_df = pd.merge(left=pos_df, right=cleavage_df)
    pos_merge_df['sequence'] = pos_merge_df['cleavage_prediction'].apply(lambda x: x.get('sequence'))
    pos_merge_df.drop(columns=["cleavage_prediction"], inplace=True)
    return pos_merge_df


def save_result(result_df, output_tsv, output_faa):
    # 保存 tsv 文件
    result_df.to_csv(output_tsv, sep='\t', index=False)

    # 保存 fasta 文件
    # 创建一个空列表来保存SeqRecord对象
    records = []

    # 遍历DataFrame的每一行
    for _, row in result_df.iterrows():
        # 创建一个SeqRecord对象
        record = SeqRecord(Seq(row['sequence']),
                           id=row['name'],
                           description=row['class'])
        # 添加到列表中
        records.append(record)

    # 使用SeqIO.write函数将SeqRecord列表写入fasta文件
    SeqIO.write(records, output_faa, 'fasta')


def help():
    def score_threshold_type(value):
        try:
            threshold = float(value)
            if 0 <= threshold <= 1:
                return threshold
            else:
                raise argparse.ArgumentTypeError(f"Threshold must be between 0 and 1.")
        except ValueError:
            raise argparse.ArgumentTypeError(f"Invalid threshold value: {value}")

    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
  examples:
  python ex_deepripp.py -i1 class.json -i2 cleavage.json -s 0.8 -o deepripp_pos
            '''
    )

    parser.add_argument('-i1', '--input_class_json', required=True, type=str,
                        help='Class json file output from deepripp analysis.')
    parser.add_argument('-i2', '--input_cleavage_json', required=True, type=str,
                        help='Cleavage json file output from deepripp analysis.')
    parser.add_argument('-o', '--output_folder', required=True, type=str, default='.',
                        help='Output folder paths.')
    parser.add_argument('-s', '--score_threshold', required=False, default=0,
                        type=score_threshold_type,
                        help='Score threshold for class predictions in the class json file.')

    args = parser.parse_args()
    return args


if __name__ == '__main__':
    args = help()

    # 如果用户没有提供 -o 参数，则 output_folder 的值将是当前路径
    if args.output_folder == '.':
        output_folder = os.getcwd()
    else:
        output_folder = args.output_folder

    if not os.path.exists(output_folder):
        # 如果文件夹不存在，创建它
        os.mkdir(output_folder)

    pos_date = ex_class_json(args.input_class_json, args.score_threshold)
    res_df = ex_core_peptide(args.input_cleavage_json, pos_date)

    save_result(res_df, os.path.join(output_folder, "deepripp_pos.tsv"),
                os.path.join(output_folder, "deepripp_pos.faa"))


