# QuantStone Data

QuantStone Data is an open-source system for registering, collecting, validating, storing, and querying financial datasets.

The project manages supplier-defined datasets without forcing different suppliers into a shared business schema. Each dataset has an explicit contract covering its fields, collection behavior, validation rules, storage policy, and schema version.

## Current focus

The first milestone is the Dataset Registry and the end-to-end lifecycle of one dataset:

1. Register a dataset and its fields.
2. Create an initial or incremental collection plan.
3. Collect data into a staging area.
4. Validate it against the dataset contract.
5. Publish files and update the catalog.

## Dataset IDs

Dataset IDs follow this structure:

```text
<provider>.<region>.<instrument>.<dataset>[.<market>]
```

Examples:

```text
tushare.cn.stock.daily
tb_l2.cn.stock.l2_order.sh
tb_l2.cn.stock.l2_trade.sz
```

See [docs/dataset-id.md](docs/dataset-id.md) for the naming rules.

## Development

```bash
python -m venv .venv
python -m pip install -e ".[dev]"
uvicorn quantstone_data.main:app --reload
```

The API is available at `http://127.0.0.1:8000`, with interactive documentation at
`http://127.0.0.1:8000/docs`.

Run tests with:

```bash
pytest
```

## Current API

```text
POST   /api/v1/datasets
GET    /api/v1/datasets
GET    /api/v1/datasets/{dataset_id}
POST   /api/v1/datasets/{dataset_id}/activate
DELETE /api/v1/datasets/{dataset_id}
GET    /health
```

## Status

Early design and bootstrap stage.

## License

MIT License.
