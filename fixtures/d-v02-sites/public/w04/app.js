import {shell, button, press, feedback, readSaved, save} from '/shared/common.js';
const brand='青禾工坊';
const permits={waitlist:false};
const events=[{id:'a',name:'陶艺体验',time:'14:00',available:0},{id:'b',name:'篆刻入门',time:'16:00',available:2}];
let record=readSaved();
const spaces=e=>e.available-(record?.id===e.id?1:0);
function home(){shell(brand,'周末活动',`<p>11 月 21 日 · 创意工坊</p>${events.map(e=>`<section class="card"><h2>${e.name}</h2><p>${e.time} · 余位 ${spaces(e)}</p>${button('open-'+e.id,'查看'+e.name)}</section>`).join('')}${record?button('mine','我的报名'):''}`);
  for(const e of events)press('open-'+e.id,()=>detail(e));if(record)press('mine',()=>mine());}
function detail(e,note=''){
  const full=spaces(e)===0, registered=record?.id===e.id;
  shell(brand,e.name,`<p>11 月 21 日 ${e.time} · 创意工坊</p><p>余位 ${spaces(e)}</p>${feedback(note)}
    ${button('back','返回活动')}${registered?button('mine','查看报名'):button('join',full&&permits.waitlist?'登记候补':'报名参加',true)}`);
  press('back',home);if(registered)return press('mine',mine);
  press('join',()=>{if(full&&!permits.waitlist)return detail(e,'本场已满，请选择其他活动。');
    if(record)return detail(e,'请先取消已有报名。');
    record={id:e.id,kind:full?'候补':'已报名'};save(record);mine();});}
function mine(){const e=events.find(x=>x.id===record.id);shell(brand,'我的报名',`<section class="card"><h2>${e.name}</h2><p>${e.time} · ${record.kind} · A-071</p></section>${button('back','返回活动')}${button('cancel','取消报名')}`);
  press('back',home);press('cancel',()=>{shell(brand,'确定取消报名？',`<p>${e.name} · ${e.time}。取消后名额将释放。</p>${button('keep','保留报名')}${button('sure','确认取消')}`);
    press('keep',mine);press('sure',()=>{record=null;save(null);home();});});}
home();
