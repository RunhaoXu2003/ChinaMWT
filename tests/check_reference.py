"""Public, patient-free parity checks against exported frozen R predictions."""
from pathlib import Path
import csv
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from core.reference import ReferenceModel


def main():
    model = ReferenceModel()
    maximum = dict(mu=0.0, limit=0.0, z=0.0)
    n = 0
    with (ROOT / 'reference/reference_parity_cases.csv').open(encoding='utf-8-sig', newline='') as stream:
        for row in csv.DictReader(stream):
            mu, sigma, q = model.predict(row['sex'], float(row['age']), float(row['bsa']))
            values = dict(mu=mu, limit=mu + sigma * q, z=(float(row['mwt']) - mu) / sigma)
            for key, value in values.items():
                error = abs(value - float(row[key]))
                maximum[key] = max(maximum[key], error)
                assert error < 1e-9, (n, key, error)
            n += 1
    assert n == 778
    for sex in ['Male', 'Female']:
        result = model.evaluate(10, sex, 50, 165, 60)
        limit = result['upper_limit_mm']
        assert model.evaluate(limit, sex, 50, 165, 60)['above_limit']
        assert not model.evaluate(limit - 1e-8, sex, 50, 165, 60)['above_limit']
    output = dict(status='PASS', queries=n, maximum_absolute_error=maximum, boundary_checks=4,
                  scope='Deterministic reference-calculation checks, not clinical validation.')
    (ROOT / 'qa').mkdir(exist_ok=True)
    (ROOT / 'qa/public_reference_check.json').write_text(json.dumps(output, indent=2), encoding='utf-8')
    print(json.dumps(output, indent=2))


if __name__ == '__main__':
    main()
