import {shell, button, press, feedback} from '/shared/common.js';
const brand='图书馆空间预约', date='11 月 18 日';
const slots=['15:00–16:00','16:00–17:00'];
let slot=slots[0], people=3, occupied=false;
function choose(note=''){
  const opts=slots.map(s=>`<option ${s===slot?'selected':''} ${occupied && s===slots[0]?'disabled':''}>${s}</option>`).join('');
  shell(brand,'预约讨论室',`<p>南馆二号讨论室 · ${date} · 最多 6 人</p>${feedback(note)}
    <label for="slot">使用时段</label><select id="slot">${opts}</select>
    <label for="people">参与人数</label><input id="people" type="number" value="${people}" min="1" max="6">
    <div>${button('next','核对预约',true)}</div>`);
  press('next',()=>{slot=document.querySelector('#slot').value;people=Number(document.querySelector('#people').value);
    if(!Number.isInteger(people)||people<1||people>6){people=3;return choose('请输入 1 至 6 人。');} review();});
}
function review(note=''){
  shell(brand,'核对预约',`<section class="card"><h2>南馆二号讨论室</h2><p>${date} · ${slot}</p><p>参与人数：${people} 人</p></section>${feedback(note)}${button('edit','返回选择')}${button('book','确认预约',true)}`);
  press('edit',()=>{if(occupied&&slot===slots[0]) slot=slots[1];choose();});
  press('book',()=>{if(slot===slots[0]){occupied=true;return review('此时段刚被预约。请返回选择其他时段。');}
    shell(brand,'预约成功',`<p role="status">预约号 R-204</p><p>${date} · ${slot} · ${people} 人</p><p>请在所选时段前往南馆二号讨论室。</p>`);});
}
choose();
