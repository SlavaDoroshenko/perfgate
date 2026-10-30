"""Summarize the first post-freeze CI pilot without changing its candidate policy."""
import argparse
import hashlib
import json
from pathlib import Path

import pandas as pd
from perfgate_analysis.compare import compare_frame, markdown
from perfgate_analysis.load import load_runs
from perfgate_analysis.power import injected_jobs, TARGET
from perfgate_analysis.quality import comparison_issues

ROOT = Path(__file__).resolve().parents[1]
p = argparse.ArgumentParser(description=__doc__)
p.add_argument('data', type=Path)
p.add_argument('--out', type=Path, required=True)
p.add_argument('--freeze', type=Path, default=ROOT/'docs/protocols/browser-candidate-2026-10-30.json')
args=p.parse_args();args.out.mkdir(parents=True,exist_ok=True)
freeze=json.loads(args.freeze.read_text())
mismatches=[name for name,digest in freeze['source_sha256'].items() if hashlib.sha256((ROOT/name).read_bytes()).hexdigest()!=digest]
if mismatches:raise SystemExit(f'Frozen sources changed: {mismatches}')
df=load_runs([args.data])
if df.empty or df.timestamp.min()<=pd.Timestamp(freeze['acquisition_after_utc']):raise SystemExit('Not an entirely post-freeze dataset')
cal=injected_jobs(df,include_invalid=True).groupby('experiment')[['kind','pct']].first()
rows=[];effects=[]
for exp,g in df.groupby('experiment'):
 issues=comparison_issues(g,('fcp','lcp','tbt','cls'),expected_runs=20,require_network=True)
 eligible=g['mode'].iloc[0]=='abab' and g.throttling.iloc[0]=='devtools'
 result=compare_frame(g,20) if eligible else None
 kind=cal.loc[exp,'kind'] if exp in cal.index else None
 target=TARGET.get(kind)
 fired=[m['name'].split('/')[-1] for m in result['metrics'] if m['regression']] if result else []
 target_row=next((m for m in result['metrics'] if m['name'].endswith('/'+target)),None) if result and target else None
 row={'experiment':exp,'app':g.app.iloc[0],'is_aa':bool(g.is_aa.iloc[0]),'kind':kind,
      'nominal_pct':float(cal.loc[exp,'pct']) if kind else None,'quality_valid':not issues,'issues':'; '.join(issues),
      'mode':g['mode'].iloc[0],'throttling':g.throttling.iloc[0],
      'status':result['status'] if result else 'outside_candidate_protocol',
      'target_detected':target in fired if target else None,'flagged_metrics':';'.join(fired),
      'target_relative_effect':target_row['relative_effect'] if target_row else None,
      'target_absolute_effect':target_row['absolute_effect'] if target_row else None,
      'measurement_and_warmup_seconds':(g.duration_ms.sum()+g.warmup_duration_ms.iloc[0])/1000}
 rows.append(row)
 if result:
  for m in result['metrics']:effects.append({'experiment':exp,**m})
aa=df[df.is_aa & (df['mode']=='abab') & (df.throttling=='devtools')]
if set(aa.app)!={'demo-spa','demo-heavy','demo-static','demo-ssr'}:raise SystemExit('Four-page A/A suite missing')
suite=compare_frame(aa,20)
(args.out/'aa-suite.json').write_text(json.dumps(suite,indent=2,allow_nan=False)+'\n')
(args.out/'aa-suite.md').write_text(markdown(suite))
r=pd.DataFrame(rows);r.to_csv(args.out/'jobs.csv',index=False)
pd.DataFrame(effects).to_csv(args.out/'metrics.csv',index=False)
manifest={'policy':freeze['policy'],'freeze_sha256':hashlib.sha256(args.freeze.read_bytes()).hexdigest(),
          'data_from':str(df.timestamp.min()),'data_through':str(df.timestamp.max()),'loads':len(df),
          'jobs':int(df.experiment.nunique()),'invalid_jobs':int((~r.quality_valid).sum()),
          'failed_loads':int((~df.ok).sum()),'aa_suite_status':suite['status'],
          'source_matches_freeze':True,'interpretation':'first post-freeze pilot, not completed confirmatory sample',
          'files_sha256':{str(f.relative_to(args.data)):hashlib.sha256(f.read_bytes()).hexdigest() for f in sorted(args.data.rglob('*.jsonl'))}}
(args.out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
print(json.dumps({k:v for k,v in manifest.items() if k!='files_sha256'},indent=2))
print(r[r.kind.notna()][['kind','nominal_pct','status','target_detected','target_relative_effect']].to_string(index=False))
