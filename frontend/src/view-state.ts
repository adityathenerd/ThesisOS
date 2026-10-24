export type WorkspaceView='dashboard'|'cases'|'reference'|'mandate';
export function readView(hash:string):{view:WorkspaceView;caseId:string|null}{
 if(hash==='#reference')return {view:'reference',caseId:null};
 if(hash==='#mandate')return {view:'mandate',caseId:null};
 if(hash==='#cases')return {view:'cases',caseId:null};
 if(hash.startsWith('#cases/')){
  try{const caseId=decodeURIComponent(hash.slice(7));if(caseId)return {view:'cases',caseId};}catch{/* A malformed link falls back to the collection. */}
  return {view:'cases',caseId:null};
 }
 return {view:'dashboard',caseId:null};
}
export function viewHash(view:WorkspaceView,caseId?:string){return view==='cases'&&caseId?`#cases/${encodeURIComponent(caseId)}`:`#${view}`;}
