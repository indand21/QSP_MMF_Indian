import os
P=os.path.join(os.path.dirname(__file__),'generate_updated_manuscript_docx.py')
s=open(P,encoding='utf-8').read()

# Source string literals contain literal \uXXXX escape TEXT. Match with '\\uXXXX'
# (one backslash + uXXXX) using ASCII-only normal strings.
M='\\u2212'; D='\\u2014'; A='\\u2248'; PM='\\u00b1'  # minus, em-dash, approx, plus-minus
edits=[
 # --- Discussion paragraph 119 ---
 ('These findings have direct clinical implications: the higher variability',
  'These findings have direct clinical implications. The higher variability'),
 (M+'2152C>T'+D+'which increase', M+'2152C>T, which increase'),
 ('[23]'+D+'are essentially', '[23] are essentially'),
 ('and 0% in East Asians [11,22,24]). The reduced-activity',
  'and 0% in East Asians [11,19,24]). The reduced-activity'),
 (A+'1.4% in Europeans [24]). Consequently', A+'1.4% in Europeans [19]). Consequently'),
 ('intronic UGT1A9 I399C>T variant'+D, 'intronic UGT1A9 I399C>T variant, which is '),
 ('Japanese renal transplant recipients [22]'+D, 'Japanese renal transplant recipients [24], '),
 ('and '+A+'3% in East Asians [24]), although', 'and '+A+'3% in East Asians [19]), although'),
 # --- Conclusions ---
 ('design isolates body weight (and assumed UGT pharmacogenomic variation) as the remaining',
  'design isolates body weight and the UGT pharmacogenomic variation as the remaining'),
 ('between Western and Indian cohorts; within that design, body weight ',
  'between Western and Indian cohorts. '),
 ('emerges as the dominant modifiable determinant. At standard', 'At standard'),
 ('therapeutic AUC window [1,3], with', 'therapeutic AUC window, with'),
 ('robust to '+PM+'20% parameter perturbation (Figure S1), ',
  'robust to '+PM+'20% parameter perturbation, '),
 ('provide mechanistic justification for prospective',
  'provide a mechanistic justification for prospective'),
 ('in Indian and other low-weight transplant populations [4,5,6].',
  'in Indian and other low-weight transplant populations.'),
]
for old,new in edits:
    c=s.count(old)
    assert c==1, f'FAIL count={c} for: {old[:55]!r}'
    s=s.replace(old,new)
open(P,'w',encoding='utf-8').write(s)
print('generator Disc119 + Conclusions synced (%d edits)'%len(edits))
