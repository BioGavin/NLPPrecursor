
# NLPPrecursor


NLPPrecursor is a deep learning framework that analyses protein sequences and predicts their RiPP biosynthetic family along
with a possible cleavage site allowing for the rapid discovery of RiPPs in genomic data. NLPPrecursor fits best with a tool
such as [PRODIGAL](https://github.com/hyattpd/Prodigal), but any ORF finder should suffice.

NLPPrecursor is freely available for use on the DeepRiPP website: <http://deepripp.magarveylab.ca>. The following repository
demonstrates how to use NLPPrecursor in a programatic manner on your own hardware. Caution, this does require you to be comfortable
with Python!


## Installation

NLPPrecursor works with python 3.7+ and needs two main requirements: PyTorch and FastAI.

Install pytorch according to your GPU/CPU preference here: <https://pytorch.org>


The project is not currently being developed, thus maintaining the installation process can be tricky given the number of dependencies. Fastai used to use the nightly release of pytorch and torchvision, but these are no longer compatible. A branch that is compatible with this library has been forked, which will need to be installed.

Conda is highly recommended, create a new environment specifically for NLPPrecursor for the easiest build.
For example, here is one way to set this up:
```bash
conda create --name deepripp python=3.7
conda activate deepripp
pip install git+https://github.com/nishanthmerwin/fastai.git@deepripp_install
pip install git+https://github.com/magarveylab/nlpprecursor
```

## Example usage for prediction

Current models are available through our [releases](https://github.com/magarveylab/nlpprecursor/releases).

To use them in your analysis, use the following code:


```python

from nlpprecursor.classification.data import DatasetGenerator as CDG
from nlpprecursor.annotation.data import DatasetGenerator as ADG
from pathlib import Path
import nlpprecursor
import sys
# This allows for backwards compatibility of the pickled models.
sys.modules["protai"] = nlpprecursor

models_dir = Path("../models") # downloaded from releases! 

class_model_dir = models_dir / "classification"
class_model_path = class_model_dir / "model.p"
class_vocab_path = class_model_dir / "vocab.pkl"
annot_model_dir = models_dir / "annotation"
annot_model_path = annot_model_dir / "model.p"
annot_vocab_path = annot_model_dir / "vocab.pkl"

sequences = [
    {
        "sequence": "MTYERPTLSKAGGFRKTTGLAGGTAKDLLGGHQLI",
        "name": "unique_name",
    }
]

class_predictions = CDG.predict(class_model_path, class_vocab_path, sequences)
cleavage_predictions = ADG.predict(annot_model_path, annot_vocab_path, sequences)

import json
print("Class predictions")
print(json.dumps(class_predictions, indent=4))

print("Cleavage predictions")
print(json.dumps(cleavage_predictions, indent=4))
```


Output: 
```json
Class predictions
[
    {
        "class_predictions": [
            {
                "class": "LASSO_PEPTIDE",
                "score": 0.9999966621398926
            }
        ],
        "name": "unique_name"
    }
]
Cleavage predictions
[
    {
        "name": "unique_name",
        "cleavage_prediction": {
            "sequence": "LAGGTAKDLLGGHQLI",
            "start": 19,
            "stop": 35,
            "score": -19735.994140625,
            "name": "unique_name",
            "status": "success"
        }
    }
]
```



## Usage (from Wlab)

```bash
# 查看帮助信息
./scripts/predict.py -h
# 使用方法
./scripts/predict.py -i input.faa -o1 class_predictions.json -o2 cleavage_predictions.json
```





## Example training

All training data to build the above models is available through this repo under `training_data`. Training
largely happens in two steps, first the classification model and second the cleavage (also called annotation) model.

In both cases, the training data is randomly stratified into training, validation and test data. During training,
you will see up to date stats based on the validation set loss. And at the end, the model will be evaluated against
the test data set and results will be output into the data_path directory.


#### Classification
The cleavage model is simple to train, and usually takes ~8 hours on a 4 core computer, 8gb of RAM and a K80 NVidia GPU.

```python
from nlpprecursor.classification.data import DatasetGenerator
from pathlib import Path
import json


def train_opt(lm_json, class_json, data_path):
    dg = DatasetGenerator(0.9, lm_json, class_json, data_path, bs=2)
    print(dg.stage)
    dg._read_jsons()
    dg.stage += 1
    print(dg.stage)

    dg.tokenize()
    dg.stage += 1
    print(dg.stage)

    dg.split_class_data()
    dg.stage += 1
    print(dg.stage)

    dg.train_lm(epochs=1)
    dg.stage +=1
    print(dg.stage)

    dg.train_class(epochs=1)

	dg.test_class()


if __name__ == "__main__":
	data_path = Path("./training_data/classification")
    lm_json = data_path / "lm_data.json"
    class_json = data_path / "class_data.json"
    train_opt(lm_json, class_json, data_path)

```



#### Cleavage (annotation)

To train the cleavage model, use the following logic to input any train or update the models.

```python

from nlpprecursor.annotation.data import DatasetGenerator
import pickle
import json

def train(data_path, json_path):
	# Train split percent
	# Training data path
	# Save directory
	# Batch size
    dg = DatasetGenerator(0.9, json_path, data_path, bs=5)
    dg.run(1) # Number of epochs


def test(data_path, raw_data_path):

    data_path = Path(data_path)
    model_path = data_path / "model.p"
    vocab_path = data_path / "vocab.pkl"
    datasplit_path = data_path / "datasplit.json"

    results = DatasetGenerator.evaluate_later(model_path, vocab_path, datasplit_path, raw_data_path)
    outpath = Path(data_path) / "tested.json"
    with outpath.open("w") as fp:
        json.dump(results, fp)

def predict(data_path, sequences):
    data_path = Path(data_path)
    model_path = data_path / "model.p"
    vocab_path = data_path / "vocab.pkl"


if __name__ == "__main__":

    data_path = "./training_data/annotation"
	json_path = data_path + "/all_props.json"

    train(data_path, json_path)
	test(data_path, json_path)

```







