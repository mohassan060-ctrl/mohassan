import io
import json
import os
import re
import zipfile
from pathlib import Path

import pandas as pd
import streamlit as st
from engine import DATA, boards, scan_all
from workflow import (STAGES,EVIDENCE_KINDS,EVIDENCE_VERDICTS,add_evidence,all_jobs,build_brief,
    get_evidence,make_cv_docx,make_evidence_docx,make_letter_docx,set_stage,sponsorship_assessment,upsert_jobs)

st.set_page_config(page_title='VisaSponsor AI | Approval Queue',page_icon='🌍',layout='wide')
st.title('VisaSponsor AI')
st.caption('International roles • evidence-based sponsorship triage • tailored application documents • human approval')
st.info('This agent never submits applications. Sponsorship claims are extracted from individual vacancies or manually entered evidence. A sponsor licence or employer history is not sufficient proof for a specific role.')
profile=json.loads((DATA/'candidate_profile.json').read_text(encoding='utf-8'))

with st.sidebar:
    st.header('Search configuration')
    st.caption('Only public Greenhouse and Lever employer boards are supported in this release.')
    entries=boards()
    with st.form('board'):
        company=st.text_input('Employer name')
        platform=st.selectbox('Recruitment system',['greenhouse','lever'])
        slug=st.text_input('Public ATS slug')
        region=st.selectbox('Lever region',['global','eu'])
        add=st.form_submit_button('Add employer')
    if add:
        if not company.strip() or not re.fullmatch(r'[a-zA-Z0-9_-]+',slug.strip()): st.error('Enter a company and a valid board slug.')
        elif any(x['platform']==platform and x['slug']==slug.strip() for x in entries):st.warning('Already configured.')
        else:
            entries.append({'company':company.strip(),'platform':platform,'slug':slug.strip(),'region':region})
            (DATA/'boards.json').write_text(json.dumps(entries,indent=2),encoding='utf-8')
            st.success('Added employer.');st.rerun()
    st.caption(f'{len(entries)} employer boards configured')
    if st.button('Scan configured boards',type='primary',use_container_width=True):
        with st.spinner('Fetching employer postings...'):
            jobs,errors=scan_all();upsert_jobs(jobs)
        st.success(f'Collected {len(jobs)} matching postings.')
        for error in errors:st.warning(error)
    st.divider()
    st.subheader('Applicant details (optional)')
    st.caption('This information stays in the current session and is inserted in generated documents only.')
    name=st.text_input('Full name',value='Syed Mohammad Hassan')
    email=st.text_input('Contact email',value='')
    linkedin=st.text_input('LinkedIn URL',value='')
    contact={'name':name,'email':email,'linkedin':linkedin,'location':'Karachi, Pakistan'}
    st.warning('Keep your dashboard private. Cloud filesystem data is not reliably persistent; use a persistent mounted DB for production.')

jobs=all_jobs()
if not jobs:
    st.warning('The queue is empty. Add official employer ATS slugs on the left and run a scan. No fake vacancies are preloaded.')
    st.markdown('Greenhouse boards: `boards.greenhouse.io/SLUG`; Lever boards: `jobs.lever.co/SLUG`.')
    st.stop()

counts=st.columns(4)
counts[0].metric('Jobs discovered',len(jobs))
counts[1].metric('Awaiting review',sum(j['status'] in ('New','Researching sponsorship','Ready for review') for j in jobs))
counts[2].metric('Approved',sum(j['status']=='Approved to apply' for j in jobs))
counts[3].metric('Applied (user recorded)',sum(j['status']=='Applied' for j in jobs))

markets=st.multiselect('Filter application stages',STAGES,default=['New','Researching sponsorship','Ready for review','Approved to apply','Applied'])
term=st.text_input('Search employer or title')
visible=[j for j in jobs if j['status'] in markets and term.casefold() in (j['title']+' '+j['company']).casefold()]
table=[]
for j in visible:
    label,eligible=sponsorship_assessment(get_evidence(j['job_id']))
    table.append({'Company':j['company'],'Title':j['title'],'Location':j['location'],'Fit score':j['score'],'Evidence classification':label,'Stage':j['status'],'Official posting':j['url']})
st.dataframe(pd.DataFrame(table),hide_index=True,use_container_width=True,column_config={'Official posting':st.column_config.LinkColumn('Official posting')})
if not visible:st.stop()

options={f"{j['company']} · {j['title']} [{j['job_id']}]":j for j in visible}
key=st.selectbox('Open application review',list(options))
job=options[key];ev=get_evidence(job['job_id']);assessment,approveable=sponsorship_assessment(ev)
st.header(job['title'])
st.write(f"**{job['company']}** · {job['location']}")
st.write('**Sponsorship evidence assessment:** '+assessment)
st.link_button('View original employer listing',job['url'])

review,evidence_tab,docs,history=st.tabs(['Review queue','Evidence register','Application pack','Job description'])
with review:
    st.write('**Current stage:** '+job['status'])
    if not approveable:st.warning('Approval is blocked until vacancy-specific positive sponsorship evidence is recorded. Employer licence or past sponsorship alone does not qualify.')
    with st.form('review'):
        new_stage=st.selectbox('Set stage',STAGES,index=STAGES.index(job['status']))
        notes=st.text_area('Internal application notes',value=job['notes'] or '')
        saved=st.form_submit_button('Save reviewed decision')
    if saved:
        try:
            set_stage(job['job_id'],new_stage,notes)
            st.success('Decision recorded. No application was submitted.');st.rerun()
        except ValueError as ex:st.error(str(ex))
    st.caption('Mark Applied only after you personally submit through the employer portal. Review decision history is recorded locally.')
with evidence_tab:
    st.subheader('Traceable sponsorship evidence')
    for e in ev:
        with st.expander(f"{e['kind']} · {e['verdict']} · {e['checked_at']}"):
            st.write(e['quote']);st.write(e['source_url']);st.caption('Recorded by: '+e['reviewer'])
    st.caption('Paste an exact quotation or an explanatory evidence note plus a working URL. This records your research; the app does not independently validate pasted evidence.')
    with st.form('evidence_entry'):
        kind=st.selectbox('Evidence source type',EVIDENCE_KINDS)
        verdict=st.selectbox('What does the source establish?',EVIDENCE_VERDICTS)
        quote=st.text_area('Exact quotation or research note')
        url=st.text_input('Evidence source URL',value=job['url'])
        submitted=st.form_submit_button('Add evidence to record')
    if submitted:
        try:add_evidence(job['job_id'],kind,verdict,quote,url);st.success('Recorded.');st.rerun()
        except ValueError as ex:st.error(str(ex))
with docs:
    st.subheader('Generate application documents')
    st.caption('The CV is a role-oriented highlights draft, not a full employment-history CV. The cover letter is a fact-constrained first draft. Review and expand both against your master CV before applying.')
    brief=build_brief(job,profile,ev)
    cv=make_cv_docx(job,profile,contact)
    letter=make_letter_docx(job,profile,contact)
    evidence_file=make_evidence_docx(job,ev)
    pack=io.BytesIO()
    with zipfile.ZipFile(pack,'w',zipfile.ZIP_DEFLATED) as z:
        z.writestr('CV_role_highlights_DRAFT.docx',cv)
        z.writestr('Cover_letter_DRAFT.docx',letter)
        z.writestr('Sponsorship_evidence.docx',evidence_file)
        z.writestr('Application_brief.json',json.dumps(brief,indent=2,ensure_ascii=False))
        z.writestr('REVIEW_BEFORE_SUBMISSION.txt','All files are drafts. Verify achievements and job suitability. Confirm immigration eligibility directly with the employer. No automatic submission occurs.\n')
    st.download_button('Download complete application pack (ZIP)',pack.getvalue(),file_name='application_pack.zip',mime='application/zip',type='primary')
    with st.expander('Facts awaiting confirmation'):
        for claim in profile.get('claims_to_confirm',[]):st.write('• '+claim)
with history:
    st.write(job['description'] or 'No description provided.')
