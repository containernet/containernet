import argparse
import ray

from algorithms import algorithm_from_name
from models import model_from_name
from utils import argparser.get_argparser
from utils.utils import evaluate
from data.data import get_data_loader


parser = get_argparser()
args, _ = parser.parse_known_args()

ray.init(runtime_env={"working_dir": "."})
# load model
model = model_from_name(args.model)()
# load data_loaders
data_loader = get_data_loader(args.dataset)
# load algorithm
algorithm = algorithm_from_name(args.algorithm)(model, data_loader)
# set evaluation method
evaluation = evaluate
# setup and initiliaze workers
algorithm.setup(args.num_workers)
# run algorithm

algorithm.run(args.iter, evaluation)
