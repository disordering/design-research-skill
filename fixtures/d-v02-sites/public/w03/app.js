import {shell, button, press, feedback, esc, readSaved, save} from '/shared/common.js';
const brand='校园设备报修';
const state=readSaved()||{device:'投影仪',room:'',detail:'',attempts:0,receipt:null};
function form(note='',role='alert'){
  shell(brand,'填写工单',`${feedback(note,role)}<label for="device">报修设备</label><select id="device">${['投影仪','打印机'].map(d=>`<option ${d===state.device?'selected':''}>${d}</option>`).join('')}</select>
    <label for="room">房间号</label><input id="room" value="${esc(state.room)}">
    <label for="detail">故障描述</label><textarea id="detail">${esc(state.detail)}</textarea>
    ${button('save','保存草稿')}${button('next','核对工单',true)}`);
  function capture(){for(const id of ['device','room','detail'])state[id]=document.getElementById(id).value;}
  press('save',()=>{capture();save(state);form('草稿已保存。','status');});
  press('next',()=>{capture();if(!state.room.trim()||!state.detail.trim())return form('请填写房间号和故障描述。');review();});
}
function receipt(){shell(brand,'工单已提交',`<p role="status">工单号 ${state.receipt}</p><p>${esc(state.room)} · ${esc(state.device)}</p><p>状态：待派单</p>`);}
function review(note=''){shell(brand,'核对工单',`<section class="card"><p>${esc(state.room)} · ${esc(state.device)}</p><p>${esc(state.detail)}</p></section>${feedback(note)}${button('edit','返回编辑')}${button('send',note?'重新提交':'提交工单',true)}`);
  press('edit',()=>form());press('send',()=>{state.attempts+=1;
    if(state.attempts===1){save(state);return review('网络暂不可用，内容已保留。');}
    state.receipt='M-318';save(state);receipt();});}
if(state.receipt)receipt();else form();
