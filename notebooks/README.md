# Notebooks

`00_validate_reporting_dataset.ipynb` is a new, runnable quality-control notebook
for the supplied final CSV. It does not perform industry recovery or modeling.

The original notebooks are still needed. After review, arrange them by execution
order: industry recovery, ML validation, and reporting export. Move reusable logic
to `src/data_processing` and `src/modeling`; keep notebooks focused on orchestration
and analytical explanation. Pin actual dependencies after inspecting the source.
