# Shift File

Depot desk for Hayes Cartage, a London cargo-bike operator. One ride camera, three slips: file it, have a word, or leave it.

The New York GoPro (`nyc_bike_gopro-1`) stands in for the bike camera.

Secrets stay in the environment: `VSS_URL`, `VSS_USERNAME`, `VSS_PASSWORD`, `WANDB_API_KEY`, `WANDB_TEAM`, `WANDB_PROJECT`. Optional `WANDB_MODEL`.

`main.py` listens on `0.0.0.0:$PORT`. Routes are `/` and `/health`. The lab ingress serves them under `/app`.
