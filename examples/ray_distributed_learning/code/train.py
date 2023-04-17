"""training script for ray"""
import ray

from training_scripts.algorithms import algorithm_from_name
from training_scripts.models import model_from_name
from training_scripts.utils import utils, argparser
from training_scripts.data import get_shape_and_classes


parser = argparser.get_argparser()
args, _ = parser.parse_known_args()

ray.init(runtime_env={"working_dir": "."})
# get model
model = model_from_name(args.model)(*get_shape_and_classes(args.dataset))
# get algorithm
algorithm = algorithm_from_name(args.algorithm)(model, args.dataset)
# set evaluation method
evaluation = utils.evaluate
# setup and initiliaze workers
algorithm.setup(args.num_workers, args.use_gpu)
# run algorithm
algorithm.run(args.iter, evaluation)
