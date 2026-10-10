# Copilote de crise Enedis — Hackathon IA for Impact 2026 (La Mêlée)

Démonstrateur d'aide à la décision pour **placer et affecter les équipes d'intervention** pendant une crise climatique,
afin de **minimiser Σ clients × heures de coupure**, en **sécurité** et avec des décisions **explicables**.
L'outil recommande, le responsable métier décide.

> Plan d'équipe, contrats d'interface, tâches et planning : [`docs/PLAN_EQUIPE_DEFI_ENEDIS.md`](docs/PLAN_EQUIPE_DEFI_ENEDIS.md)

## Installation (≈ 10 min)

Prérequis : Python 3.11+ et git. 100 % open source, CPU seulement.

```bash
git clone https://github.com/<compte>/enedis-crise-copilote.git
cd enedis-crise-copilote
python -m venv .venv
# Windows (PowerShell) : .venv\Scripts\Activate.ps1      macOS / Linux : source .venv/bin/activate
pip install -r requirements.txt
pytest -q                      # doit afficher "passed"
```

Déposer les fichiers fournis par Enedis dans `data/raw/` (ils ne sont **pas** versionnés) :
`agents_v2.csv`, `poste_v2.csv`, `insee_v2.csv`, `coupures_v2_100_crises.csv` (noms exacts).

## Exécution

```bash
python -m crise.data.nettoyage      # données propres → data/clean/*.parquet
streamlit run app/Accueil.py        # salle de crise
```

Copilote IA (P5 seulement) : installer [Ollama](https://ollama.com) puis `ollama pull qwen2.5:3b`.

## Organisation

| Lot | Propriétaire | Dossiers |
|---|---|---|
| 1 · Données & simulateur | P1 | `src/crise/data`, `models.py`, `trajet.py`, `simulateur.py`, `policies/base.py`, `policies/baselines.py` |
| 2 · Optimisation & explicabilité | P2 | `policies/wspt_hongrois.py`, `explication.py` |
| 3 · Évaluation & robustesse | P3 | `kpi.py`, `prepositionnement.py`, `benchmark.py`, `scenarios.py` |
| 4 · Interface | P4 | `app/` |
| 5 · Copilote, doc, pitch | P5 | `src/crise/copilote`, `README.md`, `docs/` |

Règles git : une branche par lot (`lot1-simu`, `lot2-optim`, `lot3-eval`, `lot4-ui`, `lot5-ia-doc`),
chacun ne modifie que ses fichiers, fusion dans `main` aux points de synchronisation après `ruff check .` et `pytest`.

## Hypothèses, limites, résultats

À compléter (T5.5) — voir plan §9.
