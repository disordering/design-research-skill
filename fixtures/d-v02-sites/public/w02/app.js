import {shell, button, press, feedback, esc} from '/shared/common.js';
const brand='蓝桥文印', modes=['到店自取','校内配送'];
let job={pages:'12',copies:'1',side:'双面',mode:modes[0],address:''};
function quote(){const sheets=job.side==='双面'?Math.ceil(Number(job.pages)/2):Number(job.pages);
  const printing=sheets*Number(job.copies)*20, delivery=job.mode===modes[1]?300:0;
  return {sheets,printing,delivery,total:printing+delivery};}
const money=cents=>(cents/100).toFixed(2);
function edit(note=''){
  const opt=(v,current)=>`<option ${v===current?'selected':''}>${v}</option>`;
  shell(brand,'设置打印单',`<p>文件：课程讲义.pdf。每张纸 0.20 元，校内配送每单 3 元。</p>${feedback(note)}
    <label for="pages">原稿页数</label><input id="pages" type="number" value="${esc(job.pages)}">
    <label for="copies">份数</label><input id="copies" type="number" value="${esc(job.copies)}">
    <label for="side">打印方式</label><select id="side">${['单面','双面'].map(v=>opt(v,job.side)).join('')}</select>
    <label for="mode">取件方式</label><select id="mode">${modes.map(v=>opt(v,job.mode)).join('')}</select>
    <div id="addressRow"><label for="address">配送楼栋</label><input id="address" value="${esc(job.address)}"></div>
    <div>${button('next','查看报价',true)}</div>`);
  const mode=document.querySelector('#mode'), addressRow=document.querySelector('#addressRow');
  const toggle=()=>{addressRow.hidden=(mode.value===modes[0]);};mode.onchange=toggle;toggle();
  press('next',()=>{for(const k of Object.keys(job))job[k]=document.getElementById(k).value;
    const inRange=(v,max)=>Number.isInteger(Number(v))&&Number(v)>0&&Number(v)<=max;
    if(!inRange(job.pages,60)||!inRange(job.copies,5))return edit('页数须为 1 至 60，份数须为 1 至 5。');
    if(job.mode===modes[1]&&!job.address.trim())return edit('请填写配送楼栋。');
    const q=quote();shell(brand,'核对报价',`<section class="card"><p>${job.pages} 页 · ${job.copies} 份 · ${job.side}</p><p>${job.mode} ${job.mode===modes[1]?esc(job.address):''}</p><p>打印费 ¥${money(q.printing)}，配送费 ¥${money(q.delivery)}</p><p>合计 ¥${money(q.total)}</p></section>${button('edit','返回修改')}${button('order','提交打印单',true)}`);
    press('edit',()=>edit());press('order',()=>shell(brand,'打印单已提交',`<p role="status">打印单 P-106</p><p>合计 ¥${money(q.total)} · ${job.mode}</p>`));});
}
edit();
