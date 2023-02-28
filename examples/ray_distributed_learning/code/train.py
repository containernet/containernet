"""training script for ray"""
import ray

from training_scripts.algorithms import algorithm_from_name
from training_scripts.models import model_from_name
from training_scripts.utils import utils, argparser
from training_scripts.data import data


parser = argparser.get_argparser()
args, _ = parser.parse_known_args()

ray.init(runtime_env={"working_dir": "."})
# load model
model = model_from_name(args.model)()
# load data_loaders
data_loader = data.get_data_loader(args.dataset)
# load algorithm
algorithm = algorithm_from_name(args.algorithm)(model, data_loader)
# set evaluation method
evaluation = utils.evaluate
# setup and initiliaze workers
algorithm.setup(args.num_workers)
# run algorithm
algorithm.run(args.iter, evaluation)
