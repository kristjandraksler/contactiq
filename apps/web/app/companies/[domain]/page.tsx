"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useParams } from "next/navigation";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";

type Company = { domain:string; name:string; website:string|null; country_code:string|null; country_name:string|null; country_flag:string|null; contacts:number; phones:number; person_phones:number; company_phones:number; cross_border:number; success_rate:number; average_confidence:number; last_scan:string|null; };
type Contact = { id:string; email:string; phone:string|null; confidence:number|null; status:string; source_url:string|null; person_match_type:string|null; phone_country_flag:string|null; phone_country_name:string|null; updated_at:string; };
type ResponseData = { company:Company; contacts:Contact[]; sources:string[] };

function number(value:number){ return new Intl.NumberFormat("sl-SI").format(value); }

export default function CompanyDetailPage(){
  const params=useParams<{domain:string}>();
  const domain=decodeURIComponent(params.domain);
  const [data,setData]=useState<ResponseData|null>(null);
  const [error,setError]=useState<string|null>(null);

  useEffect(()=>{ void (async()=>{ try{ const response=await fetch(`${API_URL}/companies/${encodeURIComponent(domain)}`,{cache:"no-store"}); if(!response.ok) throw new Error("Podjetja ni bilo mogoče naložiti."); setData(await response.json()); }catch(err){ setError(err instanceof Error?err.message:"Nepričakovana napaka."); } })(); },[domain]);

  if(error) return <div className="panel pagePanel"><div className="errorBanner">{error}</div><Link href="/companies">← Nazaj na podjetja</Link></div>;
  if(!data) return <div className="panel pagePanel">Nalagam podjetje …</div>;
  const company=data.company;

  return <div className="companyDetailPage">
    <Link className="companyBack" href="/companies">← Nazaj na podjetja</Link>
    <header className="companyDetailHero">
      <div className="companyDetailIdentity"><span>{company.name.slice(0,2).toUpperCase()}</span><div><p className="eyebrow">COMPANY INTELLIGENCE</p><h1>{company.name}</h1><p>{company.domain}</p></div></div>
      <div className="companyDetailActions">{company.website&&<a href={company.website} target="_blank" rel="noreferrer">Odpri spletno stran ↗</a>}<Link href={`/contacts?search=${encodeURIComponent(company.domain)}`}>Odpri vse kontakte</Link></div>
    </header>

    <section className="companyDetailKpis">
      <article><span>Kontakti</span><strong>{number(company.contacts)}</strong></article>
      <article><span>Telefoni</span><strong>{number(company.phones)}</strong><small>{company.person_phones} osebnih · {company.company_phones} poslovnih</small></article>
      <article><span>Uspešnost</span><strong>{company.success_rate.toFixed(1)}%</strong></article>
      <article><span>Confidence</span><strong>{company.average_confidence ? `${company.average_confidence.toFixed(0)}%` : "—"}</strong></article>
      <article><span>Država</span><strong>{company.country_flag ?? "🌍"} {company.country_name ?? "Neznana"}</strong></article>
      <article><span>Cross-border</span><strong>{number(company.cross_border)}</strong></article>
    </section>

    <section className="companyDetailGrid">
      <article className="panel pagePanel"><div className="panelTop"><div><h2>Kontakti</h2><p className="muted">Vsi kontakti, povezani s to domeno.</p></div></div><div className="companiesTableWrap"><table className="companiesTable"><thead><tr><th>E-mail</th><th>Telefon</th><th>Tip</th><th>Confidence</th><th>Status</th></tr></thead><tbody>{data.contacts.map(contact=><tr key={contact.id}><td><strong>{contact.email}</strong></td><td>{contact.phone ? <span>{contact.phone_country_flag ?? "☎"} {contact.phone}</span> : "—"}</td><td>{contact.person_match_type?.replaceAll("_"," ") ?? "—"}</td><td>{contact.confidence!==null?`${contact.confidence}%`:"—"}</td><td><span className={`companyStatus ${contact.status.toLowerCase()}`}>{contact.status.replaceAll("_"," ")}</span></td></tr>)}</tbody></table></div></article>
      <aside className="panel pagePanel companySources"><h2>Viri</h2><p className="muted">Javne strani, na katerih so bili najdeni podatki.</p>{data.sources.length===0?<div className="companiesEmpty">Ni shranjenih virov.</div>:<div>{data.sources.map(source=><a href={source} target="_blank" rel="noreferrer" key={source}>{source}<span>↗</span></a>)}</div>}</aside>
    </section>
  </div>;
}
