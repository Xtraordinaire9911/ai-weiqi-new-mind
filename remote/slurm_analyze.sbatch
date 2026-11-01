#!/bin/bash
# Slurm batch template: run analyze_remote.py on a GPU node of a university cluster / supercomputer (the KataGo analysis engine needs just 1 GPU).
# !! This is a template and has not been run on a real LRZ system: partition names, container images, and whether compute nodes have internet access differ per cluster, so read your cluster's documentation first.
#
# How LRZ AI Systems works (official docs: https://doku.lrz.de/ai-systems-11484278.html):
#   - You need an LRZ account AND membership in a project with AI Systems enabled before you can ssh to login.ai.lrz.de (from inside the Munich Scientific Network MWN or over VPN)
#   - Batch jobs are the preferred way to work; software normally goes into an Enroot container (NGC images)
#   - Compute nodes often cannot reach the internet directly => on the login node, run setup_katago.py first to download KataGo and the weights, and let the job read local files only
#
# Usage:
#   1) On the login node:  python3 setup_katago.py --dir $HOME/katago_env --model /path/to/kata1-tf3-b11c768-s12752M-d6531M.bin.gz
#   2) Upload the input:   scp g_*.n.json  <user>@login.ai.lrz.de:~/josekiapp/in/
#   3) Submit:             sbatch slurm_analyze.sbatch          (edit the #SBATCH lines below as needed)
#   4) Fetch the results:  scp '<user>@login.ai.lrz.de:~/josekiapp/out/g_*.a2.json' .
#
#SBATCH --job-name=katago-a2
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=8
#SBATCH --mem=24G
#SBATCH --time=04:00:00
#SBATCH --output=katago-a2-%j.log
##SBATCH --partition=lrz-v100x2        # <- uncomment and replace with a GPU partition of your cluster (see sinfo)

set -euo pipefail
ROOT=${ROOT:-$HOME/josekiapp}
ENV=${ENV:-$HOME/katago_env}
mkdir -p "$ROOT/out"

# If the cluster provides CUDA/cuDNN through environment modules, load them here (names differ per cluster):
# module load cuda cudnn

source "$ENV/env.sh"          # sets LD_LIBRARY_PATH / KATAGO_BIN / KATAGO_MODEL
nvidia-smi || true

# To run inside a container, change the python3 line below to:
#   srun --container-image=nvcr.io#nvidia/cuda:12.8.0-cudnn-runtime-ubuntu22.04 --container-mounts=$ROOT:$ROOT,$ENV:$ENV ...
python3 -u "$ROOT/analyze_remote.py" \
    --in "$ROOT/in" --out "$ROOT/out" \
    --katago "$KATAGO_BIN" --model "$KATAGO_MODEL" \
    --visits 220 --forced 100 --threads 2 --search-threads 16 --batch 64
# Resume: after a timeout or preemption just submit the job again; finished groups are skipped automatically.
