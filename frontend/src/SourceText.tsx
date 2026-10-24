import type {ReactNode} from 'react';

function inline(text:string):ReactNode[]{
 const parts=text.split(/(\*\*[^*]+\*\*|`[^`]+`|\[[^\]]+\]\(https?:\/\/[^\s)]+\))/g);
 return parts.map((part,index)=>{if(part.startsWith('**')&&part.endsWith('**'))return <strong key={index}>{part.slice(2,-2)}</strong>;if(part.startsWith('`')&&part.endsWith('`'))return <code key={index}>{part.slice(1,-1)}</code>;const link=part.match(/^\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)$/);return link?<a key={index} href={link[2]} target="_blank" rel="noreferrer">{link[1]} ↗</a>:part;});
}
export default function SourceText({text}:{text:string}){
 const lines=text.replaceAll('\r\n','\n').split('\n'),blocks:ReactNode[]=[];let index=0;
 while(index<lines.length){const line=lines[index];if(!line.trim()){index++;continue;}
  if(line.startsWith('|')&&lines[index+1]?.match(/^\|[\s:|-]+\|\s*$/)){const cells=(s:string)=>s.trim().slice(1,-1).split('|').map(cell=>cell.trim());const head=cells(line),rows:string[][]=[];index+=2;while(lines[index]?.startsWith('|')){rows.push(cells(lines[index]));index++;}blocks.push(<div className="source-table-wrap" key={`t${index}`}><table><thead><tr>{head.map((cell,i)=><th key={i}>{inline(cell)}</th>)}</tr></thead><tbody>{rows.map((row,r)=><tr key={r}>{row.map((cell,c)=><td key={c}>{inline(cell)}</td>)}</tr>)}</tbody></table></div>);continue;}
  const heading=line.match(/^(#{1,6})\s+(.+)$/);if(heading){blocks.push(<h3 key={`h${index}`}>{inline(heading[2])}</h3>);index++;continue;}
  if(/^[-*] /.test(line)){const items:string[]=[];while(lines[index]&&/^[-*] /.test(lines[index])){items.push(lines[index].slice(2));index++;}blocks.push(<ul key={`u${index}`}>{items.map((item,i)=><li key={i}>{inline(item)}</li>)}</ul>);continue;}
  if(/^\d+\. /.test(line)){const items:string[]=[];while(lines[index]&&/^\d+\. /.test(lines[index])){items.push(lines[index].replace(/^\d+\. /,''));index++;}blocks.push(<ol key={`o${index}`}>{items.map((item,i)=><li key={i}>{inline(item)}</li>)}</ol>);continue;}
  const paragraph=[line];index++;while(index<lines.length&&lines[index].trim()&&!/^(?:#{1,6} |[-*] |\d+\. |\|)/.test(lines[index]))paragraph.push(lines[index++]);blocks.push(<p key={`p${index}`}>{inline(paragraph.join('\n'))}</p>);
 }
 return <div className="source-text">{blocks}</div>;
}
