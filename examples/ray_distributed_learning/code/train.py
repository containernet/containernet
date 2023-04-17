"""training script for ray"""
import time

import ray

from training_scripts.algorithms import algorithm_from_name
from training_scripts.models import model_from_name
from training_scripts.utils import utils, argparser, log_manager
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
algorithm.setup(args.num_workers, args.use_gpu, args.lr)
# run algorithm
start_time = time.perf_counter()
algorithm.run(args.iter, evaluation)
elapsed_time = time.perf_counter() - start_time
# log results
log_manager.update("train_time", elapsed_time)
log_manager.update("learning_rate", args.lr)
log_manager.update("training_algorithm", args.algorithm)
log_manager.update("dataset", args.dataset)
log_manager.update("gpu_training", args.use_gpu)
log_manager.update("iterations", args.iter)
log_manager.save()
