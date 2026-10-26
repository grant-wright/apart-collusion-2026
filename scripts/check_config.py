"""Offline check: does Colosseum build a client from one of our configs? NO API call is made.
Run from the colosseum folder:  .venv\Scripts\python.exe <this file> <config yaml path>
"""
import sys
import yaml
from terrarium import utils

cfg = yaml.safe_load(open(sys.argv[1]))
for entry in cfg["llm_models"]:
    llm = entry["llm"]
    provider = llm["provider"]
    client = utils.get_client_instance(llm)
    print(f"{entry['label']}: provider={provider} client={type(client).__name__} "
          f"model={utils.get_model_name(provider, llm)} params={utils.get_generation_params(llm)}")
sweep = cfg["experiment"]["sweeps"][0]
print("seeds:", cfg["experiment"]["seeds"], "| environments:", [e["label"] for e in sweep["environments"]],
      "| secret_channel:", sweep["secret_channel_enabled"], "| prompt_variants:", sweep["prompt_variants"])
runs = (len(cfg["experiment"]["seeds"]) * len(sweep["environments"]) * len(sweep["topologies"])
        * len(sweep["num_agents"]) * len(sweep["colluder_counts"]) * len(cfg["llm_models"]))
print("rough run count (before secret/variant combos):", runs)
