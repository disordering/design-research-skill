const articles=[{id:'m1',title:'温度与釉色',type:'展签'},{id:'m2',title:'匠人手记',type:'导览'},{id:'m3',title:'灯下的刻纹',type:'展签'}];
let category='全部资料', chosen=[], removed=null;
const one=id=>document.getElementById(id);
const btn=(s,fn)=>{const b=document.createElement('button');b.type='button';b.textContent=s;b.onclick=fn;return b;};
function page(title,hint){one('heading').textContent=title;one('hint').textContent=hint;one('tools').replaceChildren();one('list').replaceChildren();one('status').textContent='';}
function card(item,button){const row=document.createElement('article');row.className='item';const label=document.createElement('div'),title=document.createElement('strong'),type=document.createElement('small');title.textContent=item.title;type.textContent=item.type;label.append(title,type);row.append(label,button);one('list').append(row);}
function catalog(){
 page('资料目录','按分类浏览，加入今天要带到现场的资料。');
 const label=document.createElement('label');label.textContent='分类';const select=document.createElement('select');for(const type of ['全部资料','展签','导览'])select.add(new Option(type,type));select.value=category;select.onchange=()=>{category=select.value;catalog()};label.append(select);one('tools').append(label,btn('查看清单（'+chosen.length+'）',list));
 for(const item of articles.filter(x=>category==='全部资料'||x.type===category)){
  const selected=chosen.includes(item.id);const b=btn(selected?'已加入':'加入清单',()=>{chosen.push(item.id);catalog();one('status').textContent='已加入《'+item.title+'》。'});b.disabled=selected;card(item,b);
 }
}
function list(){
 page('随行清单','共 '+chosen.length+' 份资料。');one('tools').append(btn('返回目录',catalog));
 if(removed){one('tools').append(btn('撤销刚才移除',()=>{const {id,index}=removed;removed=null;if(!chosen.includes(id))chosen.splice(index,0,id);list();one('status').textContent='已恢复资料。'}));}
 for(const id of chosen){const item=articles.find(x=>x.id===id);card(item,btn('移出',()=>{const index=chosen.indexOf(id);chosen.splice(index,1);removed={id,index};list();one('status').textContent='已移出《'+item.title+'》。'}));}
 if(!chosen.length)one('status').textContent='清单为空。';
}
catalog();
