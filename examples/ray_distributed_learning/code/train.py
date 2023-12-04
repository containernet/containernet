"""training script for ray"""
import time

import ray

from training_scripts.algorithms import algorithm_from_name
from training_scripts.models import model_from_name
from training_scripts.utils import utils, argparser, log_manager
from training_scripts.data import get_classes_and_shape


parser = argparser.get_argparser()
args, _ = parser.parse_known_args()

ray.init(runtime_env={"working_dir": "."})
# get model
model = model_from_name(args.model)(*get_classes_and_shape(args.dataset))
# get algorithm
algorithm = algorithm_from_name(args.algorithm)(model, args.dataset)
# set evaluation method
evaluation = utils.evaluate
# setup and initiliaze workers
algorithm.setup(args.num_workers, not args.use_cpu, args.lr, args.batch_size)
# run algorithm
start_time = time.perf_counter()
algorithm.run(args.epochs, evaluation)
elapsed_time = time.perf_counter() - start_time
# log results
log_manager.update("training_time", elapsed_time)
log_manager.update("learning_rate", args.lr)
log_manager.update("training_algorithm", args.algorithm)
log_manager.update("dataset", args.dataset)
log_manager.update("gpu_training", not args.use_cpu)
log_manager.update("epochs", args.epochs)
log_manager.save()
