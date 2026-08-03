"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import { API_URL } from "../contacts/constants";

type Lead = { id: string; email: string; phone: string | null; domain: string };
type CallSummary = { id:string; call_result:string; summary:string; next_action:string; next_call_at:string|null; duration_seconds:number|null; created_by:string|null; created_at:string };

const RESULTS: Record<string,string> = { CONNECTED:"Pogovor", NO_ANSWER:"Ni odgovora", VOICEMAIL:"Govorna pošta", WRONG_NUMBER:"Napačna številka", NOT_INTERESTED:"Ne zanima", FOLLOW_UP:"Follow-up", MEETING_BOOKED:"Termin dogovorjen", OFFER_SENT:"Ponudba poslana", OTHER:"Drugo" };
const ACTIONS: Record<string,string> = { NONE:"Brez naslednje aktivnosti", CALL:"Ponovni klic", EMAIL:"Pošlji e-mail", MEETING:"Sestanek", OFFER:"Pošlji ponudbo", OTHER:"Drugo" };

function date(value:string|null){ return value ? new Intl.DateTimeFormat("sl-SI",{dateStyle:"medium",timeStyle:"short"}).format(new Date(value)) : "—"; }

export default function CallSummaryDrawer({lead,onClose}:{lead:Lead;onClose:()=>void}){
  const [items,setItems]=useState<CallSummary[]>([]);
  const [loading,setLoading]=useState(true);
  const [saving,setSaving]=useState(false);
  const [error,setError]=useState<string|null>(null);
  const [result,setResult]=useState("CONNECTED");
  const [summary,setSummary]=useState("");
  const [action,setAction]=useState("NONE");
  const [nextAt,setNextAt]=useState("");
  const [duration,setDuration]=useState("");
  const [createdBy,setCreatedBy]=useState("Kristjan");

  const load=useCallback(async()=>{
    try{setLoading(true);setError(null);const r=await fetch(`${API_URL}/contacts/${lead.id}/call-summaries`,{cache:"no-store"});const d=await r.json();if(!r.ok)throw new Error(d.detail??"Napaka pri nalaganju.");setItems(d.items??[]);}catch(e){setError(e instanceof Error?e.message:"Napaka pri nalaganju.");}finally{setLoading(false);}
  },[lead.id]);
  useEffect(()=>{void load();},[load]);

  async function save(e:FormEvent){e.preventDefault();try{setSaving(true);setError(null);const mins=Number(duration||0);const r=await fetch(`${API_URL}/contacts/${lead.id}/call-summaries`,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({call_result:result,summary:summary.trim(),next_action:action,next_call_at:nextAt?new Date(nextAt).toISOString():null,duration_seconds:mins>0?mins*60:null,created_by:createdBy.trim()||null})});const d=await r.json();if(!r.ok)throw new Error(d.detail??"Shranjevanje ni uspelo.");setSummary("");setAction("NONE");setNextAt("");setDuration("");await load();}catch(e){setError(e instanceof Error?e.message:"Shranjevanje ni uspelo.");}finally{setSaving(false);}}
  async function remove(id:string){if(!confirm("Izbrišem povzetek klica?"))return;const r=await fetch(`${API_URL}/contacts/${lead.id}/call-summaries/${id}`,{method:"DELETE"});if(r.ok)await load();}

  return <div className="callDrawerBackdrop" onMouseDown={e=>{if(e.target===e.currentTarget)onClose();}}><aside className="callDrawer">
    <header className="callDrawerHeader"><div><p className="eyebrow">POVZETKI KLICEV</p><h2>{lead.phone??"Telefon"}</h2><p className="muted">{lead.email}</p></div><button onClick={onClose} aria-label="Zapri">×</button></header>
    <form className="callSummaryForm" onSubmit={save}>
      <div className="callFormGrid"><label><span>Rezultat klica</span><select value={result} onChange={e=>setResult(e.target.value)}>{Object.entries(RESULTS).map(([v,l])=><option key={v} value={v}>{l}</option>)}</select></label><label><span>Trajanje (min)</span><input type="number" min="0" value={duration} onChange={e=>setDuration(e.target.value)} placeholder="npr. 8"/></label></div>
      <label><span>Povzetek</span><textarea required rows={5} value={summary} onChange={e=>setSummary(e.target.value)} placeholder="Kaj se je zgodilo med klicem?"/></label>
      <div className="callFormGrid"><label><span>Naslednja aktivnost</span><select value={action} onChange={e=>setAction(e.target.value)}>{Object.entries(ACTIONS).map(([v,l])=><option key={v} value={v}>{l}</option>)}</select></label><label><span>Datum in ura</span><input type="datetime-local" value={nextAt} onChange={e=>setNextAt(e.target.value)}/></label></div>
      <label><span>Klical</span><input value={createdBy} onChange={e=>setCreatedBy(e.target.value)}/></label>
      {error&&<div className="callSummaryError">{error}</div>}
      <button className="callSaveButton" disabled={saving||!summary.trim()}>{saving?"Shranjujem …":"Shrani povzetek"}</button>
    </form>
    <section className="callTimeline"><div className="callTimelineHeader"><div><p className="eyebrow">ZGODOVINA</p><h3>Pretekli klici</h3></div><span>{items.length}</span></div>
      {loading?<div className="callTimelineEmpty">Nalaganje …</div>:items.length===0?<div className="callTimelineEmpty">Za ta kontakt še ni povzetkov klicev.</div>:<div className="callTimelineList">{items.map(item=><article className="callTimelineItem" key={item.id}><div className="callTimelineDot"/><div className="callTimelineContent"><div className="callTimelineTop"><div><span className="callResultBadge">{RESULTS[item.call_result]??item.call_result}</span><strong>{date(item.created_at)}</strong></div><button onClick={()=>void remove(item.id)}>Izbriši</button></div><p>{item.summary}</p><div className="callTimelineMeta">{item.duration_seconds!==null&&<span>Trajanje: {Math.round(item.duration_seconds/60)} min</span>}{item.created_by&&<span>Klical: {item.created_by}</span>}{item.next_action!=="NONE"&&<span>Naslednje: {ACTIONS[item.next_action]??item.next_action}</span>}{item.next_call_at&&<span>{date(item.next_call_at)}</span>}</div></div></article>)}</div>}
    </section>
  </aside></div>;
}
