import http from 'node:http';
import {spawn} from 'node:child_process';
import {fileURLToPath} from 'node:url';
const url='http://127.0.0.1:4173/session.html';
const healthy=await new Promise(resolve=>{const request=http.get(url,res=>{res.resume();resolve(res.statusCode===200);});request.setTimeout(1800,()=>request.destroy());request.on('error',()=>resolve(false));});
if(healthy){
 console.log('本地界面服务已经运行，无需重复启动。');
 console.log('请在浏览器打开：'+url);
}else{
 console.log('正在启动交互界面：'+url);
 console.log('请保持此窗口开启。后端引擎需另行启动。');
 const child=spawn(process.execPath,[fileURLToPath(new URL('./server.mjs',import.meta.url))],{cwd:fileURLToPath(new URL('.',import.meta.url)),stdio:'inherit',windowsHide:true});
 child.on('error',err=>{console.error('启动失败：'+err.message);process.exitCode=1;});
 child.on('exit',code=>{if(code)console.error('服务退出，请查看上方错误。');process.exitCode=code||0;});
}
