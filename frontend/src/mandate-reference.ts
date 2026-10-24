export interface CanonicalReference{document_path:string;document_version:string;document_sha256:string;document_text:string;review_status:string;policy_active:boolean|null}
export interface MandateRuntimeView{input_mode:string;binding_status:string;source_path:string|null;source_version:string|null;source_hash:string|null;assessment_count:number|null;qualification_policy_approved:boolean|null;note:string;reference:CanonicalReference|null}
export interface ThesisSection{id:string;title:string;text:string}
export const localReferenceMeta={document_path:'planning/investment-thesis/scouting-mandate.md',document_version:'0.3',document_sha256:'2d01a3b2a91b25aa5c4285aefcfffc5f84246833dbfe54aa66778ba96c0e6ce4',review_status:'human_reviewed_direction_only',policy_active:false};

export function thesisSections(text:string):{title:string;introduction:string;sections:ThesisSection[]}{
 const lines=text.replaceAll('\r\n','\n').split('\n'),title=lines.find(line=>line.startsWith('# '))?.slice(2)??'Canonical thesis';
 const sections:ThesisSection[]=[];let current:ThesisSection|null=null;const intro:string[]=[];
 for(const line of lines){if(line.startsWith('## ')){const heading=line.slice(3),id=heading.match(/^(\d+)\./)?.[1]??`section-${sections.length+1}`;current={id,title:heading,text:''};sections.push(current);}else if(current)current.text+=(current.text?'\n':'')+line;else intro.push(line);}
 return{title,introduction:intro.join('\n'),sections};
}
export async function referenceHash(text:string){const bytes=await crypto.subtle.digest('SHA-256',new TextEncoder().encode(text));return[...new Uint8Array(bytes)].map(byte=>byte.toString(16).padStart(2,'0')).join('');}
export async function verifyReference(reference:CanonicalReference){return /^[a-f0-9]{64}$/i.test(reference.document_sha256)&&(await referenceHash(reference.document_text))===reference.document_sha256.toLowerCase();}

export async function readMandateReference(input:unknown,mandateId:string):Promise<MandateRuntimeView>{
 if(!input||typeof input!=='object')throw new Error('The backend returned no reference metadata.');
 const raw=input as Record<string,unknown>;
 if(raw.mandate_id!==mandateId)throw new Error('The reference response belongs to a different mandate.');
 for(const key of ['document_path','document_version','document_sha256','document_text'])if(typeof raw[key]!=='string')throw new Error(`The reference response is missing ${key}.`);
 const sameLocal=raw.document_sha256===localReferenceMeta.document_sha256;
 const reference:CanonicalReference={document_path:raw.document_path as string,document_version:raw.document_version as string,document_sha256:raw.document_sha256 as string,document_text:raw.document_text as string,review_status:sameLocal?localReferenceMeta.review_status:'not_reported',policy_active:null};
 if(!(await verifyReference(reference)))throw new Error('The backend document text does not match its reported SHA-256. The runtime reference was not accepted.');
 return{input_mode:'Full canonical reference pinned on server; individual assessment use is not reported here',binding_status:'Server reference and content hash verified',source_path:reference.document_path,source_version:reference.document_version,source_hash:reference.document_sha256,assessment_count:null,qualification_policy_approved:typeof raw.qualification_policy_approved==='boolean'?raw.qualification_policy_approved:null,reference,note:`${typeof raw.authority==='string'?raw.authority:''} This response confirms the server-pinned document. It does not include per-assessment input bindings; those are not inferred from the saved run brief.`};
}
