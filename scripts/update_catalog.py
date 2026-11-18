#!/usr/bin/env python3
"""Best-effort free TCGdex Japanese *metadata* lookup; no card images or prices.
Only save match if printed local card number and exact Japanese card name match uniquely.
"""
import csv
import json
import re
import time
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

ROOT=Path(__file__).resolve().parents[1]
CSV=ROOT/'data/price_updates.csv'
OUT=ROOT/'data/catalog.json'
BASE='https://api.tcgdex.net/v2/ja/cards'

def base_name(name):
    name=re.sub(r'\s*\([^)]*\)\s*$', '', name).strip()
    return re.sub(r'\s+(?:SAR|SR|AR|UR|CSR|CHR|HR|RRR|RR|R|U|C|PROMO)\b.*$', '', name).strip()

def lookup(name, printed):
    url=BASE+'?'+urlencode({'name':name, 'pagination:itemsPerPage':100})
    req=Request(url,headers={'User-Agent':'POKE-WATCH/1.0 (public card metadata lookup)'})
    with urlopen(req,timeout=20) as response:
        data=json.load(response)
    if not isinstance(data,list):
        return None
    # TCGdex card objects use localId (printed number before slash), not rarity suffix.
    local=printed.split('/')[0].lstrip('0') or '0'
    matches=[x for x in data if isinstance(x,dict)
             and x.get('name')==name
             and str(x.get('localId','')).lstrip('0')==local]
    if len(matches)!=1: return None
    card=matches[0]
    cardid=card.get('id')
    if not isinstance(cardid,str) or not re.fullmatch(r'[A-Za-z0-9_-]{2,80}',cardid):
        return None
    return {'name':name,'printed_number':printed,'tcgdex_id':cardid,
            'url':'https://api.tcgdex.net/v2/ja/cards/'+cardid,'provider':'TCGdex',
            'match_status':'number_and_exact_name'}

def main():
    with CSV.open(encoding='utf-8-sig',newline='') as f:
        rows=list(csv.DictReader(f))
    latest={r['card_id']:r['name'] for r in rows if r.get('card_id')}
    result=json.loads(OUT.read_text(encoding='utf8')) if OUT.exists() else {}
    updated=0; checked=0
    for card_id,name in latest.items():
        if card_id in result: continue
        number=card_id.split(' ',1)[-1].strip()
        if not re.fullmatch(r'\d{1,4}/\d{1,4}',number):continue
        checked+=1
        try:
            item=lookup(base_name(name),number)
            if item:result[card_id]=item;updated+=1
        except Exception as ex:
            print('Lookup failed for', card_id, str(ex)[:160])
        time.sleep(.2)
    OUT.parent.mkdir(parents=True,exist_ok=True)
    content=json.dumps(result,ensure_ascii=False,indent=2,sort_keys=True)+'\n'
    if not OUT.exists() or OUT.read_text(encoding='utf8')!=content:
        OUT.write_text(content,encoding='utf8')
    print(f'Catalog: checked {checked}, newly matched {updated}, total matched {len(result)}')

if __name__=='__main__':main()
