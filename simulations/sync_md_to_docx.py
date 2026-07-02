# Sync MPA_QSP_Manuscript_Updated.md to the manually-updated authoritative docx.
import re, os
HERE = os.path.join(os.path.dirname(__file__), '..', 'outputs', 'manuscript_updated')
PATH = os.path.join(HERE, 'MPA_QSP_Manuscript_Updated.md')

# old(md) -> new(docx) reference numbering
MAP = {19: 20, 20: 21, 21: 22, 22: 24, 23: 23, 24: 19}

def remap_cites(s):
    """Remap only citations that reference a number >=19; leave others verbatim."""
    def rep(m):
        nums = []
        for c in m.group(1).replace('–', '-').split(','):
            c = c.strip()
            if '-' in c:
                lo, hi = c.split('-'); nums += list(range(int(lo), int(hi) + 1))
            elif c:
                nums.append(int(c))
        if not any(n >= 19 for n in nums):
            return m.group(0)
        mapped = sorted(set(MAP.get(n, n) for n in nums))
        return '[' + ', '.join(map(str, mapped)) + ']'
    return re.sub(r'\[([\d,\s–-]+)\]', rep, s)

# --- docx-final text for the two wholesale-replaced paragraphs ---
CONCL = ("This PBPK/PD analysis quantifies the contribution of body weight to MPA overexposure in "
    "Indian transplant patients under contemporary clinical conditions. The contemporary-practice "
    "design isolates body weight and the UGT pharmacogenomic variation as the remaining "
    "differentiating parameters between Western and Indian cohorts. At standard 1 g BID dosing with "
    "clinically representative albumin and tacrolimus-based regimens, 68% of Indian patients exceed "
    "the therapeutic AUC window, with correspondingly elevated toxicity risk (67.2% any adverse "
    "event vs 48.7%). Weight-based dosing at 12 mg/kg BID (nomogram: 500 mg for <50 kg, 750 mg for "
    "50–<75 kg, 1000 mg for ≥75 kg) optimizes both target attainment and the therapeutic "
    "index. These findings, robust to ±20% parameter perturbation, provide a mechanistic "
    "justification for prospective clinical trials of individualized MPA dosing in Indian and other "
    "low-weight transplant populations.")

DISC = ("These findings have direct clinical implications. The higher variability in Indian patients "
    "suggests a stronger rationale for routine therapeutic drug monitoring (TDM) and AUC-guided dose "
    "adjustment in this population [3, 5, 6, 17]. Furthermore, the pharmacogenetic architecture of MPA "
    "metabolism differs substantially between South Asian and Western populations in ways directly "
    "relevant to overexposure. The UGT1A9 promoter gain-of-function variants −275T>A and "
    "−2152C>T, which increase hepatic UGT1A9 expression, lower MPA exposure by ~20%, and have "
    "been associated with acute rejection in MMF/tacrolimus-treated Western recipients [23] are "
    "essentially absent in South Asians (gnomAD minor-allele frequency ≈1% each, versus "
    "≈5–6% in Europeans and 0% in East Asians [11, 19, 24]). The reduced-activity UGT1A9*3 "
    "(c.98T>C) allele, which conversely raises MPA exposure, is likewise near-absent in South Asians "
    "(<0.2% vs ≈1.4% in Europeans [19]). Consequently, the common European variants that shift "
    "MPA clearance are not operative at the population level in Indian patients, who lack the "
    "clearance-accelerating genotype that partially protects a subset (~10–15%) of Western "
    "recipients from overexposure. By contrast, the intronic UGT1A9 I399C>T variant, which is reported "
    "to influence MPA pharmacokinetics in Japanese renal transplant recipients [24], reaches its "
    "highest global frequency in South Asians (≈33%, versus ≈30% in Europeans and ≈3% "
    "in East Asians [19]), although its functional impact on MPA exposure remains unresolved. Together "
    "with an intermediate UGT2B7 c.802C>T T-allele frequency (≈37–40% in South Indian "
    "cohorts [18], below the ≈49–52% reported in Europeans), these data indicate that the "
    "UGT variants most strongly linked to MPA exposure in Western and East Asian studies do not "
    "transfer directly to South Asians. Pharmacogenomic-guided dosing in Indian recipients will "
    "therefore require South Asian-specific functional-variant discovery rather than genotyping the "
    "established European markers, reinforcing AUC-guided TDM as the pragmatic near-term strategy "
    "[3, 17].")

lines = open(PATH, encoding='utf-8').read().split('\n')
out = []
inref = False
refbuf = []

def flush_refs():
    # parse "N. text" entries, reorder by MAP, renumber, emit consecutively
    entries = {}
    for ln in refbuf:
        m = re.match(r'^(\d+)\.\s+(.*)$', ln.strip())
        if m:
            entries[int(m.group(1))] = m.group(2)
    new = {}
    for old, txt in entries.items():
        new[MAP.get(old, old)] = txt
    res = []
    for n in sorted(new):
        res.append(f'{n}. {new[n]}')
    return res

for s in lines:
    st = s.strip()
    if st == '## References':
        inref = True; out.append(s); continue
    if inref:
        if st == '---' or (s.startswith('## ') and st != '## References'):
            inref = False
            out.append('')                 # blank line after heading already present? keep clean
            out.extend(flush_refs())
            out.append('')
            out.append(s)
            continue
        refbuf.append(s); continue
    # prose
    if st.startswith('This PBPK/PD analysis quantifies'):
        out.append(CONCL)
    elif st.startswith('These findings have direct clinical implications'):
        out.append(DISC)
    elif 'recommendations (contiguous weight bins)' in s:
        out.append(s.replace('(contiguous weight bins): ', '(contiguous weight bins), that are '))
    elif st.startswith('Virtual populations of 500'):
        s = s.replace('established effect-size estimate: direct',
                      'established effect-size estimate, as the direct')
        out.append(remap_cites(s))
    elif s.startswith('| UGT1A9 activity |'):
        out.append('| UGT1A9 activity | 1.01 ± 0.15 | 0.96 ± 0.18 |')
    elif s.startswith('| UGT2B7 activity |'):
        out.append('| UGT2B7 activity | 1.01 ± 0.15 | 0.94 ± 0.18 |')
    else:
        out.append(remap_cites(s))

# collapse the accidental double blank introduced before flush (the original had a blank after heading)
text = '\n'.join(out)
text = text.replace('## References\n\n\n', '## References\n\n')
open(PATH, 'w', encoding='utf-8').write(text)
print('md synced')
